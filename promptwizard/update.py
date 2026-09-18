from __future__ import annotations
import json
import urllib.request
from typing import Any
from promptwizard import __version__
__all__ = ['RELEASES_URL', 'check_for_update', 'compare_versions', 'parse_version']
RELEASES_URL = 'https://api.github.com/repos/Sanderovich2/PromptWizard/releases/latest'

def parse_version(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in str(value or '').strip().lstrip('vV').split('.'):
        digits = ''
        for char in chunk:
            if not char.isdigit():
                break
            digits += char
        parts.append(int(digits) if digits else 0)
    return tuple(parts)

def compare_versions(current: str, latest: str) -> int:
    left = list(parse_version(current))
    right = list(parse_version(latest))
    size = max(len(left), len(right))
    left += [0] * (size - len(left))
    right += [0] * (size - len(right))
    if left == right:
        return 0
    return 1 if left > right else -1

def check_for_update(current: str=__version__, *, url: str=RELEASES_URL, timeout: float=8.0) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': f'PromptWizard/{current}'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode('utf-8'))
    if not isinstance(data, dict):
        raise ValueError('the release feed is not a JSON object')
    tag = str(data.get('tag_name') or '')
    return {'current': current, 'latest': tag.lstrip('vV'), 'url': str(data.get('html_url') or ''), 'newer': compare_versions(current, tag) < 0}
