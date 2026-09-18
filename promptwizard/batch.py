from __future__ import annotations
import re
from typing import Iterable, Sequence
from promptwizard.config import Config
from promptwizard.i18n import Translator
from promptwizard.pipeline import SessionResult, run
__all__ = ['BATCH_LIMIT', 'SPLITTER', 'run_batch', 'split_prompts']
BATCH_LIMIT = 20
SPLITTER = re.compile('\\n\\s*\\n|^\\s*-{3,}\\s*$', re.MULTILINE)

def split_prompts(raw: str) -> list[str]:
    return [part.strip() for part in SPLITTER.split(str(raw or '')) if part.strip()]

def clean_prompts(items: Iterable[str], *, limit: int = BATCH_LIMIT) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        text = str(item or '').strip()
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= max(1, int(limit)):
            break
    return cleaned

def run_batch(config: Config, translator: Translator, prompts: Sequence[str], *, limit: int = BATCH_LIMIT) -> list[SessionResult]:
    return [run(config, translator, prompt) for prompt in clean_prompts(prompts, limit=limit)]
