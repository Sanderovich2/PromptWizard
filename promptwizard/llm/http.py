from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Mapping

from promptwizard import __version__
from promptwizard.errors import LLMResponseError, ProviderHTTPError, ProviderTimeout, ProviderUnavailable

__all__ = ['USER_AGENT', 'get_json', 'post_json', 'request_json']

USER_AGENT = f'PromptWizard/{__version__} (+https://github.com/Sanderovich2/PromptWizard)'
_STATUS_HINTS: dict[int, tuple[str, str]] = {
    400: ('error.provider.bad_request', 'bad request'),
    401: ('error.provider.auth', 'authentication failed'),
    403: ('error.provider.auth', 'permission denied'),
    404: ('error.provider.model_not_found', 'model or endpoint not found'),
    408: ('error.provider.timeout', 'request timed out'),
    413: ('error.provider.bad_request', 'request too large'),
    422: ('error.provider.bad_request', 'unprocessable request'),
    429: ('error.provider.rate_limit', 'rate limit / quota exceeded'),
    500: ('error.provider.server', 'provider server error'),
    502: ('error.provider.server', 'provider server error'),
    503: ('error.provider.server', 'provider temporarily unavailable'),
    504: ('error.provider.server', 'provider gateway timeout'),
}

RETRY_STATUSES = frozenset({502, 503, 504})
RETRY_DELAY = 1.5
RETRY_ATTEMPTS = 3


def request_json(
    url: str,
    *,
    method: str='GET',
    payload: Mapping[str, Any] | None=None,
    headers: Mapping[str, str] | None=None,
    timeout: float=60.0,
    provider: str='',
) -> dict[str, Any]:
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return _attempt(url, method=method, payload=payload, headers=headers, timeout=timeout, provider=provider)
        except ProviderHTTPError as exc:
            if exc.status not in RETRY_STATUSES or attempt == RETRY_ATTEMPTS - 1:
                raise
            time.sleep(RETRY_DELAY * (attempt + 1))
    raise AssertionError('unreachable')


def _attempt(
    url: str,
    *,
    method: str='GET',
    payload: Mapping[str, Any] | None=None,
    headers: Mapping[str, str] | None=None,
    timeout: float=60.0,
    provider: str='',
) -> dict[str, Any]:
    body = None
    request_headers = {'Accept': 'application/json', 'User-Agent': USER_AGENT}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        request_headers['Content-Type'] = 'application/json; charset=utf-8'
    if headers:
        request_headers.update({key: value for key, value in headers.items() if value is not None})
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method.upper())
    label = provider or url.split('/')[2] if '//' in url else provider or url
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        try:
            detail = exc.read().decode('utf-8', errors='replace')
        except Exception:
            detail = ''
        hint_key, reason = _STATUS_HINTS.get(status, ('error.provider.http', 'unexpected status'))
        raise ProviderHTTPError(
            f'{label}: HTTP {status} ({reason})',
            status=status,
            body=detail,
            hint_key=hint_key,
            hint_kwargs={'provider': provider or label, 'status': status},
        ) from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, 'reason', exc)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            raise ProviderTimeout(
                f'{label}: no answer within {timeout:g}s',
                hint_key='error.provider.timeout',
                hint_kwargs={'provider': provider or label, 'timeout': timeout},
            ) from exc
        raise ProviderUnavailable(
            f'{label}: cannot reach the provider ({reason})',
            hint_key='error.provider.unreachable',
            hint_kwargs={'provider': provider or label, 'reason': reason},
        ) from exc
    except (socket.timeout, TimeoutError) as exc:
        raise ProviderTimeout(
            f'{label}: no answer within {timeout:g}s',
            hint_key='error.provider.timeout',
            hint_kwargs={'provider': provider or label, 'timeout': timeout},
        ) from exc
    except OSError as exc:
        raise ProviderUnavailable(
            f'{label}: connection failed ({exc})',
            hint_key='error.provider.unreachable',
            hint_kwargs={'provider': provider or label, 'reason': exc},
        ) from exc
    if not raw.strip():
        raise LLMResponseError(
            f'{label}: empty response body',
            hint_key='error.provider.bad_response',
            hint_kwargs={'provider': provider or label},
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMResponseError(
            f'{label}: response is not valid JSON ({exc.msg})',
            hint_key='error.provider.bad_response',
            hint_kwargs={'provider': provider or label},
        ) from exc
    if not isinstance(data, dict):
        raise LLMResponseError(
            f'{label}: expected a JSON object, got {type(data).__name__}',
            hint_key='error.provider.bad_response',
            hint_kwargs={'provider': provider or label},
        )
    return data


def post_json(
    url: str,
    payload: Mapping[str, Any],
    *,
    headers: Mapping[str, str] | None=None,
    timeout: float=60.0,
    provider: str='',
) -> dict[str, Any]:
    return request_json(url, method='POST', payload=payload, headers=headers, timeout=timeout, provider=provider)


def get_json(
    url: str,
    *,
    headers: Mapping[str, str] | None=None,
    timeout: float=60.0,
    provider: str='',
) -> dict[str, Any]:
    return request_json(url, method='GET', payload=None, headers=headers, timeout=timeout, provider=provider)
