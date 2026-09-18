from __future__ import annotations
from promptwizard.config import PROVIDER_NAMES, Config, ProviderSettings
from promptwizard.llm.base import LLMProvider, ProviderStatus
from promptwizard.llm.gemini import GeminiProvider
from promptwizard.llm.hosted import GroqProvider, OpenRouterProvider, PollinationsProvider
from promptwizard.llm.offline import OfflineProvider
from promptwizard.llm.ollama import OllamaProvider
from promptwizard.llm.openai_compat import OpenAICompatibleProvider
__all__ = ['STATES', 'build_provider', 'describe_providers', 'provider_class', 'provider_names', 'status_state']
STATES: tuple[str, ...] = ('ok', 'no_key', 'no_url', 'no_model', 'unreachable', 'error')
_UNREACHABLE_HINTS: tuple[str, ...] = ('cannot reach', 'unreachable', 'timed out', 'timeout', 'connection', 'refused', 'getaddrinfo', 'no route')
_BY_NAME: dict[str, type[LLMProvider]] = {'pollinations': PollinationsProvider, 'ollama': OllamaProvider, 'gemini': GeminiProvider, 'groq': GroqProvider, 'openrouter': OpenRouterProvider, 'openai_compatible': OpenAICompatibleProvider, 'offline': OfflineProvider}
_BY_KIND: dict[str, type[LLMProvider]] = {'ollama': OllamaProvider, 'gemini': GeminiProvider, 'openai_compatible': OpenAICompatibleProvider, 'offline': OfflineProvider}

def provider_names() -> tuple[str, ...]:
    return PROVIDER_NAMES

def provider_class(name: str | None, kind: str | None=None) -> type[LLMProvider]:
    if name and name in _BY_NAME:
        return _BY_NAME[name]
    if kind and kind in _BY_KIND:
        return _BY_KIND[kind]
    return OpenAICompatibleProvider

def build_provider(config: Config, name: str | None=None) -> LLMProvider:
    settings: ProviderSettings = config.provider_settings(name)
    adapter = provider_class(settings.name, settings.kind)
    provider = adapter(settings, api_key=config.resolve_api_key(settings.name), timeout=config.timeout, default_temperature=config.temperature, default_max_tokens=config.max_tokens)
    if settings.name and settings.name != provider.name:
        provider.name = settings.name
    return provider

def status_state(status: ProviderStatus) -> str:
    if status.available:
        return 'ok'
    if status.requires_key and (not status.key_present):
        return 'no_key'
    detail = (status.detail or '').strip()
    lowered = detail.lower()
    if 'no base_url' in lowered:
        return 'no_url'
    if 'no model' in lowered:
        return 'no_model'
    if any((needle in lowered for needle in _UNREACHABLE_HINTS)):
        return 'unreachable'
    return 'error'

def describe_providers(config: Config) -> tuple[ProviderStatus, ...]:
    statuses: list[ProviderStatus] = []
    for name in sorted(config.providers):
        try:
            provider = build_provider(config, name)
            statuses.append(provider.status())
        except Exception as exc:
            statuses.append(ProviderStatus(name=name, available=False, detail=str(getattr(exc, 'message', exc))))
    return tuple(statuses)
