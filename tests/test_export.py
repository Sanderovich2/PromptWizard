from __future__ import annotations
import json
import pytest
from promptwizard.analyzer import Analysis, Issue
from promptwizard.errors import StorageError
from promptwizard.export import autosave_result, render, to_markdown, to_text
from promptwizard.pipeline import SessionResult
from promptwizard.rewriter import Rewrite

def _result() -> SessionResult:
    return SessionResult(id='20260101-000000-abcdef', started_at='2026-01-01T00:00:00+03:00', finished_at='2026-01-01T00:00:05+03:00', provider='offline', model='-', mode='offline', prompt_language='en', ui_language='en', original_prompt='Write something', analysis=Analysis(language='en', score=20, summary='weak', issues=(Issue('format', 'high', 'No format', 'add one'),)), questions=(), answers={}, rewrite=Rewrite(improved_prompt='Task:\nWrite something', changes=('Specified the format.',), language='en'), warnings=())

def test_markdown_carries_every_section(translator):
    text = to_markdown(_result(), translator)
    assert 'Write something' in text
    assert 'No format' in text
    assert 'Task:' in text
    assert 'Specified the format.' in text

def test_text_export_is_plain(translator):
    text = to_text(_result(), translator)
    assert 'ORIGINAL PROMPT' in text
    assert 'Write something' in text

def test_json_export_round_trips(translator):
    payload = json.loads(render(_result(), 'json', translator))
    assert payload['id'] == '20260101-000000-abcdef'
    assert payload['rewrite']['improved_prompt'].startswith('Task:')
    assert payload['analysis']['issues'][0]['category'] == 'format'

def test_unknown_format_is_rejected(translator):
    with pytest.raises(StorageError):
        render(_result(), 'docx', translator)

def test_markdown_carries_the_run_stats(translator):
    result = _result()
    result.duration_ms = 2500
    result.tokens_in = 100
    result.tokens_out = 40
    text = to_markdown(result, translator)
    assert '2.5' in text
    assert '140' in text
    assert 'offline' in text

def test_plain_text_carries_the_run_stats(translator):
    result = _result()
    result.duration_ms = 2500
    result.tokens_in = 100
    result.tokens_out = 40
    assert '2.5' in to_text(result, translator)

def test_exports_without_stats_stay_clean(translator):
    assert 'Time:' not in to_markdown(_result(), translator)
    assert 'Time:' not in to_text(_result(), translator)

def test_autosave_writes_a_markdown_file(translator, tmp_path):
    result = _result()
    path = autosave_result(result, translator, tmp_path / 'out')
    assert path is not None
    assert path.name == f'promptwizard-{result.id}.md'
    assert path.parent == tmp_path / 'out'
    body = path.read_text(encoding='utf-8')
    assert 'Task:' in body
    assert 'Write something' in body

def test_the_translation_is_exported(translator):
    result = _result()
    result.translated_prompt = 'Write something concrete'
    markdown = to_markdown(result, translator)
    assert 'Write something concrete' in markdown
    assert to_markdown(_result(), translator).count('Write something concrete') == 0

def test_plain_text_carrying_the_translation(translator):
    result = _result()
    result.translated_prompt = 'Write something concrete'
    text = to_text(result, translator)
    assert 'Write something concrete' in text
    assert 'TRANSLATION USED FOR THE ANALYSIS' in text

def test_autosave_is_off_without_a_folder(translator):
    assert autosave_result(_result(), translator, '') is None
    assert autosave_result(_result(), translator, None) is None
