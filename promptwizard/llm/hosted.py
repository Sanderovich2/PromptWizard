"""Thin, named subclasses of the OpenAI-compatible adapter.

``config`` already routes these two by ``kind == "openai_compatible"``; the
subclasses exist only to carry the correct provider name and the attribution
headers OpenRouter asks for, so status lines and session logs read
``groq/llama-3.3-70b-versatile`` instead of ``openai_compatible/...``.
"""

from __future__ import annotations

from typing import Mapping

from promptwizard.llm.openai_compat import OpenAICompatibleProvider

__all__ = ["GroqProvider", "OpenRouterProvider", "PollinationsProvider"]


class GroqProvider(OpenAICompatibleProvider):
    """Groq free tier (very fast open-weight models)."""

    name = "groq"
    kind = "openai_compatible"
    requires_key = True
    api_key_env = "GROQ_API_KEY"


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter, restricted in practice to the ``:free`` model variants."""

    name = "openrouter"
    kind = "openai_compatible"
    requires_key = True
    api_key_env = "OPENROUTER_API_KEY"
    #: OpenRouter's docs ask clients to identify themselves.
    extra_headers: Mapping[str, str] = {
        "HTTP-Referer": "https://github.com/Sanderovich2/PromptWizard",
        "X-Title": "PromptWizard",
    }


class PollinationsProvider(OpenAICompatibleProvider):
    """Keyless community endpoint (``text.pollinations.ai``).

    Needs no account, no key and no local server, so it is the default: a fresh
    install produces a real rewrite before anything is configured.  Being free
    and community-run, it may rate-limit; the pipeline then degrades to the
    deterministic template and the user is told why.
    """

    name = "pollinations"
    kind = "openai_compatible"
    requires_key = False
    api_key_env = ""
