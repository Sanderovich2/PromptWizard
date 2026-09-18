from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from promptwizard.batch import BATCH_LIMIT, clean_prompts, run_batch, split_prompts
from promptwizard.config import Config
from promptwizard.i18n import get_translator
from promptwizard.webui.server import serve


def test_prompts_split_on_a_blank_line():
    assert split_prompts("one\n\ntwo") == ["one", "two"]


def test_prompts_split_on_a_rule():
    assert split_prompts("one\n---\ntwo") == ["one", "two"]


def test_prompts_split_on_several_blank_lines():
    assert split_prompts("one\n\n\n   \n\ntwo\n") == ["one", "two"]


def test_a_single_prompt_stays_whole():
    assert split_prompts("just one prompt\nwith a line break") == ["just one prompt\nwith a line break"]


def test_empty_input_yields_nothing():
    assert split_prompts("   \n\n  ") == []
    assert split_prompts("") == []


def test_clean_prompts_drops_duplicates_and_blanks():
    assert clean_prompts(["one", " ", "one", "two"]) == ["one", "two"]


def test_clean_prompts_respects_the_limit():
    assert len(clean_prompts([f"p{index}" for index in range(BATCH_LIMIT + 5)])) == BATCH_LIMIT


def test_the_offline_batch_rewrites_every_prompt(config, translator):
    config.provider = "offline"
    results = run_batch(config, translator, ["Write something about cats", "Do the thing"])
    assert len(results) == 2
    assert all(result.rewrite is not None for result in results)
    assert results[0].original_prompt == "Write something about cats"


@pytest.fixture()
def web(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    config.provider = "offline"
    httpd, _thread, url = serve(config, get_translator("en"))
    yield url.rstrip("/"), tmp_path
    httpd.shutdown()
    httpd.server_close()


def post(base, path, payload):
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=20) as response:
        return response.status, json.loads(response.read())


def test_the_batch_endpoint_returns_every_result(web):
    base, _tmp = web
    status, data = post(
        base,
        "/api/batch",
        {"prompts": "Write something about cats\n\nDo the thing", "lang": "en"},
    )
    assert status == 200
    assert len(data["results"]) == 2
    first = data["results"][0]
    assert first["prompt"] == "Write something about cats"
    assert first["rewrite"]["improved_prompt"]
    assert first["score"] >= 0
    assert first["saved"]


def test_the_batch_endpoint_saves_the_sessions(web):
    base, _tmp = web
    status, data = post(base, "/api/batch", {"prompts": ["Write something about cats"], "lang": "en"})
    assert status == 200
    identifier = data["results"][0]["id"]
    status, record = get(base, "/api/sessions/" + identifier)
    assert status == 200
    assert record["original_prompt"].startswith("Write something about cats")


def test_the_batch_endpoint_feeds_the_drafts(web):
    base, _tmp = web
    post(base, "/api/batch", {"prompts": ["Write something about cats", "Do the thing"], "lang": "en"})
    status, data = get(base, "/api/drafts")
    assert status == 200
    assert data["drafts"] == ["Do the thing", "Write something about cats"]


def test_an_empty_batch_is_refused(web):
    base, _tmp = web
    status, data = post(base, "/api/batch", {"prompts": "   ", "lang": "en"})
    assert status == 400
    assert "error" in data
