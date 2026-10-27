"""HTTP API for the dashboard and for ordinary (non-MCP) apps.

Run: .venv/bin/uvicorn gatekeeper.api:app --port 8000 --reload
Shares the SQLite DB with the MCP server, so dashboard changes apply to Claude Desktop too.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from .core import Gatekeeper  # noqa: E402
from .interpreter import Interpreter  # noqa: E402
from .models import CATEGORIES  # noqa: E402
from .policy import TEMPLATES  # noqa: E402
from .store import Store  # noqa: E402


class TemplateIn(BaseModel):
    name: str


class RuleIn(BaseModel):
    effect: str
    category: str
    agents: list[str] = ["*"]


class AgentIn(BaseModel):
    agent: str
    hours: float = 24
    operations: list[str] = ["*"]


class ResolveIn(BaseModel):
    choice: str


class QueryIn(BaseModel):
    agent: str
    operation: str
    params: dict = {}


class RequestIn(BaseModel):
    agent: str
    request: str


def create_app(gk: Gatekeeper | None = None, interpreter: Interpreter | None = None) -> FastAPI:
    gk = gk or Gatekeeper(Store(os.getenv("GATEKEEPER_DB", str(ROOT / "gatekeeper.db"))))
    state = {"interp": interpreter}

    def interp() -> Interpreter:
        if state["interp"] is None:
            state["interp"] = Interpreter()
        return state["interp"]

    app = FastAPI(title="Privacy Gatekeeper")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                       allow_methods=["*"], allow_headers=["*"])

    def bad(exc: Exception):
        raise HTTPException(400, str(exc))

    # --- dashboard -----------------------------------------------------
    @app.get("/api/overview")
    def overview():
        return {
            "template": gk.store.get_setting("template"),
            "templates": {k: {c: e.value for c, e in v.items()} for k, v in TEMPLATES.items()},
            "categories": sorted(CATEGORIES),
            "rules": [{"id": r.id, "effect": r.effect.value, "category": r.category,
                       "agents": list(r.agents), "source": r.source} for r in gk.store.list_rules()],
            "grants": [{**g, "expires_at": g["expires_at"].isoformat()} for g in gk.store.list_grants()],
            "escalations": gk.store.list_escalations("pending"),
            "digest": gk.digest(),
            "sources": gk.registry.catalog(),
            "interpreter": os.getenv("INTERPRETER", "mock"),
        }

    @app.get("/api/ledger")
    def ledger(limit: int = 100):
        return gk.store.ledger(limit)

    @app.post("/api/template")
    def set_template(body: TemplateIn):
        try:
            gk.apply_template(body.name)
        except ValueError as e:
            bad(e)
        return {"ok": True}

    @app.post("/api/rules")
    def add_rule(body: RuleIn):
        try:
            r = gk.add_user_rule(body.effect, body.category, agents=tuple(body.agents))
        except ValueError as e:
            bad(e)
        return {"id": r.id}

    @app.delete("/api/rules/{rule_id}")
    def delete_rule(rule_id: str):
        if not rule_id.startswith("user:"):
            raise HTTPException(400, "Template rules change via the template selector")
        gk.store.delete_rule(rule_id)
        return {"ok": True}

    @app.post("/api/agents")
    def connect(body: AgentIn):
        gk.connect_agent(body.agent, body.hours, body.operations)
        return {"ok": True}

    @app.post("/api/agents/{agent}/revoke")
    def revoke(agent: str):
        gk.revoke_agent(agent)
        return {"ok": True}

    @app.post("/api/escalations/{esc_id}")
    def resolve(esc_id: str, body: ResolveIn):
        try:
            rule = gk.resolve_escalation(esc_id, body.choice)
        except ValueError as e:
            bad(e)
        return {"rule": rule.id if rule else None}

    # --- agent-facing HTTP (for non-MCP apps) --------------------------
    @app.post("/api/query")
    def query(body: QueryIn):
        return gk.handle(body.agent, body.operation, body.params)

    @app.post("/api/request")
    def request(body: RequestIn):
        try:
            return gk.request_data(body.agent, body.request, interp())
        except Exception as e:  # noqa: BLE001
            raise HTTPException(503, f"Interpreter unavailable: {e}")

    return app


app = create_app()
