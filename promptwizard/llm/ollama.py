from __future__ import annotations
from typing import Any, Mapping
from promptwizard.errors import LLMResponseError, MissingCredentials, ProviderHTTPError
from promptwizard.llm.base import LLMProvider, LLMRequest, LLMResponse, ProviderStatus
from promptwizard.llm.http import get_json, post_json
__all__ = ['OllamaProvider']
DEFAULT_BASE_URL = 'http://localhost:11434'

class OllamaProvider(LLMProvider):
    name = 'ollama'
    kind = 'ollama'
    requires_key = False

    @property
    def base_url(self) -> str:
        return (self.settings.base_url or DEFAULT_BASE_URL).rstrip('/')

    def complete(self, request: LLMRequest) -> LLMResponse:
        prepared = self.prepare(request)
        if not self.model:
            raise MissingCredentials('ollama: no model configured', hint_key='error.provider.no_model', hint_kwargs={'provider': self.name})
        messages: list[dict[str, str]] = []
        if prepared.system:
            messages.append({'role': 'system', 'content': prepared.system})
        messages.append({'role': 'user', 'content': prepared.prompt})
        payload: dict[str, Any] = {'model': self.model, 'messages': messages, 'stream': False, 'options': {'temperature': prepared.temperature, 'num_predict': prepared.max_tokens}}
        if prepared.json_mode:
            payload['format'] = 'json'
        try:
            data = post_json(f'{self.base_url}/api/chat', payload, timeout=self.timeout, provider=self.name)
        except ProviderHTTPError as exc:
            if exc.status == 404 and 'not found' in exc.body.lower():
                raise ProviderHTTPError(f'ollama: model {self.model!r} is not pulled locally', status=exc.status, body=exc.body, hint_key='error.provider.ollama_pull', hint_kwargs={'provider': self.name, 'model': self.model}) from exc
            raise
        return LLMResponse(text=self._extract_text(data), provider=self.name, model=str(data.get('model') or self.model), raw=data)

    def list_models(self) -> tuple[str, ...]:
        data = get_json(f'{self.base_url}/api/tags', timeout=min(self.timeout, 10.0), provider=self.name)
        entries = data.get('models') or []
        names = []
        for entry in entries:
            if isinstance(entry, Mapping):
                name = entry.get('name') or entry.get('model')
                if name:
                    names.append(str(name))
        return tuple(sorted(names))

    def status(self) -> ProviderStatus:
        try:
            models = self.list_models()
        except Exception as exc:
            return ProviderStatus(name=self.name, available=False, detail=str(getattr(exc, 'message', exc)))
        detail = 'server reachable'
        if self.model and models and (not any((item.split(':')[0] == self.model.split(':')[0] for item in models))):
            detail = f'server reachable, but {self.model!r} is not pulled yet'
        elif not self.model:
            detail = 'server reachable, no model configured'
        return ProviderStatus(name=self.name, available=True, detail=detail, models=models)

    @staticmethod
    def _extract_text(data: Mapping[str, Any]) -> str:
        message = data.get('message')
        if isinstance(message, Mapping):
            content = message.get('content')
            if isinstance(content, str) and content.strip():
                return content
        response = data.get('response')
        if isinstance(response, str) and response.strip():
            return response
        error = data.get('error')
        if error:
            raise LLMResponseError(f'ollama: {error}', hint_key='error.provider.bad_response', hint_kwargs={'provider': 'ollama'})
        raise LLMResponseError('ollama: response contained no message content', hint_key='error.provider.bad_response', hint_kwargs={'provider': 'ollama'})
