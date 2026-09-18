from __future__ import annotations
import json
import re
from typing import Any
__all__ = ['extract_json', 'as_str', 'as_list', 'as_int']
_FENCE_RE = re.compile('```(?:json)?\\s*(.*?)```', re.DOTALL)

def extract_json(text: str) -> Any | None:
    if not text or not text.strip():
        return None
    stripped = text.strip()
    direct = _try_loads(stripped)
    if direct is not None:
        return direct
    for match in _FENCE_RE.finditer(text):
        candidate = _try_loads(match.group(1).strip())
        if candidate is not None:
            return candidate
    return _scan_braced(text, '{', '}') or _scan_braced(text, '[', ']')

def _try_loads(raw: str) -> Any | None:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None

def _scan_braced(text: str, opener: str, closer: str) -> Any | None:
    start = text.find(opener)
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    parsed = _try_loads(text[start:index + 1])
                    if parsed is not None:
                        return parsed
                    break
        start = text.find(opener, start + 1)
    return None

def as_str(value: Any, default: str='') -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return default

def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]

def as_int(value: Any, default: int=0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        match = re.search('-?\\d+', value)
        if match:
            return int(match.group(0))
    return default
