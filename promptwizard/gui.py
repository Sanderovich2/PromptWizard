"""Optional tkinter GUI: same pipeline as the CLI, two phases instead of one.

Phase 1 (Analyze) shows the issues and the whole question batch with an answer
field under each.  Phase 2 (Rewrite) sends the answers and shows the improved
prompt.  The split exists because a window can hold the questions open, which a
terminal cannot do comfortably.

``tkinter`` is imported lazily so that a Python build without Tk still imports
this module, and the CLI keeps working: :func:`launch` raises
:class:`~promptwizard.errors.GUIUnavailable` instead of crashing the process.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from promptwizard.config import Config
from promptwizard.errors import GUIUnavailable, PromptWizardError
from promptwizard.i18n import LANGUAGES, Translator, get_translator
from promptwizard.pipeline import Session, SessionResult
from promptwizard.questions import Question
from promptwizard.storage import save_session

__all__ = ["launch"]


def launch(config: Config, translator: Translator) -> int:
    """Start the GUI and block until the window closes.

    Raises:
        GUIUnavailable: tkinter is missing, or Tk cannot talk to a display.
    """
    try:
        import tkinter as tk
    except ImportError as exc:
        raise GUIUnavailable(
            "tkinter is not available in this Python build",
            hint_key="error.gui.unavailable",
        ) from exc
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise GUIUnavailable(
            f"cannot start Tk: {exc}",
            hint_key="error.gui.tcl",
        ) from exc
    PromptWizardWindow(root, config, translator)
    root.mainloop()
    return 0


class PromptWizardWindow:
    """The single window: prompt in, issues and questions, improved prompt out."""

    def __init__(self, root: Any, config: Config, translator: Translator) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.root = root
        self.config = config
        self.translator = translator
        self.session: Session | None = None
        self.result: SessionResult | None = None
        self.answer_entries: list[Any] = []
        self.labels: dict[str, Any] = {}
        self.buttons: dict[str, Any] = {}
        self._build()
        self._apply_texts()

    # ------------------------------------------------------------------ layout
    def _text(self, parent: Any, height: int) -> Any:
        widget = self.tk.Text(parent, height=height, wrap="word", undo=True)
        scroll = self.ttk.Scrollbar(parent, command=widget.yview)
        widget.configure(yscrollcommand=scroll.set)
        return widget, scroll

    def _build(self) -> None:
        tk, ttk = self.tk, self.ttk
        self.root.title(self.translator("gui.title"))
        self.root.minsize(760, 640)
        frame = ttk.Frame(self.root, padding=8)
        frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        top = ttk.Frame(frame)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.labels["language"] = ttk.Label(top, text="")
        self.labels["language"].grid(row=0, column=0, sticky="w")
        self.lang_var = tk.StringVar(value=self.config.lang)
        self.lang_combo = ttk.Combobox(
            top, textvariable=self.lang_var, values=list(LANGUAGES), width=6, state="readonly"
        )
        self.lang_combo.grid(row=0, column=1, sticky="w", padx=(6, 16))
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language)
        self.labels["provider"] = ttk.Label(top, text="")
        self.labels["provider"].grid(row=0, column=2, sticky="w")
        self.provider_var = tk.StringVar(value=self._provider_label())
        ttk.Label(top, textvariable=self.provider_var).grid(row=0, column=3, sticky="w", padx=(6, 16))
        self.labels["score"] = ttk.Label(top, text="")
        self.labels["score"].grid(row=0, column=4, sticky="w")
        self.score_var = tk.StringVar(value="-")
        ttk.Label(top, textvariable=self.score_var).grid(row=0, column=5, sticky="w")

        self.labels["prompt"] = ttk.Label(frame, text="")
        self.labels["prompt"].grid(row=1, column=0, sticky="w")
        prompt_text, prompt_scroll = self._text(frame, 7)
        prompt_text.grid(row=2, column=0, sticky="nsew")
        prompt_scroll.grid(row=2, column=1, sticky="ns")
        self.prompt_text = prompt_text

        actions = ttk.Frame(frame)
        actions.grid(row=3, column=0, sticky="ew", pady=6)
        self.buttons["analyze"] = ttk.Button(actions, command=self._on_analyze)
        self.buttons["analyze"].grid(row=0, column=0)
        self.buttons["rewrite"] = ttk.Button(actions, command=self._on_rewrite, state="disabled")
        self.buttons["rewrite"].grid(row=0, column=1, padx=6)
        self.buttons["save"] = ttk.Button(actions, command=self._on_save, state="disabled")
        self.buttons["save"].grid(row=0, column=2)

        self.labels["issues"] = ttk.Label(frame, text="")
        self.labels["issues"].grid(row=4, column=0, sticky="w")
        issues_text, issues_scroll = self._text(frame, 6)
        issues_text.grid(row=5, column=0, sticky="nsew")
        issues_scroll.grid(row=5, column=1, sticky="ns")
        issues_text.configure(state="disabled")
        self.issues_text = issues_text

        self.labels["questions"] = ttk.Label(frame, text="")
        self.labels["questions"].grid(row=6, column=0, sticky="w", pady=(6, 0))
        self.questions_frame = ttk.Frame(frame)
        self.questions_frame.grid(row=7, column=0, sticky="ew")
        self.questions_frame.columnconfigure(1, weight=1)

        self.labels["result"] = ttk.Label(frame, text="")
        self.labels["result"].grid(row=8, column=0, sticky="w", pady=(6, 0))
        result_text, result_scroll = self._text(frame, 7)
        result_text.grid(row=9, column=0, sticky="nsew")
        result_scroll.grid(row=9, column=1, sticky="ns")
        self.result_text = result_text

        self.labels["changes"] = ttk.Label(frame, text="")
        self.labels["changes"].grid(row=10, column=0, sticky="w", pady=(6, 0))
        changes_text, changes_scroll = self._text(frame, 4)
        changes_text.grid(row=11, column=0, sticky="nsew")
        changes_scroll.grid(row=11, column=1, sticky="ns")
        changes_text.configure(state="disabled")
        self.changes_text = changes_text

        self.status_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.status_var, foreground="#555").grid(row=12, column=0, sticky="w", pady=(6, 0))

        for row in (2, 5, 9, 11):
            frame.rowconfigure(row, weight=1)

    def _apply_texts(self) -> None:
        t = self.translator
        self.root.title(t("gui.title"))
        self.labels["language"].configure(text=t("gui.language"))
        self.labels["provider"].configure(text=t("gui.provider_label"))
        self.labels["score"].configure(text=t("gui.score_label"))
        self.labels["prompt"].configure(text=t("gui.prompt_label"))
        self.labels["issues"].configure(text=t("gui.issues_label"))
        self.labels["questions"].configure(text=t("gui.questions_label"))
        self.labels["result"].configure(text=t("gui.result_label"))
        self.labels["changes"].configure(text=t("gui.changes_label"))
        self.buttons["analyze"].configure(text=t("gui.analyze"))
        self.buttons["rewrite"].configure(text=t("gui.rewrite"))
        self.buttons["save"].configure(text=t("gui.save"))
        if not self.status_var.get():
            self.status_var.set(t("gui.ready"))

    def _provider_label(self) -> str:
        settings = self.config.provider_settings()
        model = settings.model or "-"
        return f"{self.config.provider} / {model}"

    # ------------------------------------------------------------------ events
    def _on_language(self, _event: Any = None) -> None:
        self.config.lang = self.lang_var.get()
        self.translator = get_translator(self.config.lang)
        self._apply_texts()

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.buttons["analyze"].configure(state=state)
        has_session = self.session is not None
        has_result = self.result is not None
        self.buttons["rewrite"].configure(state="normal" if (not busy and has_session) else "disabled")
        self.buttons["save"].configure(state="normal" if (not busy and has_result) else "disabled")
        self.status_var.set(self.translator("gui.busy") if busy else self.translator("gui.ready"))

    def _show_error(self, exc: BaseException) -> None:
        from tkinter import messagebox

        self._set_busy(False)
        message = getattr(exc, "message", str(exc))
        hint_key = getattr(exc, "hint_key", None)
        if hint_key:
            hint = self.translator.get(hint_key, **getattr(exc, "hint_kwargs", {}))
            if hint and hint != hint_key:
                message = f"{message}\n{hint}"
        messagebox.showerror(self.translator("gui.error"), message)
        self.status_var.set(self.translator("gui.error"))

    def _on_analyze(self) -> None:
        from tkinter import messagebox

        prompt = self.prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showinfo(self.translator("gui.title"), self.translator("gui.no_prompt"))
            return
        self._set_busy(True)

        def work() -> None:
            try:
                session = Session(self.config, self.translator, prompt)
                session.analyze()
                questions = session.make_questions()
            except BaseException as exc:  # noqa: BLE001 - reported in the UI
                self.root.after(0, self._show_error, exc)
                return
            self.root.after(0, self._show_analysis, session, questions)

        threading.Thread(target=work, daemon=True).start()

    def _show_analysis(self, session: Session, questions: tuple[Question, ...]) -> None:
        self.session = session
        self.result = None
        analysis = session.analysis
        for child in list(self.questions_frame.winfo_children()):
            child.destroy()
        self.answer_entries = []
        if analysis is not None:
            self.score_var.set(f"{analysis.score}/100")
            lines: list[str] = [analysis.summary, ""]
            for index, issue in enumerate(analysis.issues, start=1):
                lines.append(
                    self.translator(
                        "run.issue_item",
                        index=index,
                        severity=self.translator(f"severity.{issue.severity}"),
                        category=self.translator(f"category.{issue.category}"),
                        title=issue.title,
                    )
                )
                if issue.detail:
                    lines.append(self.translator("run.issue_detail", detail=issue.detail))
            if not analysis.issues:
                lines.append(self.translator("run.no_issues"))
            self._set_text(self.issues_text, "\n".join(lines))

        for index, question in enumerate(questions):
            title = self.translator("run.question_item", index=index + 1, text=question.text)
            if question.why:
                title = f"{title}\n{self.translator('run.question_why', why=question.why)}"
            if question.options:
                title = f"{title}\n{self.translator('run.question_options', options=' | '.join(question.options))}"
            self.ttk.Label(self.questions_frame, text=title, wraplength=680, justify="left").grid(
                row=index * 2, column=0, columnspan=2, sticky="w", pady=(4, 0)
            )
            entry = self.ttk.Entry(self.questions_frame)
            entry.grid(row=index * 2 + 1, column=0, columnspan=2, sticky="ew", pady=(0, 6))
            self.answer_entries.append(entry)

        if session.warnings:
            self.status_var.set(self.translator("run.template_warning", reason=session.warnings[-1]))
        self._set_busy(False)
        self.buttons["rewrite"].configure(state="normal" if questions else "disabled")

    def _on_rewrite(self) -> None:
        if self.session is None:
            return
        answers = {
            question.id: entry.get()
            for question, entry in zip(self.session.questions, self.answer_entries)
        }
        self.session.set_answers(answers)
        self._set_busy(True)

        def work() -> None:
            try:
                assert self.session is not None
                self.session.run_rewrite()
                result = self.session.result()
                save_session(self.config, result.to_dict())
            except BaseException as exc:  # noqa: BLE001 - reported in the UI
                self.root.after(0, self._show_error, exc)
                return
            self.root.after(0, self._show_rewrite, result)

        threading.Thread(target=work, daemon=True).start()

    def _show_rewrite(self, result: SessionResult) -> None:
        self.result = result
        rewrite = result.rewrite
        self._set_text(self.result_text, "" if rewrite is None else rewrite.improved_prompt)
        self._set_text(
            self.changes_text,
            "" if rewrite is None else "\n".join(self.translator("run.change_item", change=item) for item in rewrite.changes),
        )
        self._set_busy(False)
        if result.warnings:
            self.status_var.set(self.translator("run.template_warning", reason=result.warnings[-1]))
        else:
            self.status_var.set(self.translator("run.done"))

    def _on_save(self) -> None:
        from tkinter import filedialog, messagebox

        if self.result is None or self.result.rewrite is None:
            return
        path = filedialog.asksaveasfilename(
            title=self.translator("gui.save_dialog"),
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("Markdown", "*.md"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            Path(path).write_text(self.result.rewrite.improved_prompt, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror(self.translator("gui.error"), str(exc))
            return
        self.status_var.set(self.translator("gui.saved", path=path))

    @staticmethod
    def _set_text(widget: Any, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")
