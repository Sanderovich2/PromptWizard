from __future__ import annotations

import threading

from promptwizard.config import Config
from promptwizard.errors import GUIUnavailable
from promptwizard.i18n import Translator
from promptwizard.webui.server import serve

__all__ = ["launch", "serve"]

WINDOW_TITLE = "PromptWizard"
WINDOW_SIZE = (1160, 840)
MIN_SIZE = (900, 620)


def launch(config: Config, translator: Translator, *, port: int = 0, native: bool = True) -> int:
    server, _thread, url = serve(config, translator, port=port)
    try:
        if native and _open_native_window(url):
            return 0
        return _open_in_browser(url)
    finally:
        server.shutdown()
        server.server_close()


def _open_native_window(url: str) -> bool:
    try:
        import webview
    except ImportError:
        return False
    try:
        webview.create_window(
            WINDOW_TITLE,
            url,
            width=WINDOW_SIZE[0],
            height=WINDOW_SIZE[1],
            min_size=MIN_SIZE,
            text_select=True,
        )
        webview.start()
    except Exception as exc:
        print(f"PromptWizard: cannot open a native window ({exc}); falling back to the browser.")
        return False
    return True


def _open_in_browser(url: str) -> int:
    import webbrowser

    print(f"PromptWizard is serving at {url}")
    print("Press Ctrl+C to stop.")
    if not webbrowser.open(url):
        print("Open that address in a browser to use the interface.")
    stop = threading.Event()
    try:
        stop.wait()
    except KeyboardInterrupt:
        print()
    return 0
