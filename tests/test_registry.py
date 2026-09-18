from __future__ import annotations
import json
from promptwizard.config import Config
from promptwizard.llm.hosted import GroqProvider, OpenRouterProvider, PollinationsProvider
from promptwizard.llm.offline import OfflineProvider
from promptwizard.llm.ollama import OllamaProvider
from promptwizard.llm.openai_compat import OpenAICompatibleProvider
from promptwizard.llm.registry import build_provider, provider_class, provider_names

def test_known_names_resolve_to_their_adapter():
    assert provider_class('pollinations', 'openai_compatible') is PollinationsProvider
    assert provider_class('groq', 'openai_compatible') is GroqProvider
    assert provider_class('openrouter', 'openai_compatible') is OpenRouterProvider
    assert provider_class('ollama', 'ollama') is OllamaProvider
    assert provider_class('offline', 'offline') is OfflineProvider

def test_unknown_name_falls_back_to_the_kind():
    assert provider_class('cerebras', 'openai_compatible') is OpenAICompatibleProvider
    assert provider_class('whatever', None) is OpenAICompatibleProvider

def test_provider_names_cover_the_builtin_table():
    names = set(provider_names())
    assert {'pollinations', 'ollama', 'gemini', 'groq', 'openrouter', 'offline'} <= names

def test_the_default_provider_is_keyless(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    provider = build_provider(config)
    assert isinstance(provider, PollinationsProvider)
    assert provider.requires_key is False
    assert provider.api_key is None
    assert provider.base_url == 'https://text.pollinations.ai/openai'

def test_config_only_provider_keeps_its_name_and_url(tmp_path):
    (tmp_path / 'config.json').write_text(json.dumps({'provider': 'cerebras', 'providers': {'cerebras': {'base_url': 'https://api.cerebras.ai/v1', 'model': 'llama3.1-8b', 'api_key_env': 'CEREBRAS_API_KEY'}}}), encoding='utf-8')
    provider = build_provider(Config.load(home=tmp_path, dotenv=False))
    assert provider.name == 'cerebras'
    assert provider.base_url == 'https://api.cerebras.ai/v1'
    assert provider.model == 'llama3.1-8b'
