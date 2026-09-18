from __future__ import annotations

import json

import pytest

from promptwizard.errors import LLMResponseError
from promptwizard.i18n import get_translator
from promptwizard.translate import build_system_prompt, build_user_prompt, parse


def test_parse_reads_the_translation():
    assert parse(json.dumps({"translated_prompt": "Hello", "language": "en"})) == "Hello"


def test_parse_accepts_the_plain_field_name():
    assert parse(json.dumps({"prompt": "Hello"})) == "Hello"


def test_parse_rejects_an_empty_translation():
    with pytest.raises(LLMResponseError):
        parse(json.dumps({"translated_prompt": "  "}))


def test_parse_rejects_prose():
    with pytest.raises(LLMResponseError):
        parse("I cannot translate this.")


def test_the_system_prompt_names_the_target_language():
    system = build_system_prompt(get_translator("ru"), "en")
    assert "английский" in system
    assert "STRICT JSON" in system


def test_the_user_prompt_wraps_the_text():
    assert "Hello there" in build_user_prompt("Hello there")


def test_the_custom_instructions_are_appended():
    system = build_system_prompt(get_translator("en"), "ru", "Keep the product names.")
    assert "Keep the product names." in system
    assert system.startswith("You are PromptWizard")
