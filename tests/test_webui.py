from __future__ import annotations

import json
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
