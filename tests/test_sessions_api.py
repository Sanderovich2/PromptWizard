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
    yield url.rstrip("/"), tmp_path
    httpd.shutdown()
    httpd.server_close()


def get(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=20) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def post(base, path, payload):
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, json.loads(response.read())


def test_sessions_are_empty_at_first(web):
    base, _tmp = web
    status, data = get(base, "/api/sessions")
    assert status == 200
    assert data["sessions"] == []


def test_a_run_shows_up_in_the_session_list(web):
    base, _tmp = web
    status, started = post(base, "/api/analyze", {"prompt": "Write something about cats", "lang": "en"})
    assert status == 200
    status, result = post(base, "/api/rewrite", {"id": started["id"], "answers": {}})
    assert status == 200

    status, listing = get(base, "/api/sessions")
    assert status == 200
    assert listing["sessions"], "the finished run must be listed"
    entry = listing["sessions"][0]
    assert entry["id"] == result["id"]
    assert entry["provider"] == "offline"
    assert "cats" in entry["prompt"]

    status, record = get(base, "/api/sessions/" + entry["id"])
    assert status == 200
    assert record["rewrite"]["improved_prompt"]
    assert record["rewrite"]["changes"]


def test_an_unknown_session_is_a_404(web):
    base, _tmp = web
    status, data = get(base, "/api/sessions/nope")
    assert status == 404
    assert "error" in data


def test_the_limit_is_validated(web):
    base, _tmp = web
    status, data = get(base, "/api/sessions?limit=abc")
    assert status == 400
