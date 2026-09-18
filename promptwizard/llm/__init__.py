"""LLM provider layer: one interface, several free backends.

``LLMProvider`` is the contract the rest of the application depends on.  The
pipeline never imports a concrete adapter; it receives an :class:`LLMProvider`
and calls :meth:`LLMProvider.complete`.  Swapping Ollama for Groq is a config
change, and every adapter can be replaced by a fake in tests.
"""

from __future__ import annotations

from promptwizard.llm.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderStatus,
)
from promptwizard.llm.registry import (
    build_provider,
    describe_providers,
    provider_names,
)

__all__ = [
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "ProviderStatus",
    "build_provider",
    "describe_providers",
    "provider_names",
]
