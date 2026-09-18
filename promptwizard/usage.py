from __future__ import annotations
__all__ = ['CHARS_PER_TOKEN', 'estimate_tokens']
CHARS_PER_TOKEN = 4

def estimate_tokens(text: str) -> int:
    value = text or ''
    if not value.strip():
        return 0
    return max(1, (len(value) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)
