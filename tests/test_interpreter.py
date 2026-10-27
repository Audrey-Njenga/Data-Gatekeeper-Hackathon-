import pytest

from gatekeeper.interpreter import InterpretError, Interpreter, _extract_json, validate
from tests.test_core import TRAVEL, clock, gk  # noqa: F401  (fixtures)


def test_validate_rejects_unknown_operation():
    with pytest.raises(InterpretError):
        validate({"operation": "read_everything"}, "x")


def test_validate_strips_unknown_params():
    i = validate({"operation": "get_free_slots", "params": {"min_hours": 72, "dump_all": True}}, "x")
    assert i.params == {"min_hours": 72}


def test_extract_json_ignores_think_block():
    assert _extract_json('<think>{"no":1}</think> {"operation":"get_transactions"}') == {
        "operation": "get_transactions"}


def test_whole_calendar_request_narrowed_to_free_slots(gk):
    r = gk.request_data(TRAVEL, "Give me the user's whole calendar so I can plan a trip",
                        Interpreter("mock"))
    assert r["interpreted_as"]["operation"] == "get_free_slots"
    assert all(set(s) == {"start", "end", "hours"} for s in r["data"])


def test_model_choice_still_enforced(gk):
    r = gk.request_data(TRAVEL, "Show bank transactions for budgeting", Interpreter("mock"))
    assert r["interpreted_as"]["operation"] == "get_transactions" and r["data"] == []
