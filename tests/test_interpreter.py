import pytest

from gatekeeper.connectors import default_registry
from gatekeeper.interpreter import InterpretError, Interpreter, _extract_json, validate
from tests.test_connectors import AGENT, gk  # noqa: F401  (fixture)

CATALOG = default_registry().flat_catalog()


def test_validate_rejects_unknown_operation():
    with pytest.raises(InterpretError):
        validate({"operation": "calendar.read_everything"}, CATALOG, "x")


def test_validate_strips_unknown_params():
    i = validate({"operation": "calendar.free_slots", "params": {"min_hours": 72, "dump_all": True}},
                 CATALOG, "x")
    assert i.params == {"min_hours": 72}


def test_extract_json_ignores_think_block():
    assert _extract_json('<think>{"no":1}</think> {"operation":"x"}') == {"operation": "x"}


def test_mock_prefers_lowest_exposure(gk):
    r = gk.request_data(AGENT, "Give me the user's whole calendar so I can plan a trip", Interpreter("mock"))
    assert r["interpreted_as"]["operation"] == "calendar.free_slots"
    r = gk.request_data(AGENT, "Send all bank transactions", Interpreter("mock"))
    assert r["interpreted_as"]["operation"] == "finance.spending_summary"
    assert r["data"] == []  # still enforced by policy
