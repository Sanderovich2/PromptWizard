from __future__ import annotations

import time

import pytest

from promptwizard.config import Config
from promptwizard.i18n import get_translator

pytest.importorskip("tkinter", reason="tkinter is not available in this Python build")


def _open_window(tmp_path):
    import tkinter as tk
    import tkinter.messagebox as messagebox

    from promptwizard.gui import PromptWizardWindow

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display for Tk: {exc}")

    dialogs: list[str] = []
    original = (messagebox.showerror, messagebox.showinfo)

    def record(kind):
        def inner(title=None, message=None, **kwargs):
            dialogs.append(f"{kind}: {title} | {message}")

        return inner

    messagebox.showerror = record("showerror")
    messagebox.showinfo = record("showinfo")

    config = Config.load(home=tmp_path, dotenv=False)
    config.provider = "offline"
    window = PromptWizardWindow(root, config, get_translator("en"))
    return root, window, dialogs, original


def _close(root, original):
    import tkinter.messagebox as messagebox

    messagebox.showerror, messagebox.showinfo = original
    root.destroy()


def _pump(root, seconds, stop_when):
    deadline = time.time() + seconds
    while time.time() < deadline:
        root.update()
        time.sleep(0.02)
        if stop_when():
            return True
    return False


def _enabled(button) -> bool:
    return bool(button.instate(["!disabled"]))


def test_gui_completes_the_whole_flow(tmp_path):
    root, window, dialogs, original = _open_window(tmp_path)
    try:
        window.prompt_text.insert("1.0", "Write something about cats")
        window._on_analyze()
        assert _pump(root, 30, lambda: window.session is not None), (
            f"the analysis never reached the UI (worker result was lost): {dialogs}"
        )
        assert dialogs == []
        assert window.session.analysis is not None
        assert window.answer_entries, "the question batch was not rendered"
        assert _enabled(window.buttons["rewrite"])
        assert window.questions_canvas.cget("scrollregion"), "the question list is not scrollable"

        for entry in window.answer_entries:
            entry.insert(0, "a short paragraph")

        window._on_rewrite()
        assert _pump(root, 30, lambda: window.result is not None), (
            f"the rewrite never reached the UI (worker result was lost): {dialogs}"
        )
        assert dialogs == []
        assert window.result.rewrite is not None
        assert window.result_text.get("1.0", "end").strip(), "the improved prompt is not shown"
        assert window.changes_text.get("1.0", "end").strip()
        assert window.notebook.index("current") == window.TAB_RESULT
        assert _enabled(window.buttons["copy"])
        assert _enabled(window.buttons["save"])
    finally:
        _close(root, original)


def test_gui_still_rewrites_when_the_model_asks_nothing(tmp_path, monkeypatch):
    root, window, dialogs, original = _open_window(tmp_path)
    try:
        from promptwizard.pipeline import Session

        monkeypatch.setattr(Session, "make_questions", lambda self, **kwargs: ())

        window.prompt_text.insert("1.0", "Write something about cats")
        window._on_analyze()
        assert _pump(root, 30, lambda: window.session is not None), f"no analysis: {dialogs}"
        assert window.answer_entries == []
        assert _enabled(window.buttons["rewrite"]), (
            "with no questions the rewrite must still be reachable, otherwise the improved "
            "prompt can never be produced"
        )
        window._on_rewrite()
        assert _pump(root, 30, lambda: window.result is not None), f"no rewrite: {dialogs}"
        assert window.result_text.get("1.0", "end").strip()
    finally:
        _close(root, original)


def test_gui_asks_for_a_prompt_when_the_field_is_empty(tmp_path):
    root, window, dialogs, original = _open_window(tmp_path)
    try:
        window._on_analyze()
        assert dialogs, "an empty prompt must tell the user what is missing"
        assert window.session is None
    finally:
        _close(root, original)


def test_gui_has_four_tabs(tmp_path):
    root, window, dialogs, original = _open_window(tmp_path)
    try:
        assert window.notebook.index("end") == 4
    finally:
        _close(root, original)
