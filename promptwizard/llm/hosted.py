from __future__ import annotations
from typing import Mapping
from promptwizard.llm.openai_compat import OpenAICompatibleProvider
__all__ = ['GroqProvider', 'OpenRouterProvider', 'PollinationsProvider']

class GroqProvider(OpenAICompatibleProvider):
    name = 'groq'
    kind = 'openai_compatible'
    requires_key = True
    api_key_env = 'GROQ_API_KEY'

class OpenRouterProvider(OpenAICompatibleProvider):
    name = 'openrouter'
    kind = 'openai_compatible'
    requires_key = True
    api_key_env = 'OPENROUTER_API_KEY'
    extra_headers: Mapping[str, str] = {'HTTP-Referer': 'https://github.com/Sanderovich2/PromptWizard', 'X-Title': 'PromptWizard'}

class PollinationsProvider(OpenAICompatibleProvider):
    name = 'pollinations'
    kind = 'openai_compatible'
    requires_key = False
    api_key_env = ''
