from __future__ import annotations

import re
from importlib import resources

from promptwizard import __version__


def _asset(name: str) -> str:
    return resources.files("promptwizard.webui").joinpath("assets", name).read_text(encoding="utf-8")


def test_every_id_the_script_uses_exists_in_the_page():
    """The regression that blanked the whole interface: the script wrote to an
    element the page no longer had, so the render threw and no label was filled."""
    html = _asset("index.html")
    script = _asset("app.js")
    page_ids = set(re.findall(r'id="([A-Za-z0-9_-]+)"', html))
    used = set(re.findall(r'\$\("([A-Za-z0-9_-]+)"\)', script))
    missing = sorted(used - page_ids)
    assert not missing, f"app.js refers to ids the page does not define: {missing}"


def test_asset_urls_carry_the_package_version():
    html = _asset("index.html")
    assert "app.js?v={{v}}" in html
    assert "app.css?v={{v}}" in html
    assert f"app.js?v={__version__}" not in html


def test_the_stylesheet_stays_balanced():
    css = _asset("app.css")
    assert css.count("{") == css.count("}")


def test_motion_respects_reduced_motion():
    css = _asset("app.css")
    if "pw-fade" in css:
        assert "prefers-reduced-motion" in css
