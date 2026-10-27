"""Gatekeeper orchestration: grant check -> typed operation -> policy -> ledger."""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Callable

from .models import CATEGORIES, Effect, Rule
from .policy import PolicyEngine, template_rules
from .store import Store
from .transformers import OPERATIONS, DataBundle


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Gatekeeper:
    def __init__(self, store: Store, data: DataBundle | None = None,
                 clock: Callable[[], datetime] = _utcnow, data_now: Callable[[], datetime] | None = None):
        self.store = store
        self.data = data or DataBundle.load()
        self.clock = clock  # UTC, used for grants/ledger
        self.data_now = data_now or (lambda: datetime.now())  # naive local, used for calendar defaults
        if not self.store.get_setting("template"):
            self.apply_template("balanced")

    # --- configuration -------------------------------------------------
    def apply_template(self, name: str) -> None:
        rules = template_rules(name)
        self.store.delete_template_rules()
        for r in rules:
            self.store.add_rule(r, self.clock())
        self.store.set_setting("template", name)

    def add_user_rule(self, effect: str, category: str, agents=("*",), operations=("*",)) -> Rule:
        if category not in CATEGORIES:
            raise ValueError(f"Unknown category '{category}'")
        rule = Rule(id=f"user:{uuid.uuid4().hex[:8]}", effect=Effect(effect), category=category,
                    agents=tuple(agents), operations=tuple(operations), source="user")
        self.store.add_rule(rule, self.clock())
        return rule

    def connect_agent(self, agent: str, hours: float = 24, operations: list[str] | None = None) -> None:
        now = self.clock()
        self.store.upsert_grant(agent, operations or ["*"], now + timedelta(hours=hours), now)

    def revoke_agent(self, agent: str) -> None:
        self.store.revoke_grant(agent)

    def resolve_escalation(self, esc_id: str, choice: str) -> Rule | None:
        """choice: 'always' -> user allow rule, 'never' -> user deny rule, 'dismiss' -> no rule.
        Applies to future requests; the agent retries to receive newly allowed data."""
        esc = self.store.get_escalation(esc_id)
        if not esc or esc["status"] != "pending":
            raise ValueError("Escalation not found or already resolved")
        rule = None
        if choice in ("always", "never"):
            rule = self.add_user_rule("allow" if choice == "always" else "deny",
                                      esc["category"], agents=(esc["agent"],))
        elif choice != "dismiss":
            raise ValueError("choice must be always | never | dismiss")
        self.store.resolve_escalation(esc_id, choice, self.clock())
        return rule

    # --- request handling ---------------------------------------------
    def _grant_error(self, agent: str, operation: str) -> str | None:
        grant = self.store.get_grant(agent)
        if not grant:
            return "no_grant"
        if grant["revoked"]:
            return "revoked"
        if grant["expires_at"] <= self.clock():
            return "expired"
        if "*" not in grant["operations"] and operation not in grant["operations"]:
            return "operation_not_granted"
        return None

    def handle(self, agent: str, operation: str, params: dict | None = None,
               interpreted_from: str | None = None) -> dict:
        params = params or {}
        entry = {"ts": self.clock().isoformat(), "agent": agent, "operation": operation,
                 "params": params, "interpreted_from": interpreted_from}

        if operation not in OPERATIONS:
            self.store.log({**entry, "outcome": "unknown_operation"})
            return {"status": "error", "error": "unknown_operation", "available": sorted(OPERATIONS)}

        err = self._grant_error(agent, operation)
        if err:
            self.store.log({**entry, "outcome": err})
            return {"status": "denied", "error": err}

        try:
            items = OPERATIONS[operation](self.data, self.data_now(), **params)
        except (TypeError, ValueError) as exc:
            self.store.log({**entry, "outcome": "bad_params"})
            return {"status": "error", "error": "bad_params", "detail": str(exc)}

        policy = PolicyEngine(self.store.list_rules())
        released, hidden, escalations = [], [], []
        for item in items:
            decision = policy.decide(agent, operation, item.categories)
            if decision.effect == Effect.ALLOW:
                released.append(item)
                continue
            hidden.append({"id": item.id, "categories": sorted(item.categories),
                           "effect": decision.effect.value, "rules": decision.rule_ids})
            if decision.effect == Effect.ASK:
                for cat in decision.ask_categories:
                    esc_id = self.store.open_escalation(agent, operation, cat, self.clock())
                    if esc_id not in escalations:
                        escalations.append(esc_id)

        self.store.log({**entry, "outcome": "ok", "released": [i.id for i in released],
                        "hidden": hidden, "escalations": escalations})

        pending = sum(1 for h in hidden if h["effect"] == "ask")
        msg = f"{len(released)} item(s) shared, {len(hidden)} withheld by the user's privacy rules."
        if pending:
            msg += f" {pending} awaiting user approval; retry later."
        return {"status": "ok", "operation": operation, "data": [i.data for i in released],
                "withheld": len(hidden), "pending_approval": pending, "message": msg}

    def request_data(self, agent: str, request: str, interpreter) -> dict:
        """Free-text request -> model proposes a typed op -> normal enforcement path."""
        from .interpreter import InterpretError
        try:
            interp = interpreter.interpret(request, today=self.data_now().date().isoformat())
        except InterpretError as exc:
            self.store.log({"ts": self.clock().isoformat(), "agent": agent, "operation": "request_data",
                            "params": {}, "outcome": "uninterpretable", "interpreted_from": request[:500]})
            return {"status": "error", "error": "uninterpretable", "detail": str(exc)}
        result = self.handle(agent, interp.operation, interp.params, interpreted_from=request[:500])
        return {**result, "interpreted_as": {"operation": interp.operation, "params": interp.params,
                                             "reason": interp.reason, "backend": interp.backend}}

    # --- reporting -----------------------------------------------------
    def digest(self, since: datetime | None = None) -> dict:
        entries = [e for e in self.store.ledger(10_000)
                   if since is None or datetime.fromisoformat(e["ts"]) >= since]
        hidden_by_cat: Counter[str] = Counter()
        for e in entries:
            for h in e["hidden"]:
                hidden_by_cat.update(h["categories"])
        return {
            "requests": len(entries),
            "agents": sorted({e["agent"] for e in entries}),
            "shared": sum(len(e["released"]) for e in entries),
            "hidden": sum(len(e["hidden"]) for e in entries),
            "blocked_requests": sum(1 for e in entries if e["outcome"] != "ok"),
            "hidden_by_category": dict(hidden_by_cat),
            "pending_escalations": len(self.store.list_escalations("pending")),
        }
