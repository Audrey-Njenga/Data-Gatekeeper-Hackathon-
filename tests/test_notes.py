from datetime import datetime

import pytest

from gatekeeper.core import Gatekeeper
from gatekeeper.store import Store

AGENT = "travel-agent"


@pytest.fixture
def gk():
    g = Gatekeeper(Store(), data_now=lambda: datetime(2026, 10, 27, 12))
    g.connect_agent(AGENT)
    return g


def test_notes_registered(gk):
    assert set(gk.registry.catalog()["notes"]["operations"]) == {"count", "search", "read"}


def test_search_returns_excerpts_not_whole_notes(gk):
    r = gk.handle(AGENT, "notes.search", {"query": "lisbon"})
    (note,) = r["data"]
    assert set(note) == {"id", "title", "excerpt"} and len(note["excerpt"]) <= 160


def test_folder_tag_hides_finance_note(gk):
    r = gk.handle(AGENT, "notes.search", {"query": "advisor"})
    assert r["data"] == [] and r["withheld"] == 1


def test_content_classifier_flags_untagged_note(gk):
    # packing list sits in travel/ but mentions a passport -> credentials -> denied
    r = gk.handle(AGENT, "notes.search", {"query": "packing"})
    assert r["data"] == []


def test_read_is_private_notes_and_needs_approval(gk):
    r = gk.handle(AGENT, "notes.read", {"id": "note:travel/lisbon-ideas"})
    assert r["data"] == [] and r["pending_approval"] == 1
    esc = next(e for e in gk.store.list_escalations() if e["category"] == "private_notes")
    gk.resolve_escalation(esc["id"], "always")
    r = gk.handle(AGENT, "notes.read", {"id": "note:travel/lisbon-ideas"})
    assert "pastel de nata" in r["data"][0]["body"]


def test_count_reveals_nothing(gk):
    r = gk.handle(AGENT, "notes.count", {"query": "knee"})
    assert r["data"] == [{"query": "knee", "count": 2}]
