from __future__ import annotations
import json
from promptwizard.config import Config
from promptwizard.llm.hosted import GroqProvider, OpenRouterProvider, PollinationsProvider
from promptwizard.llm.offline import OfflineProvider
from promptwizard.llm.ollama import OllamaProvider
from promptwizard.llm.openai_compat import OpenAICompatibleProvider
from promptwizard.llm.base import ProviderStatus
from promptwizard.llm.registry import build_provider, provider_class, provider_names, status_state

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

def test_a_keyless_provider_does_not_claim_to_need_a_key(tmp_path, monkeypatch):
    config = Config.load(home=tmp_path, dotenv=False)
    provider = build_provider(config, 'pollinations')
    monkeypatch.setattr(provider, 'list_models', lambda: ('openai-fast',))
    status = provider.status()
    assert status.available is True
    assert status.requires_key is False
    assert status.key_present is False
    assert status.models == ('openai-fast',)
    assert status_state(status) == 'ok'

def test_a_provider_with_a_key_reports_it(tmp_path, monkeypatch):
    config = Config.load(home=tmp_path, dotenv=False)
    config.providers['groq'].api_key = 'secret'
    provider = build_provider(config, 'groq')
    monkeypatch.setattr(provider, 'list_models', lambda: ('llama-3.3-70b-versatile',))
    status = provider.status()
    assert status.available is True
    assert status.requires_key is True
    assert status.key_present is True
    assert status_state(status) == 'ok'

def test_the_status_state_names_the_reason():
    assert status_state(ProviderStatus(name='a', available=True, detail='reachable, 2 model(s) listed')) == 'ok'
    assert status_state(ProviderStatus(name='a', available=False, detail='no API key found', requires_key=True, key_present=False)) == 'no_key'
    assert status_state(ProviderStatus(name='a', available=False, detail='a: no base_url configured')) == 'no_url'
    assert status_state(ProviderStatus(name='a', available=False, detail='a: no model configured')) == 'no_model'
    assert status_state(ProviderStatus(name='a', available=False, detail='ollama: cannot reach the provider ([WinError 10061])')) == 'unreachable'
    assert status_state(ProviderStatus(name='a', available=False, detail='something odd')) == 'error'
    assert status_state(ProviderStatus(name='a', available=False, detail='')) == 'error'
