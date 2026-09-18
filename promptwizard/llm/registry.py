"""Provider registry: name/kind -> adapter, plus the ``providers`` command data.

This is the single place that knows which adapter implements which provider.  A
provider added purely through ``config.json`` (a new OpenAI-compatible free
tier) resolves through its ``kind``, so no registry change is needed for it.
"""

from __future__ import annotations

from promptwizard.config import PROVIDER_NAMES, Config, ProviderSettings
from promptwizard.llm.base import LLMProvider, ProviderStatus
from promptwizard.llm.gemini import GeminiProvider
from promptwizard.llm.hosted import GroqProvider, OpenRouterProvider, PollinationsProvider
from promptwizard.llm.offline import OfflineProvider
from promptwizard.llm.ollama import OllamaProvider
from promptwizard.llm.openai_compat import OpenAICompatibleProvider

__all__ = [
    "build_provider",
    "describe_providers",
    "provider_class",
    "provider_names",
]

#: Known provider names mapped to their adapter.
_BY_NAME: dict[str, type[LLMProvider]] = {
    "pollinations": PollinationsProvider,
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "openrouter": OpenRouterProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "offline": OfflineProvider,
}

#: Fallback by the ``kind`` field for providers defined only in config.
_BY_KIND: dict[str, type[LLMProvider]] = {
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "offline": OfflineProvider,
}


def provider_names() -> tuple[str, ...]:
    """Names of the built-in providers, in config order."""
    return PROVIDER_NAMES


def provider_class(name: str | None, kind: str | None = None) -> type[LLMProvider]:
    """Resolve the adapter for ``name``/``kind``.

    Name wins over kind because it is the more specific statement (``groq`` is
    more precise than ``openai_compatible``).  Anything unknown becomes a plain
    OpenAI-compatible adapter, which is exactly how a config-only free tier
    works.
    """
    if name and name in _BY_NAME:
        return _BY_NAME[name]
    if kind and kind in _BY_KIND:
        return _BY_KIND[kind]
    return OpenAICompatibleProvider


def build_provider(config: Config, name: str | None = None) -> LLMProvider:
    """Instantiate the provider selected by ``name`` (default: config.provider).

    The API key is resolved by :class:`promptwizard.config.Config` (environment
    first, then the config file) and never logged.
    """
    settings: ProviderSettings = config.provider_settings(name)
    adapter = provider_class(settings.name, settings.kind)
    provider = adapter(
        settings,
        api_key=config.resolve_api_key(settings.name),
        timeout=config.timeout,
        default_temperature=config.temperature,
        default_max_tokens=config.max_tokens,
    )
    # A config-only provider (for example "cerebras") reuses the generic adapter;
    # carry its real name so messages and session logs stay truthful.
    if settings.name and settings.name != provider.name:
        provider.name = settings.name
    return provider


def describe_providers(config: Config) -> tuple[ProviderStatus, ...]:
    """Probe every configured provider once, for ``promptwizard providers``.

    Probing is best effort: a provider that raises is reported as unavailable
    rather than aborting the command.
    """
    statuses: list[ProviderStatus] = []
    for name in sorted(config.providers):
        try:
            provider = build_provider(config, name)
            statuses.append(provider.status())
        except Exception as exc:  # noqa: BLE001 - the command must list all providers
            statuses.append(
                ProviderStatus(
                    name=name,
                    available=False,
                    detail=str(getattr(exc, "message", exc)),
                )
            )
    return tuple(statuses)
