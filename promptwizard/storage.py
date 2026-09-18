from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Iterator, Mapping
from promptwizard.config import Config
from promptwizard.errors import StorageError
__all__ = ['SESSION_FILENAME', 'get_session', 'iter_sessions', 'list_sessions', 'save_session', 'sessions_file']
SESSION_FILENAME = 'sessions.jsonl'

def sessions_file(config: Config) -> Path:
    return config.sessions_dir / SESSION_FILENAME

def save_session(config: Config, record: Mapping[str, Any]) -> Path:
    path = sessions_file(config)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
    except OSError as exc:
        raise StorageError(f'cannot write the session log at {path}: {exc}', hint_key='error.storage.write') from exc
    return path

def iter_sessions(config: Config) -> Iterator[dict[str, Any]]:
    path = sessions_file(config)
    if not path.exists():
        return
    try:
        raw = path.read_text(encoding='utf-8')
    except OSError as exc:
        raise StorageError(f'cannot read the session log at {path}: {exc}', hint_key='error.storage.read') from exc
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            yield parsed

def list_sessions(config: Config, limit: int | None=None) -> list[dict[str, Any]]:
    records = list(iter_sessions(config))
    records.reverse()
    if limit is not None and limit >= 0:
        records = records[:limit]
    return records

def get_session(config: Config, session_id: str) -> dict[str, Any] | None:
    target = (session_id or '').strip()
    if not target:
        return None
    matches = [record for record in iter_sessions(config) if str(record.get('id', '')) == target]
    if not matches:
        matches = [record for record in iter_sessions(config) if str(record.get('id', '')).startswith(target)]
    return matches[-1] if matches else None
