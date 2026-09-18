from __future__ import annotations
import pytest
from promptwizard.analyzer import Analysis, Issue
from promptwizard.errors import LLMResponseError
from promptwizard.rewriter import heuristic, parse

def test_parse_reads_changes_and_joins_what_and_why():
    text = '{"improved_prompt":"Task: x","language":"en","changes":[{"what":"Added format","why":"clearer"},{"what":"Trimmed"}]}'
    rewrite = parse(text, 'en')
    assert rewrite.improved_prompt == 'Task: x'
    assert rewrite.changes[0] == 'Added format — clearer'
    assert rewrite.changes[1] == 'Trimmed'
    assert rewrite.language == 'en'

def test_parse_accepts_the_prompt_alias():
    assert parse('{"prompt":"Task: y"}', 'en').improved_prompt == 'Task: y'

def test_parse_requires_a_prompt():
    with pytest.raises(LLMResponseError):
        parse('{"changes":[]}', 'en')

def test_parse_rejects_prose():
    with pytest.raises(LLMResponseError):
        parse('Here is your prompt: do the thing', 'en')

def _analysis() -> Analysis:
    return Analysis(language='en', score=40, summary='', issues=(Issue('format', 'high', 't'), Issue('audience', 'medium', 't')))

def test_heuristic_builds_a_scaffold_and_folds_in_answers(translator):
    rewrite = heuristic('Do the thing', _analysis(), {'format': 'a table', 'audience': 'engineers'}, translator, translator)
    assert 'Do the thing' in rewrite.improved_prompt
    assert 'a table' in rewrite.improved_prompt
    assert 'engineers' in rewrite.improved_prompt
    assert rewrite.language == 'en'
    assert rewrite.changes

def test_heuristic_marks_missing_sections(translator):
    rewrite = heuristic('Do the thing', _analysis(), {}, translator, translator)
    assert '(not specified)' in rewrite.improved_prompt
    assert 'Do the thing' in rewrite.improved_prompt

def test_heuristic_reports_no_changes_when_there_are_no_gaps(translator):
    clean = Analysis(language='en', score=100, summary='', issues=())
    rewrite = heuristic('Do the thing', clean, {}, translator, translator)
    assert rewrite.changes == (translator('change.none'),)
