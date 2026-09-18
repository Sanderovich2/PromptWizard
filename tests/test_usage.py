from __future__ import annotations

from promptwizard.usage import CHARS_PER_TOKEN, estimate_tokens


def test_empty_text_counts_as_nothing():
    assert estimate_tokens("") == 0
    assert estimate_tokens("   \n  ") == 0


def test_short_text_still_costs_one_token():
    assert estimate_tokens("hi") == 1


def test_the_estimate_grows_with_the_text():
    assert estimate_tokens("x" * CHARS_PER_TOKEN) == 1
    assert estimate_tokens("x" * (CHARS_PER_TOKEN + 1)) == 2


def test_the_estimate_is_deterministic():
    text = "Analyze this prompt and rewrite it."
    assert estimate_tokens(text) == estimate_tokens(text)
