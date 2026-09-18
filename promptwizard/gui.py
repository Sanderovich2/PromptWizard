from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Any

from promptwizard.config import Config
from promptwizard.errors import GUIUnavailable
from promptwizard.i18n import LANGUAGES, Translator, get_translator
from promptwizard.pipeline import Session, SessionResult
from promptwizard.questions import Question
from promptwizard.storage import save_session

__all__ = ["launch"]

POLL_MS = 100
PAD = 12


def launch(config: Config, translator: Translator) -> int:
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
        raise GUIUnavailable(f"cannot start Tk: {exc}", hint_key="error.gui.tcl") from exc
    PromptWizardWindow(root, config, translator)
    root.mainloop()
    return 0


class PromptWizardWindow:
    TAB_PROMPT = 0
    TAB_ANALYSIS = 1
    TAB_QUESTIONS = 2
    TAB_RESULT = 3

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
        self._events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._font = self._pick_font()
        self._setup_style()
        self._build()
        self._apply_texts()
        self._drain()

    def _pick_font(self) -> str:
        from tkinter import font as tkfont

        families = set(tkfont.families(self.root))
        for name in ("Segoe UI", "Helvetica Neue", "DejaVu Sans", "Arial", "Liberation Sans"):
            if name in families:
                return name
        return "TkDefaultFont"

    def _setup_style(self) -> None:
        style = self.ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        font = self._font
        self.root.configure(background="#f4f5f7")
        style.configure(".", background="#f4f5f7", font=(font, 10))
        style.configure("TFrame", background="#f4f5f7")
        style.configure("TLabel", background="#f4f5f7")
        style.configure("Title.TLabel", font=(font, 15, "bold"), background="#f4f5f7")
        style.configure("Muted.TLabel", foreground="#5b6470", background="#f4f5f7", font=(font, 9))
        style.configure("Section.TLabel", font=(font, 10, "bold"), background="#f4f5f7")
        style.configure("TButton", padding=(12, 6))
        style.configure("Accent.TButton", font=(font, 10, "bold"), padding=(16, 7))
        style.configure("TNotebook", background="#f4f5f7", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 8), font=(font, 10))
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#ffffff")],
            foreground=[("selected", "#111418")],
        )

    def _text(self, parent: Any, height: int, *, readonly: bool = False) -> tuple[Any, Any]:
        widget = self.tk.Text(
            parent,
            height=height,
            wrap="word",
            undo=not readonly,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#d9dde3",
            highlightcolor="#4a7dff",
            padx=8,
            pady=8,
            font=(self._font, 10),
            background="#ffffff",
        )
        scroll = self.ttk.Scrollbar(parent, command=widget.yview)
        widget.configure(yscrollcommand=scroll.set)
        if readonly:
            widget.configure(state="disabled")
        return (widget, scroll)

    def _build(self) -> None:
        tk, ttk = (self.tk, self.ttk)
        self.root.title(self.translator("gui.title"))
        self.root.minsize(820, 620)

        outer = ttk.Frame(self.root, padding=PAD)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, PAD))
        header.columnconfigure(0, weight=1)
        self.labels["title"] = ttk.Label(header, text="", style="Title.TLabel")
        self.labels["title"].grid(row=0, column=0, sticky="w")
        self.labels["subtitle"] = ttk.Label(header, text="", style="Muted.TLabel")
        self.labels["subtitle"].grid(row=1, column=0, sticky="w")

        controls = ttk.Frame(header)
        controls.grid(row=0, column=1, rowspan=2, sticky="e")
        self.labels["language"] = ttk.Label(controls, text="")
        self.labels["language"].grid(row=0, column=0, sticky="e", padx=(0, 6))
        self.lang_var = tk.StringVar(value=self.config.lang)
        self.lang_combo = ttk.Combobox(
            controls, textvariable=self.lang_var, values=list(LANGUAGES), width=5, state="readonly"
        )
        self.lang_combo.grid(row=0, column=1, sticky="e", padx=(0, 16))
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language)
        self.labels["provider"] = ttk.Label(controls, text="")
        self.labels["provider"].grid(row=0, column=2, sticky="e", padx=(0, 6))
        self.provider_var = tk.StringVar(value=self._provider_label())
        ttk.Label(controls, textvariable=self.provider_var, style="Muted.TLabel").grid(
            row=0, column=3, sticky="e"
        )

        self.notebook = ttk.Notebook(outer)
        self.notebook.grid(row=2, column=0, sticky="nsew")

        prompt_tab = ttk.Frame(self.notebook, padding=PAD)
        analysis_tab = ttk.Frame(self.notebook, padding=PAD)
        questions_tab = ttk.Frame(self.notebook, padding=PAD)
        result_tab = ttk.Frame(self.notebook, padding=PAD)
        for tab in (prompt_tab, analysis_tab, questions_tab, result_tab):
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(1, weight=1)
            self.notebook.add(tab, text="")

        self.labels["prompt"] = ttk.Label(prompt_tab, text="", style="Section.TLabel")
        self.labels["prompt"].grid(row=0, column=0, sticky="w", pady=(0, 6))
        prompt_text, prompt_scroll = self._text(prompt_tab, 16)
        prompt_text.grid(row=1, column=0, sticky="nsew")
        prompt_scroll.grid(row=1, column=1, sticky="ns")
        self.prompt_text = prompt_text
        self.labels["prompt_hint"] = ttk.Label(prompt_tab, text="", style="Muted.TLabel")
        self.labels["prompt_hint"].grid(row=2, column=0, sticky="w", pady=(6, 0))

        self.labels["analysis"] = ttk.Label(analysis_tab, text="", style="Section.TLabel")
        self.labels["analysis"].grid(row=0, column=0, sticky="w", pady=(0, 6))
        analysis_text, analysis_scroll = self._text(analysis_tab, 16, readonly=True)
        analysis_text.grid(row=1, column=0, sticky="nsew")
        analysis_scroll.grid(row=1, column=1, sticky="ns")
        self.issues_text = analysis_text
        self.score_var = tk.StringVar(value="-")
        score_row = ttk.Frame(analysis_tab)
        score_row.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self.labels["score"] = ttk.Label(score_row, text="", style="Muted.TLabel")
        self.labels["score"].grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Label(score_row, textvariable=self.score_var, style="Section.TLabel").grid(
            row=0, column=1, sticky="w"
        )

        self.labels["questions"] = ttk.Label(questions_tab, text="", style="Section.TLabel")
        self.labels["questions"].grid(row=0, column=0, sticky="w", pady=(0, 6))
        questions_canvas = tk.Canvas(
            questions_tab, highlightthickness=0, background="#ffffff", borderwidth=0
        )
        questions_scroll = self.ttk.Scrollbar(questions_tab, command=questions_canvas.yview)
        questions_canvas.configure(yscrollcommand=questions_scroll.set)
        questions_canvas.grid(row=1, column=0, sticky="nsew")
        questions_scroll.grid(row=1, column=1, sticky="ns")
        self.questions_canvas = questions_canvas
        self.questions_frame = ttk.Frame(questions_canvas, padding=8)
        self._questions_window = questions_canvas.create_window(
            (0, 0), window=self.questions_frame, anchor="nw"
        )
        self.questions_frame.bind(
            "<Configure>",
            lambda event: questions_canvas.configure(scrollregion=questions_canvas.bbox("all")),
        )
        questions_canvas.bind(
            "<Configure>",
            lambda event: questions_canvas.itemconfigure(self._questions_window, width=event.width),
        )
        questions_canvas.bind("<Enter>", self._bind_wheel)
        questions_canvas.bind("<Leave>", self._unbind_wheel)
        self.labels["questions_empty"] = ttk.Label(questions_tab, text="", style="Muted.TLabel")
        self.labels["questions_empty"].grid(row=2, column=0, sticky="w", pady=(6, 0))

        self.labels["result"] = ttk.Label(result_tab, text="", style="Section.TLabel")
        self.labels["result"].grid(row=0, column=0, sticky="w", pady=(0, 6))
        result_text, result_scroll = self._text(result_tab, 16, readonly=True)
        result_text.grid(row=1, column=0, sticky="nsew")
        result_scroll.grid(row=1, column=1, sticky="ns")
        self.result_text = result_text
        result_actions = ttk.Frame(result_tab)
        result_actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.buttons["copy"] = ttk.Button(result_actions, command=self._on_copy, state="disabled")
        self.buttons["copy"].grid(row=0, column=0)
        self.buttons["save"] = ttk.Button(result_actions, command=self._on_save, state="disabled")
        self.buttons["save"].grid(row=0, column=1, padx=6)

        self.labels["changes"] = ttk.Label(outer, text="", style="Section.TLabel")
        self.labels["changes"].grid(row=3, column=0, sticky="w", pady=(PAD, 4))
        changes_text, changes_scroll = self._text(outer, 5, readonly=True)
        changes_text.grid(row=4, column=0, sticky="ew")
        changes_scroll.grid(row=4, column=1, sticky="ns")
        self.changes_text = changes_text
        outer.rowconfigure(4, weight=0)

        actions = ttk.Frame(outer)
        actions.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(PAD, 0))
        actions.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="")
        ttk.Label(actions, textvariable=self.status_var, style="Muted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.buttons["analyze"] = ttk.Button(actions, command=self._on_analyze)
        self.buttons["analyze"].grid(row=0, column=1)
        self.buttons["rewrite"] = ttk.Button(
            actions, command=self._on_rewrite, style="Accent.TButton", state="disabled"
        )
        self.buttons["rewrite"].grid(row=0, column=2, padx=(6, 0))

    def _bind_wheel(self, _event: Any = None) -> None:
        self.questions_canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _event: Any = None) -> None:
        self.questions_canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event: Any) -> None:
        try:
            self.questions_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _apply_texts(self) -> None:
        t = self.translator
        self.root.title(t("gui.title"))
        self.labels["title"].configure(text=t("app.name"))
        self.labels["subtitle"].configure(text=t("app.tagline"))
        self.labels["language"].configure(text=t("gui.language"))
        self.labels["provider"].configure(text=t("gui.provider_label"))
        self.labels["prompt"].configure(text=t("gui.prompt_label"))
        self.labels["prompt_hint"].configure(text=t("gui.prompt_hint"))
        self.labels["analysis"].configure(text=t("gui.issues_label"))
        self.labels["score"].configure(text=t("gui.score_label"))
        self.labels["questions"].configure(text=t("gui.questions_label"))
        self.labels["questions_empty"].configure(text=t("gui.no_questions"))
        self.labels["result"].configure(text=t("gui.result_label"))
        self.labels["changes"].configure(text=t("gui.changes_label"))
        self.notebook.tab(self.TAB_PROMPT, text=t("gui.tab_prompt"))
        self.notebook.tab(self.TAB_ANALYSIS, text=t("gui.tab_analysis"))
        self.notebook.tab(self.TAB_QUESTIONS, text=t("gui.tab_questions"))
        self.notebook.tab(self.TAB_RESULT, text=t("gui.tab_result"))
        self.buttons["analyze"].configure(text=t("gui.analyze"))
        self.buttons["rewrite"].configure(text=t("gui.rewrite"))
        self.buttons["copy"].configure(text=t("gui.copy"))
        self.buttons["save"].configure(text=t("gui.save"))
        if not self.status_var.get():
            self.status_var.set(t("gui.ready"))

    def _provider_label(self) -> str:
        settings = self.config.provider_settings()
        model = settings.model or "-"
        return f"{self.config.provider} / {model}"

    def _on_language(self, _event: Any = None) -> None:
        self.config.lang = self.lang_var.get()
        self.translator = get_translator(self.config.lang)
        self._apply_texts()

    def _set_busy(self, busy: bool) -> None:
        self.buttons["analyze"].configure(state="disabled" if busy else "normal")
        ready = not busy and self.session is not None
        self.buttons["rewrite"].configure(state="normal" if ready else "disabled")
        ready_save = not busy and self.result is not None
        self.buttons["save"].configure(state="normal" if ready_save else "disabled")
        self.buttons["copy"].configure(state="normal" if ready_save else "disabled")
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

    def _drain(self) -> None:
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "analysis":
                    self._show_analysis(*payload)
                elif kind == "rewrite":
                    self._show_rewrite(*payload)
                elif kind == "error":
                    self._show_error(payload)
        except queue.Empty:
            pass
        self.root.after(POLL_MS, self._drain)

    def _on_analyze(self) -> None:
        from tkinter import messagebox

        prompt = self.prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showinfo(self.translator("gui.title"), self.translator("gui.no_prompt"))
            return
        self.session = None
        self.result = None
        self._set_busy(True)
        self.notebook.select(self.TAB_ANALYSIS)
        config = self.config
        translator = self.translator
        events = self._events

        def work() -> None:
            try:
                session = Session(config, translator, prompt)
                session.analyze()
                questions = session.make_questions()
            except BaseException as exc:
                events.put(("error", exc))
                return
            events.put(("analysis", (session, questions)))

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
                title = (
                    f"{title}\n{self.translator('run.question_options', options=' | '.join(question.options))}"
                )
            self.ttk.Label(
                self.questions_frame,
                text=title,
                wraplength=720,
                justify="left",
                background="#ffffff",
            ).grid(row=index * 2, column=0, sticky="w", padx=6, pady=(6, 0))
            entry = self.ttk.Entry(self.questions_frame)
            entry.grid(row=index * 2 + 1, column=0, sticky="ew", padx=6, pady=(0, 6))
            self.answer_entries.append(entry)
        self.questions_frame.columnconfigure(0, weight=1)
        self.questions_canvas.configure(scrollregion=self.questions_canvas.bbox("all"))
        self.labels["questions_empty"].configure(
            text="" if questions else self.translator("gui.no_questions")
        )
        if session.warnings:
            self.status_var.set(self.translator("run.template_warning", reason=session.warnings[-1]))
        self._set_busy(False)
        self.notebook.select(self.TAB_QUESTIONS if questions else self.TAB_ANALYSIS)

    def _on_rewrite(self) -> None:
        if self.session is None:
            return
        answers = {
            question.id: entry.get() for question, entry in zip(self.session.questions, self.answer_entries)
        }
        self.session.set_answers(answers)
        self._set_busy(True)
        session = self.session
        config = self.config
        events = self._events

        def work() -> None:
            try:
                session.run_rewrite()
                result = session.result()
                save_session(config, result.to_dict())
            except BaseException as exc:
                events.put(("error", exc))
                return
            events.put(("rewrite", (result,)))

        threading.Thread(target=work, daemon=True).start()

    def _show_rewrite(self, result: SessionResult) -> None:
        self.result = result
        rewrite = result.rewrite
        self._set_text(self.result_text, "" if rewrite is None else rewrite.improved_prompt)
        self._set_text(
            self.changes_text,
            ""
            if rewrite is None
            else "\n".join(self.translator("run.change_item", change=item) for item in rewrite.changes),
        )
        self._set_busy(False)
        self.notebook.select(self.TAB_RESULT)
        self.result_text.see("1.0")
        if result.warnings:
            self.status_var.set(self.translator("run.template_warning", reason=result.warnings[-1]))
        else:
            self.status_var.set(self.translator("run.done"))

    def _improved(self) -> str:
        if self.result is None or self.result.rewrite is None:
            return ""
        return self.result.rewrite.improved_prompt

    def _on_copy(self) -> None:
        text = self._improved()
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set(self.translator("gui.copied"))

    def _on_save(self) -> None:
        from tkinter import filedialog, messagebox

        text = self._improved()
        if not text:
            return
        path = filedialog.asksaveasfilename(
            title=self.translator("gui.save_dialog"),
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("Markdown", "*.md"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8")
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
