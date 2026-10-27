"""Example connectors (calendar, profile, finance) through the full gatekeeper."""
from datetime import datetime

import pytest

from gatekeeper.core import Gatekeeper
from gatekeeper.store import Store

NOV = {"start": "2026-11-01T00:00:00", "end": "2026-12-01T00:00:00"}
AGENT = "travel-agent"


@pytest.fixture
def gk():
    g = Gatekeeper(Store(), data_now=lambda: datetime(2026, 10, 27, 12))
    g.connect_agent(AGENT)
    return g


def test_catalog_lists_all_sources(gk):
    cat = gk.registry.catalog()
    assert set(cat) == {"calendar", "profile", "finance"}
    assert cat["calendar"]["operations"]["free_slots"]["exposure"] == 1


def test_free_slots_reveal_no_details_and_find_trip_window(gk):
    r = gk.handle(AGENT, "calendar.free_slots", {**NOV, "min_hours": 72})
    assert r["withheld"] == 0
    assert all(set(s) == {"start", "end", "hours"} for s in r["data"])
    assert any(s["start"] <= "2026-11-19" and s["end"] >= "2026-11-22" for s in r["data"])


def test_calendar_events_filtered(gk):
    titles = {d["title"] for d in gk.handle(AGENT, "calendar.events", NOV)["data"]}
    assert "Team standup" in titles
    for hidden in ("Mortgage advisor call", "Call with Barclays re: loan", "Physio appointment"):
        assert hidden not in titles


def test_notes_field_adds_sensitivity(gk):
    r = gk.handle(AGENT, "calendar.events", {**NOV, "fields": ["title", "notes"]})
    assert "Mum's birthday lunch" not in {d["title"] for d in r["data"]}


def test_finance_denied_under_balanced(gk):
    assert gk.handle(AGENT, "finance.transactions")["withheld"] == 7
    assert gk.handle(AGENT, "finance.spending_summary")["data"] == []


def test_profile(gk):
    assert gk.handle(AGENT, "profile.preferences", {"category": "travel"})["data"][0]["travel"]["seat"] == "window"
    assert gk.handle(AGENT, "profile.field", {"name": "passport_number"})["data"] == []
