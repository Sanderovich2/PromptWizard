"""Rewrite the prompt and explain what changed.

Output language rule (see :mod:`promptwizard.i18n`): the rewritten prompt is
written in the **language of the original prompt**, because it is material the
user will feed to a model; the "what changed" explanations are written in the
**UI language**.

The deterministic path assembles a structured prompt from labelled sections,
filling each section from the user's answers and marking the rest as
"(not specified)" so the remaining gaps stay visible instead of silently
plausible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from promptwizard.analyzer import Analysis
from promptwizard.errors import LLMResponseError
from promptwizard.i18n import Translator
from promptwizard.parsing import as_list, as_str, extract_json

__all__ = [
    "Rewrite",
    "build_system_prompt",
    "build_user_prompt",
    "heuristic",
    "parse",
]

#: Question id -> scaffold section it fills.  ``length`` folds into the output
#: format section because that is where a reader looks for it.
_QUESTION_TO_SECTION: dict[str, str] = {
    "context": "context",
    "audience": "audience",
    "constraints": "constraints",
    "format": "format",
    "length": "format",
    "examples": "examples",
    "tone": "tone",
}

#: Sections of the deterministic scaffold, in the order they are written.
_SCAFFOLD_SECTIONS: tuple[str, ...] = ("context", "audience", "constraints", "format", "examples", "tone")


@dataclass(frozen=True)
class Rewrite:
    """The improved prompt plus a short change log.

    Attributes:
        improved_prompt: The rewritten prompt, in the original prompt's language.
        changes: Human-readable "what changed and why" lines (UI language).
        language: Language the improved prompt is written in.
        raw: Raw model answer, kept for the session log.
    """

    improved_prompt: str
    changes: tuple[str, ...]
    language: str
    raw: str = ""


def build_system_prompt(translator: Translator, prompt_language: str) -> str:
    """System instruction: rewrite the prompt, explain the edits separately."""
    schema = (
        '{"improved_prompt":"<the rewritten prompt>",'
        '"changes":[{"what":"<what changed>","why":"<why>"}],'
        '"language":"ru|en|other"}'
    )
    target = translator.get(f"language.{prompt_language}", default=translator("language.unknown"))
    return (
        "You are PromptWizard, a prompt engineer. Rewrite the user's prompt so a model "
        "understands it better, and answer with STRICT JSON only:\n"
        + schema
        + "\nRules:\n"
        f"- Write \"improved_prompt\" in {target}: the same language as the original prompt.\n"
        f'- Write every "what" and "why" in {translator("language." + translator.lang)}.\n'
        "- Keep the original intent and constraints. Do not add requirements the user did not "
        "imply; make the implicit explicit instead.\n"
        "- Structure the result: role or task, context, constraints, expected output format, "
        "and audience or examples when they matter.\n"
        "- List the concrete changes you made, one entry each, most important first.\n"
        "- Return only the improved prompt in \"improved_prompt\": no commentary, no markdown fence."
    )


def build_user_prompt(
    prompt: str,
    analysis: Analysis,
    questions: Sequence[object] = (),
    answers: Mapping[str, str] | None = None,
) -> str:
    """User turn: original prompt, weaknesses, and the user's answers."""
    lines = ["Original prompt:", prompt.strip(), "", "Known weaknesses:"]
    if analysis.issues:
        for issue in analysis.issues:
            lines.append(f"- [{issue.severity}] {issue.category}: {issue.title}")
    else:
        lines.append("- (none reported)")
    if questions:
        lines.extend(["", "Clarifications from the user:"])
        for question in questions:
            identifier = getattr(question, "id", "")
            text_value = getattr(question, "text", "")
            answer = (answers or {}).get(identifier, "").strip()
            lines.append(f"- Q: {text_value}")
            lines.append(f"  A: {answer or '(not answered)'}")
    return "\n".join(lines)


def parse(text: str, language: str = "unknown") -> Rewrite:
    """Parse the model answer into a :class:`Rewrite`.

    Raises:
        LLMResponseError: The answer contained no usable JSON or no prompt.
    """
    data = extract_json(text)
    if not isinstance(data, Mapping):
        raise LLMResponseError(
            "rewriter: the model did not return a JSON object",
            hint_key="error.provider.bad_response",
            hint_kwargs={"provider": "api"},
        )
    improved = as_str(data.get("improved_prompt")) or as_str(data.get("prompt"))
    if not improved:
        raise LLMResponseError(
            "rewriter: the model returned no improved prompt",
            hint_key="error.provider.bad_response",
            hint_kwargs={"provider": "api"},
        )
    changes: list[str] = []
    for entry in as_list(data.get("changes")):
        if isinstance(entry, Mapping):
            what = as_str(entry.get("what"))
            why = as_str(entry.get("why"))
            if what and why:
                changes.append(f"{what} — {why}")
            elif what or why:
                changes.append(what or why)
        else:
            value = as_str(entry)
            if value:
                changes.append(value)
    detected = as_str(data.get("language")).lower()
    if detected not in ("ru", "en"):
        detected = language
    return Rewrite(improved_prompt=improved, changes=tuple(changes), language=detected, raw=text)


def heuristic(
    prompt: str,
    analysis: Analysis,
    answers: Mapping[str, str] | None,
    prompt_translator: Translator,
    ui_translator: Translator,
) -> Rewrite:
    """Assemble a structured prompt with no model call.

    Args:
        prompt: The original prompt.
        analysis: Its analysis (the gap list drives which sections are shown).
        answers: Answers keyed by question id (see :mod:`promptwizard.questions`).
        prompt_translator: Translator for the **prompt** language (section labels).
        ui_translator: Translator for the **UI** language ("what changed" lines).
    """
    translator = prompt_translator
    answers = {key: (value or "").strip() for key, value in (answers or {}).items()}
    gaps = {issue.category for issue in analysis.issues}

    section_values: dict[str, list[str]] = {section: [] for section in _SCAFFOLD_SECTIONS}
    for question_id, answer in answers.items():
        if not answer:
            continue
        section = _QUESTION_TO_SECTION.get(question_id)
        if section and section in section_values:
            section_values[section].append(answer)
        else:
            section_values["context"].append(answer)

    blocks = [f"{translator('scaffold.task')}:\n{prompt.strip()}"]
    used_sections: list[str] = []
    for section in _SCAFFOLD_SECTIONS:
        values = section_values[section]
        gap = section in gaps or (section == "format" and ("format" in gaps or "missing_detail" in gaps))
        if not values and not gap:
            continue
        body = "\n".join(values) if values else translator("scaffold.none")
        blocks.append(f"{translator('scaffold.' + section)}:\n{body}")
        used_sections.append(section)

    improved_prompt = "\n\n".join(blocks)

    changes: list[str] = []
    for category in _ordered_categories(analysis):
        changes.append(ui_translator(f"change.{category}"))
    if any(answers.values()):
        changes.append(ui_translator("change.answers"))
    if not changes:
        changes.append(ui_translator("change.none"))
    return Rewrite(
        improved_prompt=improved_prompt,
        changes=tuple(changes),
        language=analysis.language,
        raw="",
    )


def _ordered_categories(analysis: Analysis) -> list[str]:
    """Categories to report, most severe first, each once."""
    order = {"high": 0, "medium": 1, "low": 2}
    seen: list[str] = []
    for issue in sorted(analysis.issues, key=lambda item: order.get(item.severity, 1)):
        if issue.category not in seen:
            seen.append(issue.category)
    return seen
