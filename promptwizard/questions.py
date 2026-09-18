"""Clarifying questions, produced as one batch.

The product requirement is explicit: ask the questions **all at once**, not one
by one.  So both producers return the whole list, and the caller (CLI or GUI)
renders them together and collects the answers together.

The model writes the wording; :func:`heuristic` derives questions from the
analysis gaps using the locale catalog, so the offline mode still asks sensible
things.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from promptwizard.analyzer import Analysis
from promptwizard.errors import LLMResponseError
from promptwizard.i18n import Translator
from promptwizard.parsing import as_list, as_str, extract_json

__all__ = [
    "Question",
    "build_system_prompt",
    "build_user_prompt",
    "heuristic",
    "parse",
]

#: Gap category -> catalog key of the heuristic question.  Several gaps collapse
#: onto one question on purpose: a user is asked once.
_CATEGORY_TO_QUESTION: dict[str, str] = {
    "missing_detail": "length",
    "scope": "length",
    "format": "format",
    "structure": "format",
    "audience": "audience",
    "constraints": "constraints",
    "examples": "examples",
    "context": "context",
    "ambiguity": "context",
    "weak_phrasing": "context",
    "clarity": "context",
    "tone": "tone",
}
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class Question:
    """One clarifying question.

    Attributes:
        id: Stable id used as the key of the matching answer.
        text: The question (in the UI language).
        why: Why the answer changes the rewrite.
        kind: ``free`` or ``choice``.
        options: Suggested answers for a ``choice`` question.
    """

    id: str
    text: str
    why: str = ""
    kind: str = "free"
    options: tuple[str, ...] = ()


def build_system_prompt(translator: Translator, limit: int) -> str:
    """System instruction asking for a JSON array of at most ``limit`` questions."""
    schema = (
        '{"questions":[{"id":"<short_snake_case>","text":"<the question>",'
        '"why":"<why the answer matters>","kind":"free|choice","options":["<suggestion>"]}]}'
    )
    return (
        "You are PromptWizard. Given a prompt and its known weaknesses, write the clarifying "
        "questions whose answers would most improve the prompt. Answer with STRICT JSON only:\n"
        + schema
        + "\nRules:\n"
        f"- At most {limit} questions.\n"
        "- Ask everything in one batch; never ask to continue a dialogue.\n"
        "- Ask only about what is genuinely missing; do not restate the prompt.\n"
        "- Prefer a few sharp questions over many shallow ones. An empty list is acceptable "
        "when the prompt is already fully specified.\n"
        f'- Write "text" and "why" in {translator("language." + translator.lang)}.\n'
        '- Use "choice" with 2-5 short "options" when the space of answers is small.'
    )


def build_user_prompt(prompt: str, analysis: Analysis) -> str:
    """User turn: the prompt plus the issue list the questions must address."""
    lines = ["Original prompt:", prompt.strip(), "", "Known weaknesses:"]
    if analysis.issues:
        for issue in analysis.issues:
            lines.append(f"- [{issue.severity}] {issue.category}: {issue.title}")
    else:
        lines.append("- (none reported)")
    return "\n".join(lines)


def parse(text: str, limit: int = 6) -> tuple[Question, ...]:
    """Parse the model answer into a tuple of questions.

    Raises:
        LLMResponseError: The answer contained no usable JSON.
    """
    data = extract_json(text)
    if isinstance(data, Mapping):
        entries = as_list(data.get("questions"))
    elif isinstance(data, list):
        entries = data
    else:
        raise LLMResponseError(
            "questions: the model did not return a JSON list",
            hint_key="error.provider.bad_response",
            hint_kwargs={"provider": "api"},
        )
    questions: list[Question] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            continue
        text_value = as_str(entry.get("text"))
        if not text_value:
            continue
        identifier = as_str(entry.get("id")) or f"q{index + 1}"
        identifier = identifier.strip().lower().replace(" ", "_")
        if identifier in seen:
            identifier = f"{identifier}_{index + 1}"
        seen.add(identifier)
        options = tuple(as_str(option) for option in as_list(entry.get("options")) if as_str(option))
        kind = as_str(entry.get("kind")).lower()
        if kind not in ("free", "choice"):
            kind = "choice" if options else "free"
        questions.append(
            Question(
                id=identifier,
                text=text_value,
                why=as_str(entry.get("why")),
                kind=kind,
                options=options,
            )
        )
        if len(questions) >= limit:
            break
    return tuple(questions)


def _options(translator: Translator, key: str) -> tuple[str, ...]:
    raw = translator.get(f"question.{key}.options", default="")
    if not raw or raw == f"question.{key}.options":
        return ()
    return tuple(part.strip() for part in raw.split("|") if part.strip())


def heuristic(
    prompt: str,
    analysis: Analysis,
    translator: Translator,
    limit: int = 6,
) -> tuple[Question, ...]:
    """Derive questions from the analysis gaps, deterministically."""
    ordered = sorted(
        analysis.issues,
        key=lambda issue: _SEVERITY_ORDER.get(issue.severity, 1),
    )
    questions: list[Question] = []
    seen: set[str] = set()
    for issue in ordered:
        key = _CATEGORY_TO_QUESTION.get(issue.category)
        if key is None or key in seen:
            continue
        seen.add(key)
        options = _options(translator, key)
        questions.append(
            Question(
                id=key,
                text=translator(f"question.{key}.text"),
                why=translator(f"question.{key}.why"),
                kind="choice" if options else "free",
                options=options,
            )
        )
        if len(questions) >= limit:
            break
    return tuple(questions)


def missing_question_keys(analysis: Analysis) -> tuple[str, ...]:
    """Catalog keys of the questions the heuristic path would ask for ``analysis``."""
    ordered = sorted(analysis.issues, key=lambda issue: _SEVERITY_ORDER.get(issue.severity, 1))
    keys: list[str] = []
    for issue in ordered:
        key = _CATEGORY_TO_QUESTION.get(issue.category)
        if key and key not in keys:
            keys.append(key)
    return tuple(keys)
