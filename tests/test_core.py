from datetime import datetime, timedelta, timezone

import pytest

from gatekeeper.classifier import classify_text
from gatekeeper.core import Gatekeeper
from gatekeeper.store import Store
from gatekeeper.transformers import DataBundle

NOV = dict(start="2026-11-01T00:00:00", end="2026-12-01T00:00:00")
TRAVEL = "travel-agent"


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
    g = Gatekeeper(Store(), DataBundle.load(), clock=clock,
                   data_now=lambda: datetime(2026, 10, 27, 12))
    g.connect_agent(TRAVEL, hours=24)
    return g


def titles(resp):
    return {d["title"] for d in resp["data"]}


def test_classifier_catches_untagged_financial():
    assert "financial" in classify_text("Call with Barclays re: loan")
    assert "health" in classify_text("Therapy session")
    assert classify_text("Dinner with Sarah") == set()


def test_balanced_hides_financial_and_escalates_health(gk):
    r = gk.handle(TRAVEL, "get_events", NOV)
    t = titles(r)
    assert "Team standup" in t and "Dinner with Sarah" in t
    for hidden in ("Mortgage advisor call", "Call with Barclays re: loan", "Pay credit card bill",
                   "Physio appointment", "Dentist", "Therapy session"):
        assert hidden not in t
    pending = gk.store.list_escalations()
    assert [e["category"] for e in pending] == ["health"]


def test_user_no_financial_rule_hides_without_prompt(gk):
    gk.apply_template("open")  # open would ASK about financial
    gk.add_user_rule("deny", "financial")
    gk.handle(TRAVEL, "get_events", NOV)
    assert all(e["category"] != "financial" for e in gk.store.list_escalations())


def test_deny_beats_user_allow(gk):
    gk.add_user_rule("allow", "financial", agents=(TRAVEL,))
    assert "Mortgage advisor call" not in titles(gk.handle(TRAVEL, "get_events", NOV))


def test_always_turns_escalation_into_rule(gk):
    gk.handle(TRAVEL, "get_events", NOV)
    (esc,) = gk.store.list_escalations()
    gk.resolve_escalation(esc["id"], "always")
    r = gk.handle(TRAVEL, "get_events", NOV)
    assert "Physio appointment" in titles(r)
    assert gk.store.list_escalations() == []
    # rule is agent-specific: another agent is still asked
    gk.connect_agent("shopping-agent")
    gk.handle("shopping-agent", "get_events", NOV)
    assert len(gk.store.list_escalations()) == 1


def test_never_turns_escalation_into_deny(gk):
    gk.handle(TRAVEL, "get_events", NOV)
    (esc,) = gk.store.list_escalations()
    gk.resolve_escalation(esc["id"], "never")
    gk.handle(TRAVEL, "get_events", NOV)
    assert gk.store.list_escalations() == []


def test_free_slots_reveal_no_details_and_find_trip_window(gk):
    r = gk.handle(TRAVEL, "get_free_slots", {**NOV, "min_hours": 72})
    assert r["withheld"] == 0
    assert all(set(s) == {"start", "end", "hours"} for s in r["data"])
    assert any(s["start"] <= "2026-11-19" and s["end"] >= "2026-11-22" for s in r["data"])


def test_notes_and_attendees_add_sensitivity(gk):
    r = gk.handle(TRAVEL, "get_events", {**NOV, "fields": ["title", "attendees", "notes"]})
    assert "Mum's birthday lunch" not in titles(r)  # home address in notes -> location (ask)


def test_transactions_denied_under_balanced(gk):
    r = gk.handle(TRAVEL, "get_transactions")
    assert r["data"] == [] and r["withheld"] == 7 and r["pending_approval"] == 0


def test_strict_denies_health(gk):
    gk.apply_template("strict")
    gk.handle(TRAVEL, "get_events", NOV)
    assert all(e["category"] != "health" for e in gk.store.list_escalations())


def test_user_rules_survive_template_change(gk):
    rule = gk.add_user_rule("deny", "people")
    gk.apply_template("open")
    assert rule.id in {r.id for r in gk.store.list_rules()}


def test_revocation_blocks_next_request(gk):
    assert gk.handle(TRAVEL, "get_free_slots", NOV)["status"] == "ok"
    gk.revoke_agent(TRAVEL)
    assert gk.handle(TRAVEL, "get_free_slots", NOV) == {"status": "denied", "error": "revoked"}


def test_expiry_and_unknown_agent(gk, clock):
    assert gk.handle("stranger", "get_free_slots")["error"] == "no_grant"
    clock.t += timedelta(hours=25)
    assert gk.handle(TRAVEL, "get_free_slots")["error"] == "expired"


def test_operation_scoped_grant(gk):
    gk.connect_agent("slots-only", operations=["get_free_slots"])
    assert gk.handle("slots-only", "get_events", NOV)["error"] == "operation_not_granted"


def test_unknown_operation_and_bad_params(gk):
    assert gk.handle(TRAVEL, "read_everything")["error"] == "unknown_operation"
    assert gk.handle(TRAVEL, "get_events", {"evil": 1})["error"] == "bad_params"


def test_ledger_stores_ids_not_content(gk):
    gk.handle(TRAVEL, "get_events", NOV)
    entry = gk.store.ledger()[0]
    blob = str(entry)
    assert "Mortgage" not in blob and "Physio" not in blob
    assert "e04" in blob


def test_digest(gk):
    gk.handle(TRAVEL, "get_events", NOV)
    gk.revoke_agent(TRAVEL)
    gk.handle(TRAVEL, "get_events", NOV)
    d = gk.digest()
    assert d["requests"] == 2 and d["blocked_requests"] == 1
    assert d["hidden_by_category"]["financial"] >= 3 and d["pending_escalations"] == 1
