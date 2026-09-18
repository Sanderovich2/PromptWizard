from __future__ import annotations

import json
import urllib.request

import pytest

from promptwizard.config import Config
from promptwizard.i18n import get_translator
from promptwizard.webui.server import serve

PRESET_CONFIG = {
    "provider": "pollinations",
    "models": {
        "primary": {"provider": "pollinations", "model": "openai", "alias": "Free default"},
        "mine": {
            "provider": "cerebras",
            "model": "llama3.1-8b",
            "base_url": "https://api.cerebras.ai/v1",
            "api_key_env": "CEREBRAS_API_KEY",
            "tooltip": "my own model",
        },
        "catalog": [{"provider": "groq", "model": "llama-3.3-70b-versatile", "alias": "Groq free"}],
    },
}


@pytest.fixture()
def web(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps(PRESET_CONFIG), encoding="utf-8")
    config = Config.load(home=tmp_path, dotenv=False)
    config.provider = "offline"
    httpd, _thread, url = serve(config, get_translator("en"))
    yield url.rstrip("/"), tmp_path
    httpd.shutdown()
    httpd.server_close()


def test_presets_are_parsed_from_the_config_file(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps(PRESET_CONFIG), encoding="utf-8")
    config = Config.load(home=tmp_path, dotenv=False)
    assert set(config.presets) == {"primary", "mine", "groq-free"}
    assert config.presets["mine"].base_url == "https://api.cerebras.ai/v1"
    assert config.presets["mine"].label == "mine"
    assert config.presets["primary"].alias == "Free default"


def test_applying_a_preset_switches_provider_and_model(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps(PRESET_CONFIG), encoding="utf-8")
    config = Config.load(home=tmp_path, dotenv=False)
    config.apply_preset("mine")
    assert config.provider == "cerebras"
    settings = config.provider_settings()
    assert settings.model == "llama3.1-8b"
    assert settings.base_url == "https://api.cerebras.ai/v1"
    assert settings.api_key_env == "CEREBRAS_API_KEY"


def test_unknown_preset_is_refused(tmp_path):
    from promptwizard.errors import ConfigError

    (tmp_path / "config.json").write_text(json.dumps(PRESET_CONFIG), encoding="utf-8")
    config = Config.load(home=tmp_path, dotenv=False)
    with pytest.raises(ConfigError):
        config.apply_preset("nope")


def test_state_exposes_the_presets(web):
    base, _tmp = web
    with urllib.request.urlopen(base + "/api/state", timeout=15) as response:
        payload = json.loads(response.read())
    assert "mine" in payload["settings"]["presets"]
    assert payload["strings"]["web.open_config"]


def test_config_open_endpoint_returns_the_path_without_launching(web):
    base, tmp_path = web
    request = urllib.request.Request(
        base + "/api/config/open",
        data=json.dumps({"launch": False}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read())
    assert payload["path"].endswith("config.json")
    assert (tmp_path / "config.json").exists()
