"""Tests for the shape-diff itself — the safety net needs its own net.

The diff's whole job is to catch a frontend-breaking change in the wire format
while ignoring the value differences that seed-vs-real data guarantees. These
tests pin both halves: the classes of change it must fail on, and the ones it
must stay quiet about.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from parity_lib import (  # noqa: E402
    compare_pair,
    contract_check,
    coverage,
    kind_of,
    merge_shapes,
    shape_of,
)


def pair(json_body, status=200):
    return {"order": 1, "endpoint": "get_children", "case": "happy",
            "rw": "read", "request": {"method": "GET", "path": "/get_children"},
            "response": {"status": status, "json": json_body}}


def problems(xano, local, status=200, local_status=200):
    p, _ = compare_pair(pair(xano, status), local_status, True, local)
    return p


def warnings(xano, local):
    _, w = compare_pair(pair(xano), 200, True, local)
    return w


# --- what the diff must catch ------------------------------------------------

def test_dropped_null_key_fails():
    """Appendix A: every row carries every key. exclude_none would drop one."""
    xano = {"id": "u1", "name": "A", "pronoun": None}
    local = {"id": "u1", "name": "A"}
    assert any("pronoun" in m for m in problems(xano, local))


def test_extra_local_key_fails():
    assert any("debug" in m for m in problems({"id": "u1"},
                                              {"id": "u1", "debug": True}))


def test_created_at_as_iso_string_fails():
    """The classic port bug: a datetime serialized ISO instead of epoch ms."""
    xano = {"created_at": 1787561676634}
    local = {"created_at": "2026-08-05T09:31:00Z"}
    msgs = problems(xano, local)
    assert any("JSON type differs" in m for m in msgs)
    assert any("epoch milliseconds" in m for m in msgs)


def test_created_at_in_seconds_fails_the_contract():
    """Same JSON type, wrong magnitude — shape alone would miss this."""
    assert any("epoch milliseconds" in m
               for m in problems({"created_at": 1787561676634},
                                 {"created_at": 1787561676}))


def test_date_of_birth_must_stay_a_yyyy_mm_dd_string():
    assert any("YYYY-MM-DD" in m
               for m in problems({"date_of_birth": "2026-08-05"},
                                 {"date_of_birth": "2026-08-05T00:00:00"}))


def test_boolean_as_int_fails():
    """formats.md: default_child is false, not 0, not ""."""
    assert any("true/false" in m for m in problems({"default_child": False},
                                                   {"default_child": 0}))


def test_user_id_as_string_fails():
    """Mixed PK conventions: user_id is an integer, uuid PKs are strings."""
    assert problems({"user_id": 42}, {"user_id": "42"})


def test_status_code_difference_fails():
    assert any("status" in m for m in problems({"m": 1}, {"m": 1}, 400, 200))


def test_error_envelope_key_change_fails():
    """env.js reads data?.message; renaming it makes every UI error generic."""
    xano = {"code": "ERROR_CODE_INPUT_ERROR", "message": "Record already exists",
            "payload": None}
    local = {"code": "ERROR_CODE_INPUT_ERROR", "detail": "Record already exists",
             "payload": None}
    msgs = problems(xano, local, 400, 400)
    assert any("message" in m for m in msgs) and any("detail" in m for m in msgs)


def test_nested_and_list_element_shapes_are_compared():
    xano = {"children": [{"id": "c1", "lat": 31.5}]}
    local = {"children": [{"id": "c1", "lat": "31.5"}]}
    assert any("children[].lat" in m for m in problems(xano, local))


def test_key_missing_from_only_some_local_rows_fails():
    """Xano emits every key on every row; a conditional key locally does not."""
    xano = {"rows": [{"id": "a", "place_id": "p"}, {"id": "b", "place_id": None}]}
    local = {"rows": [{"id": "a", "place_id": "p"}, {"id": "b"}]}
    assert any("place_id" in m for m in problems(xano, local))


def test_non_json_local_body_fails():
    p, _ = compare_pair(pair({"ok": True}), 200, False, "<html>500</html>")
    assert any("JSON" in m for m in p)


# --- what the diff must NOT flag ---------------------------------------------

def test_different_values_are_not_a_problem():
    """The whole point of 8.2: real data vs seed data, same shape."""
    xano = {"id": "c1", "name": "Amina", "created_at": 1787561676634,
            "lat": 31.5204, "default_child": False}
    local = {"id": "c9", "name": "Someone Else", "created_at": 1700000000000,
             "lat": 0.0, "default_child": False}
    assert problems(xano, local) == []


def test_int_and_float_are_one_number_kind():
    """formats.md: lat/lon arrive as float in 357 rows and int in 148."""
    assert problems({"lat": 31, "lon": 74.3}, {"lat": 31.5, "lon": 74}) == []


def test_empty_vs_populated_string_is_data_not_shape():
    """384/505 rows hold "" for relationship_focus; both are strings."""
    assert problems({"relationship_focus": ""},
                    {"relationship_focus": "child"}) == []


def test_empty_list_on_one_side_warns_but_does_not_fail():
    """Seed data legitimately returns nothing for a real user's query."""
    p, w = compare_pair(pair({"rows": [{"id": "a"}]}), 200, True, {"rows": []})
    assert p == []
    assert any("unverifiable" in m for m in w)


def test_null_on_one_side_only_warns():
    """A nullable column showing null on one side is expected with
    different data — but it is where a null-vs-empty break would show, so it
    is surfaced as a warning rather than swallowed."""
    p, w = compare_pair(pair({"pronoun": None}), 200, True, {"pronoun": "she/her"})
    assert p == []
    assert any("null-vs-empty" in m for m in w)


def test_different_message_text_warns_only():
    xano = {"code": "E", "message": "Invalid Credentials.", "payload": None}
    local = {"code": "E", "message": "Invalid credentials", "payload": None}
    p, w = compare_pair(pair(xano, 401), 401, True, local)
    assert p == []
    assert any("message text" in m for m in w)


def test_contract_violation_on_the_xano_side_is_a_warning_not_a_failure():
    """Reality wins over Appendix A (plan Phase 4) — if live Xano disagrees,
    the doc is what changes, so the diff must not fail the port for it."""
    p, w = compare_pair(pair({"created_at": "2026-08-05"}), 200, True,
                        {"created_at": "2026-08-05"})
    assert p == []
    assert any("XANO side" in m for m in w)


def test_excusing_one_key_does_not_excuse_the_others():
    """The excuse above is per key. A second key the port gets wrong on its
    own must still fail, or one Appendix A drift would blind the whole body."""
    xano = {"created_at": "2026-08-05", "default_child": False}
    local = {"created_at": "2026-08-05", "default_child": 0}
    p, _ = compare_pair(pair(xano), 200, True, local)
    assert p and all("default_child" in m for m in p)
    assert not any("created_at" in m for m in p)


# --- units -------------------------------------------------------------------

def test_bool_is_not_a_number():
    assert kind_of(True) == "bool" and kind_of(1) == "number"


def test_merge_marks_keys_absent_from_some_elements_optional():
    merged = merge_shapes(shape_of({"a": 1, "b": 2}), shape_of({"a": 1}))
    assert merged["optional"] == {"b"}


def test_contract_check_walks_nested_structures():
    bad = contract_check({"data": {"rows": [{"created_at": 12}]}})
    assert len(bad) == 1 and "data.rows[0].created_at" in bad[0]


def test_id_alone_carries_no_format_rule():
    """`id` is a uuid string in children but an integer in `user`."""
    assert contract_check({"id": 7}) == [] and contract_check({"id": "u"}) == []


def test_coverage_reports_missing_endpoints():
    pairs = [{"endpoint": "get_children"}, {"endpoint": "get_children"}]
    covered, missing = coverage(pairs, ["get_children", "add_children"])
    assert covered == ["get_children"] and missing == ["add_children"]


@pytest.mark.parametrize("value", [None, True, 1, 1.5, "", "x", [], {}])
def test_shape_of_accepts_every_json_value(value):
    assert "kinds" in shape_of(value)
