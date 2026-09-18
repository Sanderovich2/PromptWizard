from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.request

import pytest

from promptwizard.config import Config
from promptwizard.i18n import get_translator
from promptwizard.webui.server import serve


@pytest.fixture()
def web(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    config.provider = "offline"
    httpd, _thread, url = serve(config, get_translator("en"))
    yield url.rstrip("/")
    httpd.shutdown()
    httpd.server_close()


def get(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=15) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def post(base, path, payload):
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_index_is_served(web):
    status, body = get(web, "/")
    assert status == 200
    assert b"<!DOCTYPE html>" in body
    assert b"/assets/app.css" in body
    assert b"logo.svg" in body
    assert b"file-input" in body
    assert b"export-format" in body


def test_assets_are_served(web):
    status, css = get(web, "/assets/app.css")
    assert status == 200 and b"--accent" in css
    status, script = get(web, "/assets/app.js")
    assert status == 200 and b"loadState" in script


def test_missing_asset_is_a_404(web):
    status, _body = get(web, "/assets/missing.css")
    assert status == 404


def test_state_carries_the_strings(web):
    status, body = get(web, "/api/state?lang=en")
    payload = json.loads(body)
    assert status == 200
    assert payload["lang"] == "en"
    assert payload["provider"] == "offline"
    assert payload["strings"]["app.name"] == "PromptWizard"
    assert "gui.tab_result" in payload["strings"]
    assert "severity.high" in payload["strings"]


def test_state_switches_language(web):
    status, body = get(web, "/api/state?lang=ru")
    payload = json.loads(body)
    assert status == 200
    assert payload["lang"] == "ru"
    assert payload["strings"]["gui.tab_result"] == "Результат"


def test_analyze_then_rewrite(web):
    status, data = post(web, "/api/analyze", {"prompt": "Write something about cats", "lang": "en"})
    assert status == 200
    assert data["analysis"]["issues"]
    assert data["questions"]

    answers = {question["id"]: "a short bullet list" for question in data["questions"]}
    status, result = post(web, "/api/rewrite", {"id": data["id"], "answers": answers})
    assert status == 200
    assert result["rewrite"]["improved_prompt"]
    assert result["rewrite"]["changes"]
    assert result["mode"] == "offline"
    assert result["saved"]


def test_empty_prompt_is_refused(web):
    status, data = post(web, "/api/analyze", {"prompt": "   ", "lang": "en"})
    assert status == 400
    assert "error" in data


def test_unknown_session_is_refused(web):
    status, data = post(web, "/api/rewrite", {"id": "nope", "answers": {}})
    assert status == 404
    assert "error" in data


def test_unknown_path_is_a_404(web):
    status, _body = get(web, "/nope")
    assert status == 404


def test_state_exposes_settings(web):
    status, body = get(web, "/api/state")
    payload = json.loads(body)
    assert status == 200
    assert payload["settings"]["theme"] == "light"
    assert payload["settings"]["provider"] == "offline"
    assert {"light", "dark"} <= set(payload["themes"])
    assert "web.settings" in payload["strings"]


def test_settings_are_saved_to_disk(web, tmp_path):
    status, data = post(web, "/api/settings", {"theme": "dark", "provider": "offline", "model": "demo"})
    assert status == 200
    assert data["settings"]["theme"] == "dark"
    assert data["settings"]["model"] == "demo"
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["theme"] == "dark"
    assert saved["providers"]["offline"]["model"] == "demo"
    status, body = get(web, "/api/state")
    assert json.loads(body)["settings"]["theme"] == "dark"


def test_custom_provider_is_saved_and_selected(web, tmp_path):
    status, data = post(
        web,
        "/api/settings",
        {
            "providers": {
                "mine": {
                    "base_url": "https://api.example.com/v1",
                    "model": "m1",
                    "api_key_env": "MINE_API_KEY",
                }
            },
            "provider": "mine",
            "model": "m1",
        },
    )
    assert status == 200
    assert data["settings"]["provider"] == "mine"
    assert data["settings"]["model"] == "m1"
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["providers"]["mine"]["base_url"] == "https://api.example.com/v1"
    assert saved["providers"]["mine"]["api_key_env"] == "MINE_API_KEY"


def test_unknown_setting_is_refused(web):
    status, data = post(web, "/api/settings", {"nonsense": 1})
    assert status == 400
    assert "error" in data


def test_models_endpoint(web):
    status, body = get(web, "/api/models?provider=offline")
    data = json.loads(body)
    assert status == 200
    assert data["provider"] == "offline"
    assert data["current"] == "deterministic-stub"
    assert "deterministic-stub" in data["models"]


def test_providers_endpoint_reports_every_provider(web, monkeypatch):
    from promptwizard.llm.base import ProviderStatus
    import promptwizard.webui.server as server_module

    def fake(config):
        return (
            ProviderStatus(name="offline", available=True, detail="stub ready", models=("deterministic-stub",)),
            ProviderStatus(name="groq", available=False, detail="no API key found", requires_key=True, key_present=False),
            ProviderStatus(name="pollinations", available=True, detail="reachable, 1 model(s) listed", models=("openai-fast",)),
            ProviderStatus(name="ollama", available=False, detail="ollama: cannot reach the provider ([WinError 10061])"),
        )

    monkeypatch.setattr(server_module, "describe_providers", fake)
    status, body = get(web, "/api/providers")
    payload = json.loads(body)
    assert status == 200
    assert [entry["name"] for entry in payload["providers"]] == ["offline", "groq", "pollinations", "ollama"]

    offline, groq, pollinations, ollama = payload["providers"]
    assert offline["available"] is True
    assert offline["state"] == "ok"
    assert offline["models"] == ["deterministic-stub"]
    assert offline["current"] == "deterministic-stub"
    assert offline["model_ok"] is True

    assert groq["available"] is False
    assert groq["state"] == "no_key"
    assert groq["requires_key"] is True
    assert groq["key_present"] is False
    assert groq["model_ok"] is True

    assert pollinations["state"] == "ok"
    assert pollinations["current"] == "openai"
    assert pollinations["model_ok"] is False

    assert ollama["state"] == "unreachable"
    assert "cannot reach" in ollama["detail"]


def test_the_providers_endpoint_survives_an_empty_result(web, monkeypatch):
    import promptwizard.webui.server as server_module

    def fake(config):
        return ()

    monkeypatch.setattr(server_module, "describe_providers", fake)
    status, body = get(web, "/api/providers")
    assert status == 200
    assert json.loads(body)["providers"] == []


def test_the_rewrite_response_carries_the_run_stats(web):
    status, data = post(web, "/api/analyze", {"prompt": "Write something about cats", "lang": "en"})
    assert status == 200
    status, result = post(web, "/api/rewrite", {"id": data["id"], "answers": {}})
    assert status == 200
    assert "duration_ms" in result["stats"]
    assert result["stats"]["tokens_total"] == 0
    assert result["original_prompt"].startswith("Write something about cats")


def test_drafts_are_collected_and_can_be_cleared(web):
    status, body = get(web, "/api/drafts")
    assert status == 200
    assert json.loads(body)["drafts"] == []

    status, _data = post(web, "/api/analyze", {"prompt": "Write something about cats", "lang": "en"})
    assert status == 200
    status, body = get(web, "/api/drafts")
    assert json.loads(body)["drafts"] == ["Write something about cats"]

    status, data = post(web, "/api/drafts", {"prompt": "Write something about cats"})
    assert status == 200
    assert data["drafts"] == []

    post(web, "/api/analyze", {"prompt": "Write something about dogs", "lang": "en"})
    status, data = post(web, "/api/drafts/clear", {})
    assert status == 200
    assert data["drafts"] == []


def test_the_result_is_autosaved_into_the_configured_folder(web, tmp_path):
    target = tmp_path / "out"
    status, _data = post(web, "/api/settings", {"autosave_dir": str(target)})
    assert status == 200
    status, started = post(web, "/api/analyze", {"prompt": "Write something about cats", "lang": "en"})
    assert status == 200
    status, result = post(web, "/api/rewrite", {"id": started["id"], "answers": {}})
    assert status == 200
    assert result["autosaved"]
    saved = pathlib.Path(result["autosaved"])
    assert saved.exists()
    assert saved.parent == target
    assert "cats" in saved.read_text(encoding="utf-8")


def test_autosave_stays_quiet_without_a_folder(web):
    status, started = post(web, "/api/analyze", {"prompt": "Write something about cats", "lang": "en"})
    assert status == 200
    status, result = post(web, "/api/rewrite", {"id": started["id"], "answers": {}})
    assert status == 200
    assert result["autosaved"] == ""


def test_the_update_endpoint_reports_the_release(web, monkeypatch):
    import promptwizard.webui.server as server_module

    def fake(current):
        return {"current": "0.3.4", "latest": "9.9.9", "url": "https://example.test", "newer": True}

    monkeypatch.setattr(server_module, "check_for_update", fake)
    status, body = get(web, "/api/update")
    data = json.loads(body)
    assert status == 200
    assert data["newer"] is True
    assert data["latest"] == "9.9.9"


def test_the_update_endpoint_survives_a_dead_network(web, monkeypatch):
    import promptwizard.webui.server as server_module

    def boom(current):
        raise OSError("no network")

    monkeypatch.setattr(server_module, "check_for_update", boom)
    status, body = get(web, "/api/update")
    data = json.loads(body)
    assert status == 200
    assert data["newer"] is False
    assert data["current"]
    assert "no network" in data["error"]


def test_the_analyze_response_carries_the_translation_slot(web):
    status, data = post(web, "/api/analyze", {"prompt": "Write something about cats", "lang": "en"})
    assert status == 200
    assert data["translation"] == ""
