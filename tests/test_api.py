from fastapi.testclient import TestClient

from gatekeeper.api import create_app
from gatekeeper.core import Gatekeeper
from gatekeeper.interpreter import Interpreter
from gatekeeper.store import Store


def client():
    return TestClient(create_app(Gatekeeper(Store()), Interpreter("mock")))


def test_dashboard_flow():
    c = client()
    assert c.post("/api/agents", json={"agent": "a"}).status_code == 200
    r = c.post("/api/query", json={"agent": "a", "operation": "calendar.events",
                                   "params": {"start": "2026-11-01T00:00:00", "end": "2026-12-01T00:00:00"}})
    assert r.json()["pending_approval"] > 0

    ov = c.get("/api/overview").json()
    assert ov["template"] == "balanced" and set(ov["sources"]) == {"calendar", "profile", "finance", "notes"}
    esc = ov["escalations"][0]
    rule = c.post(f"/api/escalations/{esc['id']}", json={"choice": "always"}).json()["rule"]
    assert rule.startswith("user:")
    assert c.delete(f"/api/rules/{rule}").status_code == 200
    assert c.delete("/api/rules/tpl:balanced:financial").status_code == 400

    assert c.post("/api/template", json={"name": "strict"}).status_code == 200
    assert c.post("/api/template", json={"name": "nope"}).status_code == 400

    c.post("/api/agents/a/revoke")
    assert c.post("/api/query", json={"agent": "a", "operation": "calendar.free_slots"}).json()["error"] == "revoked"
    assert len(c.get("/api/ledger").json()) == 2


def test_free_text_request():
    c = client()
    c.post("/api/agents", json={"agent": "a"})
    r = c.post("/api/request", json={"agent": "a", "request": "my calendar availability"}).json()
    assert r["interpreted_as"]["operation"] == "calendar.free_slots"
