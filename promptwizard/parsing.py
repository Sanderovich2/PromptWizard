"""Lenient JSON extraction from model answers.

Free-tier models wrap JSON in prose or code fences, add a friendly sentence
before it, or emit the object inside a larger text.  The contract is: parse what
is parseable, and treat a missing object as "no answer" so the caller can fall
back to the deterministic path instead of showing the user a raw traceback.
"""

from __future__ import annotations

import json
import re
from typing import Any

__all__ = ["extract_json", "as_str", "as_list", "as_int"]

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> Any | None:
    """Return the first JSON value found in ``text``, or ``None``.

    Tries, in order: whole-text parse, fenced blocks, the first balanced object,
    the first balanced array.
    """
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
    return _scan_braced(text, "{", "}") or _scan_braced(text, "[", "]")


def _try_loads(raw: str) -> Any | None:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None


def _scan_braced(text: str, opener: str, closer: str) -> Any | None:
    """Find the first balanced ``opener..closer`` span that parses as JSON."""
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
                elif char == "\\":
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
                    parsed = _try_loads(text[start : index + 1])
                    if parsed is not None:
                        return parsed
                    break
        start = text.find(opener, start + 1)
    return None


def as_str(value: Any, default: str = "") -> str:
    """Coerce a JSON value into a stripped string."""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return default


def as_list(value: Any) -> list[Any]:
    """Coerce a JSON value into a list (single values become a one-item list)."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def as_int(value: Any, default: int = 0) -> int:
    """Coerce a JSON value into an int, tolerating ``"72"`` and ``"72/100"``."""
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+", value)
        if match:
            return int(match.group(0))
    return default
