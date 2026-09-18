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
