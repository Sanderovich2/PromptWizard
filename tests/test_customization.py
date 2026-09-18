from __future__ import annotations

import json
import sys
import urllib.request

import pytest

from promptwizard.config import FONTS, THEMES, Config
from promptwizard.errors import ConfigError
from promptwizard.i18n import get_translator
from promptwizard.settings import save_settings, settings_view
from promptwizard.webui.server import serve


def test_theme_offers_follow_the_system():
    assert "auto" in THEMES


def test_font_size_is_validated(tmp_path):
    with pytest.raises(ConfigError):
        Config.load(home=tmp_path, overrides={"font_size": 40}, dotenv=False)


def test_font_and_size_round_trip(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    save_settings(config, {"font": "Georgia", "font_size": 18})
    reloaded = Config.load(home=tmp_path, dotenv=False)
    assert reloaded.font == "Georgia"
    assert reloaded.font_size == 18
    assert reloaded.to_dict()["font_size"] == 18
    assert "Georgia" in FONTS
    assert settings_view(reloaded)["font"] == "Georgia"


def test_autostart_round_trip_on_a_temp_key():
    if not sys.platform.startswith("win"):
        pytest.skip("autostart is wired up for Windows only")
    import winreg

    from promptwizard import autostart

    key = r"Software\PromptWizardTest\Run"
    try:
        autostart.set_enabled(True, key_path=key, command='"C:\\fake\\promptwizard-gui.exe"')
        assert autostart.is_enabled(key_path=key)
        assert "promptwizard-gui" in autostart.current_command(key_path=key)
        assert autostart.state(key_path=key)["enabled"] is True
        autostart.set_enabled(False, key_path=key)
        assert not autostart.is_enabled(key_path=key)
    finally:
        for path in (key, r"Software\PromptWizardTest"):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
            except OSError:
                pass


@pytest.fixture()
def web(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    config.provider = "offline"
    httpd, _thread, url = serve(config, get_translator("en"))
    yield url.rstrip("/"), tmp_path
    httpd.shutdown()
    httpd.server_close()


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=15) as response:
        return json.loads(response.read())


def _post(base, path, payload):
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def test_state_exposes_the_customization(web):
    base, _tmp = web
    payload = _get(base, "/api/state")
    assert "auto" in payload["themes"]
    assert "" in payload["settings"]["fonts"]
    assert "Georgia" in payload["settings"]["fonts"]
    assert "supported" in payload["settings"]["autostart"]
    assert payload["strings"]["web.font"]


def test_font_and_advanced_settings_are_saved(web):
    base, tmp_path = web
    data = _post(
        base,
        "/api/settings",
        {"font": "Georgia", "font_size": 19, "max_questions": 3, "temperature": 0.7, "max_tokens": 900},
    )
    assert data["settings"]["font"] == "Georgia"
    assert data["settings"]["font_size"] == 19
    assert data["settings"]["max_questions"] == 3
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["font"] == "Georgia"
    assert saved["font_size"] == 19
    assert saved["max_questions"] == 3


def test_autostart_endpoint_only_reads_when_no_value_is_given(web):
    base, _tmp = web
    data = _post(base, "/api/autostart", {})
    assert "supported" in data
    assert "command" in data


def test_custom_system_prompts_round_trip(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    save_settings(config, {"system_analyzer": "Always flag missing risks.", "system_rewriter": "Prefer short bullets."})
    reloaded = Config.load(home=tmp_path, dotenv=False)
    assert reloaded.system_analyzer == "Always flag missing risks."
    assert reloaded.system_rewriter == "Prefer short bullets."
    assert settings_view(reloaded)["system_analyzer"] == "Always flag missing risks."
    assert reloaded.to_dict()["system_rewriter"] == "Prefer short bullets."


def test_custom_system_prompts_can_be_cleared(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    save_settings(config, {"system_analyzer": "something"})
    save_settings(config, {"system_analyzer": ""})
    assert Config.load(home=tmp_path, dotenv=False).system_analyzer == ""


def test_web_saves_the_custom_system_prompts(web):
    base, tmp_path = web
    data = _post(base, "/api/settings", {"system_analyzer": "Be strict.", "system_rewriter": ""})
    assert data["settings"]["system_analyzer"] == "Be strict."
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["system_analyzer"] == "Be strict."
    assert saved["system_rewriter"] == ""
    state = _get(base, "/api/state")
    assert state["settings"]["system_analyzer"] == "Be strict."


def test_the_delivery_settings_round_trip(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    save_settings(
        config,
        {
            "auto_copy": True,
            "autosave_dir": "C:/Temp/prompts",
            "theme_day_start": "8:5",
            "theme_night_start": "22:30",
        },
    )
    reloaded = Config.load(home=tmp_path, dotenv=False)
    assert reloaded.auto_copy is True
    assert reloaded.autosave_dir == "C:/Temp/prompts"
    assert reloaded.theme_day_start == "08:05"
    assert reloaded.theme_night_start == "22:30"
    view = settings_view(reloaded)
    assert view["auto_copy"] is True
    assert view["autosave_dir"] == "C:/Temp/prompts"
    assert view["theme_night_start"] == "22:30"
    assert "schedule" in view["themes"]


def test_a_broken_clock_is_rejected(tmp_path):
    with pytest.raises(ConfigError):
        Config.load(home=tmp_path, overrides={"theme_day_start": "nope"}, dotenv=False)
    (tmp_path / "config.json").write_text(json.dumps({"theme_night_start": "25:00"}), encoding="utf-8")
    with pytest.raises(ConfigError):
        Config.load(home=tmp_path, dotenv=False)


def test_a_broken_boolean_is_rejected(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"auto_copy": "maybe"}), encoding="utf-8")
    with pytest.raises(ConfigError):
        Config.load(home=tmp_path, dotenv=False)


def test_the_analysis_switches_round_trip(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    save_settings(config, {"translate_prompt": True, "check_updates": False})
    reloaded = Config.load(home=tmp_path, dotenv=False)
    assert reloaded.translate_prompt is True
    assert reloaded.check_updates is False
    view = settings_view(reloaded)
    assert view["translate_prompt"] is True
    assert view["check_updates"] is False


def test_web_saves_the_delivery_settings(web):
    base, tmp_path = web
    data = _post(
        base,
        "/api/settings",
        {"auto_copy": True, "autosave_dir": "C:/Temp/out", "theme_day_start": "06:30", "theme_night_start": "21:15"},
    )
    assert data["settings"]["auto_copy"] is True
    assert data["settings"]["autosave_dir"] == "C:/Temp/out"
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["auto_copy"] is True
    assert saved["theme_day_start"] == "06:30"
    assert saved["theme_night_start"] == "21:15"
