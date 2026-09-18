from __future__ import annotations
import json
from pathlib import Path
from promptwizard.config import Config
from promptwizard.errors import StorageError
__all__ = ['DRAFT_LIMIT', 'add_draft', 'clear_drafts', 'drafts_file', 'list_drafts', 'remove_draft']
DRAFT_LIMIT = 20

def drafts_file(config: Config) -> Path:
    return config.home / 'drafts.json'

def list_drafts(config: Config) -> list[str]:
    path = drafts_file(config)
    try:
        raw = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise StorageError(f'cannot read the drafts at {path}: {exc}', hint_key='error.storage.read') from exc
    try:
        data = json.loads(raw or '[]')
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if str(item).strip()]

def _write(config: Config, items: list[str]) -> Path:
    path = drafts_file(config)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except OSError as exc:
        raise StorageError(f'cannot write the drafts at {path}: {exc}', hint_key='error.storage.write') from exc
    return path

def add_draft(config: Config, prompt: str, *, limit: int = DRAFT_LIMIT) -> list[str]:
    text = (prompt or '').strip()
    if not text:
        return list_drafts(config)
    items = [item for item in list_drafts(config) if item != text]
    items.insert(0, text)
    items = items[:max(1, int(limit))]
    _write(config, items)
    return items

def remove_draft(config: Config, prompt: str) -> list[str]:
    text = (prompt or '').strip()
    items = [item for item in list_drafts(config) if item != text]
    _write(config, items)
    return items

def clear_drafts(config: Config) -> list[str]:
    _write(config, [])
    return []
