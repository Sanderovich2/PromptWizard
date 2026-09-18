from __future__ import annotations
from promptwizard.analyzer import Analysis, Issue
from promptwizard.errors import LLMResponseError
from promptwizard.questions import heuristic, parse

def test_parse_limits_and_dedupes_ids():
    text = '{"questions":[{"id":"a","text":"Q1"},{"id":"a","text":"Q2"},{"text":"Q3"}]}'
    questions = parse(text, limit=5)
    assert [question.id for question in questions] == ['a', 'a_2', 'q3']

def test_parse_honours_the_limit():
    text = '{"questions":[{"id":"a","text":"Q1"},{"id":"b","text":"Q2"}]}'
    assert len(parse(text, limit=1)) == 1

def test_parse_accepts_a_bare_array():
    assert parse('[{"id":"a","text":"Q"}]', limit=3)[0].id == 'a'

def test_parse_rejects_prose():
    import pytest
    with pytest.raises(LLMResponseError):
        parse('Ask me later.', limit=3)

def test_parse_derives_choice_kind_from_options():
    questions = parse('{"questions":[{"id":"a","text":"Q","options":["x","y"]}]}', limit=3)
    assert questions[0].kind == 'choice'
    assert questions[0].options == ('x', 'y')

def test_heuristic_maps_gaps_to_questions(translator):
    analysis = Analysis(language='en', score=10, summary='', issues=(Issue('format', 'high', 't'), Issue('audience', 'medium', 't')))
    questions = heuristic('x', analysis, translator, limit=6)
    assert [question.id for question in questions] == ['format', 'audience']
    assert questions[0].options
    assert questions[0].text

def test_heuristic_collapses_several_gaps_onto_one_question(translator):
    analysis = Analysis(language='en', score=10, summary='', issues=(Issue('missing_detail', 'high', 't'), Issue('scope', 'high', 't')))
    questions = heuristic('x', analysis, translator, limit=6)
    assert [question.id for question in questions] == ['length']
