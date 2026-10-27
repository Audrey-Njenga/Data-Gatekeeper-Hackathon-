"""Core gatekeeper behaviour, tested with a synthetic connector (no calendar knowledge)."""
from datetime import datetime, timedelta, timezone

import pytest

from gatekeeper.classifier import classify_text
from gatekeeper.connectors import Connector, Operation, Registry
from gatekeeper.core import Gatekeeper
from gatekeeper.models import Item
from gatekeeper.store import Store

AGENT = "agent-a"

NOTES = [
    ("n1", "Groceries list", set()),
    ("n2", "Mortgage paperwork", {"financial"}),
    ("n3", "Physio exercises", {"health"}),
    ("n4", "Project roadmap", {"work"}),
    ("n5", "Home address for parcels", {"location"}),
]


class NotesConnector(Connector):
    name = "notes"
    description = "The user's personal notes."

    def operations(self):
        return [
            Operation("titles", "Note titles only.", self.titles, {"tag": "optional"}, exposure=2),
            Operation("count", "Number of notes.", self.count, {}, exposure=1),
        ]

    def titles(self, ctx, tag=None):
        return [Item(id=i, data={"title": t}, categories=c or {"general"}) for i, t, c in NOTES]

    def count(self, ctx):
        return [Item(id="count", data={"count": len(NOTES)}, categories={"general"})]


class Clock:
    def __init__(self):
        self.t = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def gk(clock):
    g = Gatekeeper(Store(), Registry([NotesConnector()]), clock=clock,
                   data_now=lambda: datetime(2026, 10, 27, 12))
    g.connect_agent(AGENT, hours=24)
    return g


def shared(resp):
    return {d["title"] for d in resp["data"]}


def test_classifier_catches_untagged_content():
    assert "financial" in classify_text("Call with Barclays re: loan")
    assert "health" in classify_text("Therapy session")
    assert classify_text("Dinner with Sarah") == set()


def test_balanced_denies_financial_and_escalates_health(gk):
    r = gk.handle(AGENT, "notes.titles")
    assert shared(r) == {"Groceries list", "Project roadmap"}
    assert sorted(e["category"] for e in gk.store.list_escalations()) == ["health", "location"]


def test_user_deny_rule_hides_without_prompt(gk):
    gk.apply_template("open")  # open would ASK about financial
    gk.add_user_rule("deny", "financial")
    gk.handle(AGENT, "notes.titles")
    assert all(e["category"] != "financial" for e in gk.store.list_escalations())


def test_deny_beats_user_allow(gk):
    gk.add_user_rule("allow", "financial", agents=(AGENT,))
    assert "Mortgage paperwork" not in shared(gk.handle(AGENT, "notes.titles"))


def test_always_turns_escalation_into_agent_scoped_rule(gk):
    gk.handle(AGENT, "notes.titles")
    health = next(e for e in gk.store.list_escalations() if e["category"] == "health")
    gk.resolve_escalation(health["id"], "always")
    assert "Physio exercises" in shared(gk.handle(AGENT, "notes.titles"))
    gk.connect_agent("agent-b")
    gk.handle("agent-b", "notes.titles")
    assert any(e["agent"] == "agent-b" and e["category"] == "health" for e in gk.store.list_escalations())


def test_never_turns_escalation_into_deny(gk):
    gk.handle(AGENT, "notes.titles")
    for e in gk.store.list_escalations():
        gk.resolve_escalation(e["id"], "never")
    gk.handle(AGENT, "notes.titles")
    assert gk.store.list_escalations() == []


def test_strict_denies_health(gk):
    gk.apply_template("strict")
    gk.handle(AGENT, "notes.titles")
    assert all(e["category"] != "health" for e in gk.store.list_escalations())


def test_user_rules_survive_template_change(gk):
    rule = gk.add_user_rule("deny", "people")
    gk.apply_template("open")
    assert rule.id in {r.id for r in gk.store.list_rules()}


def test_revocation_blocks_next_request(gk):
    assert gk.handle(AGENT, "notes.count")["status"] == "ok"
    gk.revoke_agent(AGENT)
    assert gk.handle(AGENT, "notes.count") == {"status": "denied", "error": "revoked"}


def test_expiry_and_unknown_agent(gk, clock):
    assert gk.handle("stranger", "notes.count")["error"] == "no_grant"
    clock.t += timedelta(hours=25)
    assert gk.handle(AGENT, "notes.count")["error"] == "expired"


def test_grant_scoping_by_operation_and_source(gk):
    gk.connect_agent("counter", operations=["notes.count"])
    assert gk.handle("counter", "notes.titles")["error"] == "operation_not_granted"
    gk.connect_agent("notes-reader", operations=["notes.*"])
    assert gk.handle("notes-reader", "notes.titles")["status"] == "ok"


def test_unknown_operation_and_bad_params(gk):
    assert gk.handle(AGENT, "notes.read_everything")["error"] == "unknown_operation"
    assert gk.handle(AGENT, "notes.titles", {"evil": 1})["error"] == "bad_params"


def test_ledger_stores_ids_not_content(gk):
    gk.handle(AGENT, "notes.titles")
    blob = str(gk.store.ledger()[0])
    assert "Mortgage" not in blob and "n2" in blob


def test_digest(gk):
    gk.handle(AGENT, "notes.titles")
    gk.revoke_agent(AGENT)
    gk.handle(AGENT, "notes.titles")
    d = gk.digest()
    assert d["requests"] == 2 and d["blocked_requests"] == 1
    assert d["hidden_by_category"]["financial"] == 1 and d["pending_escalations"] == 2
