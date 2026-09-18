"""Config loading precedence, validation and provider merging."""

from __future__ import annotations

import json
import os

import pytest

from promptwizard.config import Config, load_dotenv
from promptwizard.errors import ConfigError


def test_defaults_come_from_the_builtin_table(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    assert config.provider == "pollinations"
    assert config.max_questions == 6
    assert {
        "pollinations",
        "ollama",
        "gemini",
        "groq",
        "openrouter",
        "openai_compatible",
        "offline",
    } <= set(config.providers)


def test_the_default_provider_needs_no_key(tmp_path):
    """A fresh install must work with no configuration at all."""
    config = Config.load(home=tmp_path, dotenv=False)
    settings = config.provider_settings()
    assert settings.base_url == "https://text.pollinations.ai/openai"
    assert settings.api_key_env == ""
    assert config.resolve_api_key() is None


def test_config_file_overrides_defaults(tmp_path):
    (tmp_path / "config.json").write_text(
        json.dumps({"provider": "groq", "max_questions": 3}), encoding="utf-8"
    )
    config = Config.load(home=tmp_path, dotenv=False)
    assert config.provider == "groq"
    assert config.max_questions == 3


def test_environment_beats_the_config_file(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text(json.dumps({"provider": "groq"}), encoding="utf-8")
    monkeypatch.setenv("PROMPTWIZARD_PROVIDER", "gemini")
    assert Config.load(home=tmp_path, dotenv=False).provider == "gemini"


def test_cli_overrides_beat_everything(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPTWIZARD_TEMPERATURE", "1.5")
    config = Config.load(home=tmp_path, overrides={"temperature": 0.9}, dotenv=False)
    assert config.temperature == 0.9


@pytest.mark.parametrize(
    "overrides",
    [{"temperature": 5.0}, {"timeout": 0}, {"max_tokens": 0}, {"max_questions": 99}],
)
def test_out_of_range_values_are_rejected(tmp_path, overrides):
    with pytest.raises(ConfigError):
        Config.load(home=tmp_path, overrides=overrides, dotenv=False)


def test_unknown_provider_is_usable_through_config_alone(tmp_path):
    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "providers": {
                    "cerebras": {
                        "base_url": "https://api.cerebras.ai/v1",
                        "model": "llama3.1-8b",
                        "api_key_env": "CEREBRAS_API_KEY",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    settings = Config.load(home=tmp_path, dotenv=False).provider_settings("cerebras")
    assert settings.base_url == "https://api.cerebras.ai/v1"
    assert settings.kind == "openai_compatible"


def test_resolve_api_key_prefers_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "  secret  ")
    assert Config.load(home=tmp_path, dotenv=False).resolve_api_key("groq") == "secret"


def test_set_provider_override_applies_model_and_base_url(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    config.set_provider_override(provider="groq", model="llama-3.1-8b-instant", base_url="https://example.test/v1")
    settings = config.provider_settings()
    assert config.provider == "groq"
    assert settings.model == "llama-3.1-8b-instant"
    assert settings.base_url == "https://example.test/v1"


def test_save_writes_json_without_secret_material(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    config.set_provider_override(provider="gemini")
    path = config.save()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["provider"] == "gemini"
    assert "api_key" not in payload["providers"]["gemini"]


def test_load_dotenv_parses_the_supported_subset(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('# comment\nexport FOO=bar\nQUOTED="a b"\n', encoding="utf-8")
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("QUOTED", raising=False)
    loaded = load_dotenv([env_file])
    assert loaded == [env_file]
    assert os.environ["FOO"] == "bar"
    assert os.environ["QUOTED"] == "a b"
