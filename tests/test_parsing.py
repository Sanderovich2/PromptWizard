"""Lenient JSON extraction: fences, surrounding prose, arrays, coercion."""

from __future__ import annotations

from promptwizard.parsing import as_int, as_list, as_str, extract_json


def test_plain_object():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_fenced_block():
    text = 'Sure!\n```json\n{"a": 2}\n```\nHope that helps.'
    assert extract_json(text) == {"a": 2}


def test_object_embedded_in_prose():
    assert extract_json('Here you go: {"a": {"b": 3}} end') == {"a": {"b": 3}}


def test_array_payload():
    assert extract_json("[1, 2, 3]") == [1, 2, 3]


def test_braces_inside_strings_do_not_break_scanning():
    assert extract_json('{"a": "}"}') == {"a": "}"}


def test_no_json_returns_none():
    assert extract_json("plain prose only") is None
    assert extract_json("") is None


def test_coercion_helpers():
    assert as_str(None, "x") == "x"
    assert as_str(7) == "7"
    assert as_list("a") == ["a"]
    assert as_list(None) == []
    assert as_int("72/100") == 72
    assert as_int(True, 5) == 5
    assert as_int("nothing") == 0
