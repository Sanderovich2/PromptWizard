from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from promptwizard.update import RELEASES_URL, check_for_update, compare_versions, parse_version


class _Feed(BaseHTTPRequestHandler):
    payload: dict = {}

    def log_message(self, *args):
        return

    def do_GET(self):
        body = json.dumps(self.payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def feed():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Feed)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/latest"
    finally:
        server.shutdown()
        server.server_close()


def test_the_release_feed_is_a_github_url():
    assert RELEASES_URL.startswith("https://api.github.com/repos/")
    assert RELEASES_URL.endswith("/releases/latest")


def test_versions_are_compared_as_numbers():
    assert parse_version("v0.3.4") == (0, 3, 4)
    assert parse_version("1.2") == (1, 2)
    assert compare_versions("0.3.4", "0.3.4") == 0
    assert compare_versions("0.3.4", "0.4.0") == -1
    assert compare_versions("0.3.10", "0.3.9") == 1
    assert compare_versions("0.3", "0.3.0") == 0


def test_a_newer_release_is_reported(feed):
    _Feed.payload = {"tag_name": "v0.4.0", "html_url": "https://example.test/v0.4.0"}
    data = check_for_update("0.3.4", url=feed)
    assert data["current"] == "0.3.4"
    assert data["latest"] == "0.4.0"
    assert data["newer"] is True
    assert data["url"] == "https://example.test/v0.4.0"


def test_the_same_release_is_not_newer(feed):
    _Feed.payload = {"tag_name": "0.3.4", "html_url": "https://example.test/v0.3.4"}
    assert check_for_update("0.3.4", url=feed)["newer"] is False


def test_an_older_release_is_not_newer(feed):
    _Feed.payload = {"tag_name": "v0.3.3", "html_url": "https://example.test/v0.3.3"}
    assert check_for_update("0.3.4", url=feed)["newer"] is False
