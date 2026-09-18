from __future__ import annotations
from typing import Any, Mapping
from promptwizard.errors import LLMResponseError, MissingCredentials
from promptwizard.llm.base import LLMProvider, LLMRequest, LLMResponse, ProviderStatus
from promptwizard.llm.http import get_json, post_json
__all__ = ['OpenAICompatibleProvider']

class OpenAICompatibleProvider(LLMProvider):
    name = 'openai_compatible'
    kind = 'openai_compatible'
    requires_key = True
    supports_json_mode = True
    extra_headers: Mapping[str, str] = {}

    @property
    def base_url(self) -> str:
        return (self.settings.base_url or '').rstrip('/')

    @property
    def endpoint(self) -> str:
        return f'{self.base_url}/chat/completions'

    @property
    def models_endpoint(self) -> str:
        return f'{self.base_url}/models'

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        headers.update({key: value for key, value in self.extra_headers.items() if value})
        return headers

    def _require_ready(self) -> None:
        if not self.base_url:
            raise MissingCredentials(f'{self.name}: no base_url configured', hint_key='error.provider.no_base_url', hint_kwargs={'provider': self.name})
        if self.requires_key and (not self.api_key):
            raise MissingCredentials(f'{self.name}: no API key found', hint_key='error.provider.missing_key', hint_kwargs={'provider': self.name, 'env_var': self.api_key_env or 'API_KEY'})
        if not self.model:
            raise MissingCredentials(f'{self.name}: no model configured', hint_key='error.provider.no_model', hint_kwargs={'provider': self.name})

    def complete(self, request: LLMRequest) -> LLMResponse:
        self._require_ready()
        prepared = self.prepare(request)
        messages: list[dict[str, str]] = []
        if prepared.system:
            messages.append({'role': 'system', 'content': prepared.system})
        messages.append({'role': 'user', 'content': prepared.prompt})
        payload: dict[str, Any] = {'model': self.model, 'messages': messages, 'temperature': prepared.temperature, 'max_tokens': prepared.max_tokens, 'stream': False}
        if prepared.json_mode and self.supports_json_mode:
            payload['response_format'] = {'type': 'json_object'}
        data = post_json(self.endpoint, payload, headers=self._headers(), timeout=self.timeout, provider=self.name)
        return LLMResponse(text=self._extract_text(data), provider=self.name, model=str(data.get('model') or self.model), raw=data)

    def list_models(self) -> tuple[str, ...]:
        data = get_json(self.models_endpoint, headers=self._headers(), timeout=min(self.timeout, 15.0), provider=self.name)
        entries = data.get('data') or data.get('models') or []
        names: list[str] = []
        for entry in entries:
            if isinstance(entry, Mapping):
                value = entry.get('id') or entry.get('name')
                if value:
                    names.append(str(value))
            elif isinstance(entry, str):
                names.append(entry)
        return tuple(sorted(names))

    def status(self) -> ProviderStatus:
        if self.requires_key and (not self.api_key):
            return ProviderStatus(name=self.name, available=False, detail='no API key found', requires_key=True, key_present=False)
        try:
            models = self.list_models()
        except Exception as exc:
            status = getattr(exc, 'status', None)
            if status == 404:
                return ProviderStatus(name=self.name, available=True, detail='key present; provider does not expose /models', requires_key=self.requires_key, key_present=bool(self.api_key))
            return ProviderStatus(name=self.name, available=False, detail=str(getattr(exc, 'message', exc)), requires_key=self.requires_key, key_present=bool(self.api_key))
        return ProviderStatus(name=self.name, available=True, detail=f'reachable, {len(models)} model(s) listed', models=models, requires_key=self.requires_key, key_present=bool(self.api_key))

    @staticmethod
    def _extract_text(data: Mapping[str, Any]) -> str:
        error = data.get('error')
        if error and (not data.get('choices')):
            detail = error.get('message') if isinstance(error, Mapping) else str(error)
            raise LLMResponseError(f'provider returned an error: {detail}', hint_key='error.provider.bad_response', hint_kwargs={'provider': 'api'})
        choices = data.get('choices') or []
        if not choices:
            raise LLMResponseError('response contained no choices', hint_key='error.provider.bad_response', hint_kwargs={'provider': 'api'})
        first = choices[0]
        if not isinstance(first, Mapping):
            raise LLMResponseError('malformed choice entry', hint_key='error.provider.bad_response', hint_kwargs={'provider': 'api'})
        message = first.get('message') or {}
        content: Any = message.get('content') if isinstance(message, Mapping) else None
        if content is None and isinstance(first.get('text'), str):
            content = first['text']
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            parts = [part.get('text', '') for part in content if isinstance(part, Mapping)]
            text = ''.join(parts)
            if text.strip():
                return text
        raise LLMResponseError('response contained no text content', hint_key='error.provider.bad_response', hint_kwargs={'provider': 'api'})
