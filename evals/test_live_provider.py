from __future__ import annotations
import os
import pytest
from promptwizard.config import Config
from promptwizard.i18n import get_translator
from promptwizard.llm.registry import build_provider
from promptwizard.pipeline import run
pytestmark = pytest.mark.eval
ROUGH_PROMPT = 'write about our product'
MIN_GROWTH = 1.5

def test_rewrite_is_longer_and_structured(tmp_path):
    if os.environ.get('PROMPTWIZARD_EVAL') != '1':
        pytest.skip('set PROMPTWIZARD_EVAL=1 to run the live eval')
    config = Config.load(home=tmp_path, dotenv=True)
    provider = build_provider(config)
    if not provider.available():
        pytest.skip(f'provider {config.provider} is not reachable right now')
    translator = get_translator(config.lang)
    result = run(config, translator, ROUGH_PROMPT, provider=provider, no_questions=True)
    assert result.rewrite is not None
    improved = result.rewrite.improved_prompt.strip()
    assert improved, 'the provider returned an empty rewrite'
    assert len(improved) >= MIN_GROWTH * len(ROUGH_PROMPT), 'the rewrite did not get more specific'
    assert result.analysis.issues, 'a deliberately vague prompt must produce at least one issue'
    assert result.mode == 'llm', f'the run degraded to {result.mode}: {result.warnings}'
