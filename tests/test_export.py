"""Export rendering: Markdown, plain text, JSON."""

from __future__ import annotations

import json

import pytest

from promptwizard.analyzer import Analysis, Issue
from promptwizard.errors import StorageError
from promptwizard.export import render, to_markdown, to_text
from promptwizard.pipeline import SessionResult
from promptwizard.rewriter import Rewrite


def _result() -> SessionResult:
    return SessionResult(
        id="20260101-000000-abcdef",
        started_at="2026-01-01T00:00:00+03:00",
        finished_at="2026-01-01T00:00:05+03:00",
        provider="offline",
        model="-",
        mode="offline",
        prompt_language="en",
        ui_language="en",
        original_prompt="Write something",
        analysis=Analysis(
            language="en",
            score=20,
            summary="weak",
            issues=(Issue("format", "high", "No format", "add one"),),
        ),
        questions=(),
        answers={},
        rewrite=Rewrite(
            improved_prompt="Task:\nWrite something",
            changes=("Specified the format.",),
            language="en",
        ),
        warnings=(),
    )


def test_markdown_carries_every_section(translator):
    text = to_markdown(_result(), translator)
    assert "Write something" in text
    assert "No format" in text
    assert "Task:" in text
    assert "Specified the format." in text


def test_text_export_is_plain(translator):
    text = to_text(_result(), translator)
    assert "ORIGINAL PROMPT" in text
    assert "Write something" in text


def test_json_export_round_trips(translator):
    payload = json.loads(render(_result(), "json", translator))
    assert payload["id"] == "20260101-000000-abcdef"
    assert payload["rewrite"]["improved_prompt"].startswith("Task:")
    assert payload["analysis"]["issues"][0]["category"] == "format"


def test_unknown_format_is_rejected(translator):
    with pytest.raises(StorageError):
        render(_result(), "docx", translator)
