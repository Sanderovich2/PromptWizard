from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from promptwizard.errors import StorageError
from promptwizard.i18n import Translator
from promptwizard.pipeline import SessionResult
from promptwizard.rewriter import Rewrite
__all__ = ['FORMATS', 'render', 'to_json', 'to_markdown', 'to_text', 'write_output']
FORMATS: tuple[str, ...] = ('md', 'txt', 'json')

def _rewrite(result: SessionResult) -> Rewrite | None:
    return result.rewrite

def to_markdown(result: SessionResult, translator: Translator) -> str:
    rewrite = _rewrite(result)
    lines: list[str] = [f"# {translator('app.name')}", '']
    lines.append(translator('run.summary', provider=result.provider, model=result.model, language=result.prompt_language))
    lines.append('')
    lines.append(translator('run.mode_label', mode=translator(f'run.mode.{result.mode}')))
    lines.append('')
    lines.append(f"## {translator('run.original_header')}")
    lines.append('')
    lines.append('```text')
    lines.append(result.original_prompt.strip())
    lines.append('```')
    lines.append('')
    lines.append(f"## {translator('run.issues_header')}")
    lines.append('')
    lines.append(translator('run.score', score=result.analysis.score))
    lines.append('')
    if result.analysis.issues:
        for index, issue in enumerate(result.analysis.issues, start=1):
            lines.append(translator('run.issue_item', index=index, severity=translator(f'severity.{issue.severity}'), category=translator(f'category.{issue.category}'), title=issue.title))
            if issue.detail:
                lines.append(translator('run.issue_detail', detail=issue.detail))
    else:
        lines.append(translator('run.no_issues'))
    lines.append('')
    if result.questions:
        lines.append(f"## {translator('run.questions_header')}")
        lines.append('')
        for index, question in enumerate(result.questions, start=1):
            lines.append(translator('run.question_item', index=index, text=question.text))
            answer = result.answers.get(question.id, '').strip()
            if answer:
                lines.append(f'   > {answer}')
        lines.append('')
    if rewrite is not None:
        lines.append(f"## {translator('run.improved_header')}")
        lines.append('')
        lines.append(rewrite.improved_prompt.strip())
        lines.append('')
        if rewrite.changes:
            lines.append(f"## {translator('run.changes_header')}")
            lines.append('')
            for change in rewrite.changes:
                lines.append(translator('run.change_item', change=change))
            lines.append('')
    if result.warnings:
        lines.append('## Warnings')
        lines.append('')
        for warning in result.warnings:
            lines.append(f'- {warning}')
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'

def to_text(result: SessionResult, translator: Translator) -> str:
    rewrite = _rewrite(result)
    bar = '=' * 60
    parts: list[str] = [bar, translator('app.name'), bar, '']
    parts.append(translator('run.summary', provider=result.provider, model=result.model, language=result.prompt_language))
    parts.append(translator('run.mode_label', mode=translator(f'run.mode.{result.mode}')))
    parts.append('')
    parts.append(translator('run.original_header').upper())
    parts.append(result.original_prompt.strip())
    parts.append('')
    parts.append(translator('run.issues_header').upper())
    parts.append(translator('run.score', score=result.analysis.score))
    if result.analysis.issues:
        for index, issue in enumerate(result.analysis.issues, start=1):
            parts.append(translator('run.issue_item', index=index, severity=translator(f'severity.{issue.severity}'), category=translator(f'category.{issue.category}'), title=issue.title))
            if issue.detail:
                parts.append(translator('run.issue_detail', detail=issue.detail))
    else:
        parts.append(translator('run.no_issues'))
    parts.append('')
    if result.questions:
        parts.append(translator('run.questions_header').upper())
        for index, question in enumerate(result.questions, start=1):
            parts.append(translator('run.question_item', index=index, text=question.text))
            answer = result.answers.get(question.id, '').strip()
            if answer:
                parts.append(f'   > {answer}')
        parts.append('')
    if rewrite is not None:
        parts.append(translator('run.improved_header').upper())
        parts.append(rewrite.improved_prompt.strip())
        parts.append('')
        if rewrite.changes:
            parts.append(translator('run.changes_header').upper())
            for change in rewrite.changes:
                parts.append(translator('run.change_item', change=change))
            parts.append('')
    if result.warnings:
        parts.append('WARNINGS')
        for warning in result.warnings:
            parts.append(f'- {warning}')
        parts.append('')
    return '\n'.join(parts).rstrip() + '\n'

def to_json(result: SessionResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + '\n'

def render(result: SessionResult, fmt: str, translator: Translator) -> str:
    normalized = (fmt or 'md').strip().lower()
    if normalized in ('md', 'markdown'):
        return to_markdown(result, translator)
    if normalized in ('txt', 'text', 'plain'):
        return to_text(result, translator)
    if normalized == 'json':
        return to_json(result)
    raise StorageError(f"unknown export format: {fmt!r} (expected one of {', '.join(FORMATS)})")

def write_output(text: str, path: str | Path) -> Path:
    target = Path(path).expanduser()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
    except OSError as exc:
        raise StorageError(f'cannot write the result to {target}: {exc}') from exc
    return target

def session_to_markdown(record: dict[str, Any], translator: Translator) -> str:
    return to_markdown(SessionResult.from_dict(record), translator)
