"""Deterministic policy engine. The only component allowed to authorise a release.

Precedence per category:
  1. Any matching DENY rule (template or user) -> deny. Deny always wins.
  2. Otherwise user rules decide (ask beats allow).
  3. Otherwise template rules decide (ask beats allow).
  4. No rule at all -> ask (fail closed).
Per item: deny if any category denies, else ask if any asks, else allow.
"""
from __future__ import annotations

from .models import Decision, Effect, Rule

A, Q, D = Effect.ALLOW, Effect.ASK, Effect.DENY

TEMPLATES: dict[str, dict[str, Effect]] = {
    "strict": {
        "financial": D, "health": D, "credentials": D, "private_notes": D,
        "people": Q, "location": Q, "work": Q, "general": A,
    },
    "balanced": {
        "financial": D, "credentials": D,
        "health": Q, "location": Q, "private_notes": Q,
        "people": A, "work": A, "general": A,
    },
    "open": {
        "credentials": D,
        "financial": Q, "health": Q,
        "location": A, "private_notes": A, "people": A, "work": A, "general": A,
    },
}


def template_rules(name: str) -> list[Rule]:
    if name not in TEMPLATES:
        raise ValueError(f"Unknown template '{name}'. Options: {sorted(TEMPLATES)}")
    return [
        Rule(id=f"tpl:{name}:{cat}", effect=eff, category=cat, source="template")
        for cat, eff in TEMPLATES[name].items()
    ]


class PolicyEngine:
    def __init__(self, rules: list[Rule]):
        self.rules = rules

    def decide_category(self, agent: str, operation: str, category: str) -> tuple[Effect, list[str]]:
        matched = [r for r in self.rules if r.matches(agent, operation, category)]
        denies = [r for r in matched if r.effect == D]
        if denies:
            return D, [r.id for r in denies]
        user = [r for r in matched if r.source == "user"]
        template = [r for r in matched if r.source != "user"]
        for pool in (user, template):
            if pool:
                asks = [r for r in pool if r.effect == Q]
                return (Q, [r.id for r in asks]) if asks else (A, [r.id for r in pool])
        return Q, ["default:ask"]

    def decide(self, agent: str, operation: str, categories: set[str]) -> Decision:
        per_category: dict[str, Effect] = {}
        rule_ids: list[str] = []
        for cat in sorted(categories or {"general"}):
            effect, ids = self.decide_category(agent, operation, cat)
            per_category[cat] = effect
            rule_ids.extend(ids)
        effects = set(per_category.values())
        overall = D if D in effects else Q if Q in effects else A
        return Decision(effect=overall, per_category=per_category, rule_ids=rule_ids)
