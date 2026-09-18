"""Prompt analysis: find structure, clarity, ambiguity and missing-detail issues.

Two producers share one result type:

* :func:`parse` reads the JSON an LLM returns for :func:`build_system_prompt`.
* :func:`heuristic` is the deterministic fallback (and the ``offline`` mode):
  it flags the same categories using rules, so the tool still says something
  useful with no model configured.

The deterministic half is what makes this testable without network: a test fixes
a prompt and asserts the exact set of categories the rules must emit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from promptwizard.errors import LLMResponseError
from promptwizard.i18n import Translator
from promptwizard.parsing import as_int, as_list, as_str, extract_json

__all__ = [
    "CATEGORIES",
    "SEVERITIES",
    "Analysis",
    "Issue",
    "build_system_prompt",
    "build_user_prompt",
    "heuristic",
    "normalize_category",
    "normalize_severity",
    "parse",
]

CATEGORIES: tuple[str, ...] = (
    "clarity",
    "structure",
    "ambiguity",
    "missing_detail",
    "weak_phrasing",
    "constraints",
    "format",
    "audience",
    "examples",
    "scope",
    "tone",
    "context",
)
SEVERITIES: tuple[str, ...] = ("high", "medium", "low")

MAX_ISSUES = 8


@dataclass(frozen=True)
class Issue:
    """One weakness found in the prompt.

    Attributes:
        category: One of :data:`CATEGORIES`; drives the localized label.
        severity: ``high`` / ``medium`` / ``low``.
        title: Short, already localized headline.
        detail: Why it matters and how to fix it (localized).
        evidence: Optional quote from the prompt.
    """

    category: str
    severity: str
    title: str
    detail: str = ""
    evidence: str = ""


@dataclass(frozen=True)
class Analysis:
    """The structured verdict for one prompt."""

    language: str
    score: int
    summary: str
    issues: tuple[Issue, ...] = ()
    raw: str = ""


def normalize_category(value: Any) -> str:
    """Map a model-supplied category onto a known one (defaults to ``clarity``)."""
    token = as_str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return token if token in CATEGORIES else "clarity"


def normalize_severity(value: Any) -> str:
    """Map a model-supplied severity onto ``high``/``medium``/``low``."""
    token = as_str(value).strip().lower()
    return token if token in SEVERITIES else "medium"


def build_system_prompt(translator: Translator) -> str:
    """System instruction asking the model for strict JSON in the UI language."""
    schema = (
        "{"
        '"language":"ru|en|other",'
        '"score":<integer 0-100, how well the prompt is specified>,'
        '"summary":"<one or two sentences>",'
        '"issues":[{"category":"' + "|".join(CATEGORIES) + '",'
        '"severity":"high|medium|low",'
        '"title":"<short headline>",'
        '"detail":"<why it matters and how to fix it>",'
        '"evidence":"<quote from the prompt, or empty>"}]'
        "}"
    )
    return (
        "You are PromptWizard, a prompt engineer. Analyze the user's prompt and answer with "
        "STRICT JSON only: no prose, no markdown fence, exactly this shape:\n"
        + schema
        + "\nRules:\n"
        f"- Return at most {MAX_ISSUES} issues, most important first.\n"
        "- Judge how the prompt is specified (clarity, structure, ambiguity, missing detail, "
        "constraints, format, audience, examples, scope, tone, context), never the topic itself.\n"
        "- Do not invent problems: an already strong prompt may return an empty issues list.\n"
        f'- Write "summary", "title" and "detail" in {translator("language." + translator.lang)}.\n'
        '- Set "language" to the language of the analyzed prompt.'
    )


def build_user_prompt(prompt: str) -> str:
    """The user turn: the raw prompt to analyze, clearly delimited."""
    return "Analyze this prompt:\n<PROMPT>\n" + prompt + "\n</PROMPT>"


def parse(text: str, language: str = "unknown") -> Analysis:
    """Parse a model answer into an :class:`Analysis`.

    Raises:
        LLMResponseError: The answer contained no usable JSON object.
    """
    data = extract_json(text)
    if not isinstance(data, Mapping):
        raise LLMResponseError(
            "analyzer: the model did not return a JSON object",
            hint_key="error.provider.bad_response",
            hint_kwargs={"provider": "api"},
        )
    issues: list[Issue] = []
    for entry in as_list(data.get("issues"))[:MAX_ISSUES]:
        if not isinstance(entry, Mapping):
            continue
        title = as_str(entry.get("title"))
        detail = as_str(entry.get("detail"))
        if not title and not detail:
            continue
        issues.append(
            Issue(
                category=normalize_category(entry.get("category")),
                severity=normalize_severity(entry.get("severity")),
                title=title or detail[:80],
                detail=detail,
                evidence=as_str(entry.get("evidence")),
            )
        )
    detected = as_str(data.get("language")).lower()
    if detected not in ("ru", "en"):
        detected = language
    score = max(0, min(100, as_int(data.get("score"), default=50)))
    summary = as_str(data.get("summary"))
    return Analysis(
        language=detected,
        score=score,
        summary=summary,
        issues=tuple(issues),
        raw=text,
    )


# --------------------------------------------------------------------- rules
_VAGUE = (
    "something", "somehow", "some", "etc", "and so on", "stuff", "things",
    "что-то", "как-то", "кое-что", "что нибудь", "и т.д", "и т.п", "всякое",
)
_FORMAT_WORDS = (
    "format", "bullet", "list", "table", "json", "markdown", "paragraph",
    "words", "chars", "headline", "summary", "формат", "список", "таблиц",
    "json", "раздел", "пункт", "абзац", "слов", "символ", "заголовок",
)
_AUDIENCE_WORDS = (
    "audience", "reader", "customer", "client", "beginner", "expert", "user",
    "company", "team", "для кого", "аудитор", "читател", "клиент", "нович", "эксперт",
)
_CONSTRAINT_WORDS = (
    "must", "only", "avoid", "do not", "don't", "no more than", "at least", "limit",
    "не ", "только", "избег", "без ", "не более", "не менее", "максимум", "минимум", "обязательно",
)
_EXAMPLE_WORDS = ("example", "for instance", "e.g", "например", "пример")
_CONTEXT_WORDS = (
    "context", "background", "project", "goal", "purpose", "because",
    "контекст", "фон", "проект", "цель", "зачем", "потому что",
)
_TONE_WORDS = (
    "tone", "formal", "friendly", "casual", "professional", "style",
    "тон", "формальн", "дружелюб", "официальн", "стил",
)


def _contains(text: str, needles: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _issue(translator: Translator, category: str, severity: str, evidence: str = "") -> Issue:
    return Issue(
        category=category,
        severity=severity,
        title=translator(f"issue.{category}.title"),
        detail=translator(f"issue.{category}.detail"),
        evidence=evidence,
    )


def heuristic(prompt: str, language: str, translator: Translator) -> Analysis:
    """Deterministic analysis used by the offline mode and as a fallback.

    Rules are intentionally simple and stable so tests can assert them.  Each
    fired rule costs points; the score is a rough readability signal, not a
    benchmark.
    """
    text = prompt.strip()
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    issues: list[Issue] = []
    penalty = 0

    if len(words) < 12:
        issues.append(_issue(translator, "missing_detail", "high"))
        penalty += 30
    if len(text) > 400 and "\n" not in text:
        issues.append(_issue(translator, "structure", "medium"))
        penalty += 12
    if _contains(text, _VAGUE):
        issues.append(_issue(translator, "ambiguity", "high"))
        penalty += 20
    if not _contains(text, _FORMAT_WORDS):
        issues.append(_issue(translator, "format", "high"))
        penalty += 18
    if not _contains(text, _AUDIENCE_WORDS):
        issues.append(_issue(translator, "audience", "medium"))
        penalty += 10
    if not _contains(text, _CONSTRAINT_WORDS):
        issues.append(_issue(translator, "constraints", "medium"))
        penalty += 10
    if not _contains(text, _EXAMPLE_WORDS):
        issues.append(_issue(translator, "examples", "low"))
        penalty += 5
    if not _contains(text, _CONTEXT_WORDS):
        issues.append(_issue(translator, "context", "medium"))
        penalty += 8
    if not _contains(text, _TONE_WORDS):
        issues.append(_issue(translator, "tone", "low"))
        penalty += 5

    score = max(10, min(100, 100 - penalty))
    if issues:
        summary = translator("analysis.summary_issues", count=len(issues))
    else:
        summary = translator("analysis.summary_ok")
    return Analysis(language=language, score=score, summary=summary, issues=tuple(issues))
