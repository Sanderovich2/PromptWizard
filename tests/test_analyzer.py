from __future__ import annotations
import pytest
from promptwizard.analyzer import CATEGORIES, heuristic, normalize_category, normalize_severity, parse
from promptwizard.errors import LLMResponseError

def test_parse_reads_the_expected_shape():
    text = '{"language":"en","score":30,"summary":"weak","issues":[{"category":"format","severity":"high","title":"No format","detail":"add one","evidence":"write"}]}'
    analysis = parse(text, 'en')
    assert analysis.score == 30
    assert analysis.summary == 'weak'
    assert analysis.issues[0].category == 'format'
    assert analysis.issues[0].evidence == 'write'

def test_parse_normalizes_and_clamps():
    text = '{"score":"250","issues":[{"category":"nonsense","severity":"critical","title":"t"}]}'
    analysis = parse(text, 'en')
    assert analysis.score == 100
    assert analysis.issues[0].category == 'clarity'
    assert analysis.issues[0].severity == 'medium'

def test_parse_rejects_prose():
    with pytest.raises(LLMResponseError):
        parse('I could not analyze this.', 'en')

def test_normalizers():
    assert normalize_category('Missing-Detail') == 'missing_detail'
    assert normalize_category('bogus') == 'clarity'
    assert normalize_severity('HIGH') == 'high'
    assert normalize_severity('critical') == 'medium'

def test_heuristic_flags_a_weak_prompt(translator):
    analysis = heuristic('Write something about cats', 'en', translator)
    categories = {issue.category for issue in analysis.issues}
    assert {'missing_detail', 'ambiguity', 'format'} <= categories
    assert analysis.score < 50
    assert all((issue.category in CATEGORIES for issue in analysis.issues))
    assert analysis.language == 'en'

def test_heuristic_accepts_a_specific_prompt(translator):
    prompt = 'Summarize the attached report as a bullet list of at most 200 words for a client.\nUse a formal tone. Do not use jargon. Example: see the sample annex.'
    analysis = heuristic(prompt, 'en', translator)
    categories = {issue.category for issue in analysis.issues}
    assert 'format' not in categories
    assert 'audience' not in categories
    assert len(analysis.issues) <= 2
    assert analysis.score > 60

def test_heuristic_is_deterministic(translator):
    first = heuristic('Do the thing', 'en', translator)
    second = heuristic('Do the thing', 'en', translator)
    assert first == second
