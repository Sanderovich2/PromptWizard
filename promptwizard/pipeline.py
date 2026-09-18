from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence
from promptwizard import __version__
from promptwizard.analyzer import Analysis, Issue
from promptwizard.analyzer import build_system_prompt as analysis_system
from promptwizard.analyzer import build_user_prompt as analysis_user
from promptwizard.analyzer import heuristic as analysis_heuristic
from promptwizard.analyzer import parse as analysis_parse
from promptwizard.config import Config
from promptwizard.errors import LLMResponseError, ProviderError
from promptwizard.i18n import LANGUAGES, Translator, detect_text_language, get_translator
from promptwizard.llm.base import LLMProvider, LLMRequest
from promptwizard.llm.registry import build_provider
from promptwizard.questions import Question
from promptwizard.questions import build_system_prompt as questions_system
from promptwizard.questions import build_user_prompt as questions_user
from promptwizard.questions import heuristic as questions_heuristic
from promptwizard.questions import parse as questions_parse
from promptwizard.rewriter import Rewrite
from promptwizard.rewriter import build_system_prompt as rewrite_system
from promptwizard.rewriter import build_user_prompt as rewrite_user
from promptwizard.rewriter import heuristic as rewrite_heuristic
from promptwizard.rewriter import parse as rewrite_parse
from promptwizard.translate import build_system_prompt as translate_system
from promptwizard.translate import build_user_prompt as translate_user
from promptwizard.translate import parse as translate_parse
from promptwizard.usage import estimate_tokens
__all__ = ['Session', 'SessionResult', 'AskCallback', 'run', 'new_session_id']
AskCallback = Callable[[Sequence[Question]], Mapping[str, str]]
MODE_LLM = 'llm'
MODE_TEMPLATE = 'template'
MODE_OFFLINE = 'offline'

def new_session_id() -> str:
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    return f'{stamp}-{uuid.uuid4().hex[:6]}'

def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')

@dataclass
class SessionResult:
    id: str
    started_at: str
    finished_at: str
    provider: str
    model: str
    mode: str
    prompt_language: str
    ui_language: str
    original_prompt: str
    analysis: Analysis
    questions: tuple[Question, ...] = ()
    answers: dict[str, str] = field(default_factory=dict)
    rewrite: Rewrite | None = None
    warnings: tuple[str, ...] = ()
    translated_prompt: str = ''
    duration_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    version: str = __version__

    def to_dict(self) -> dict[str, Any]:
        return {'id': self.id, 'version': self.version, 'started_at': self.started_at, 'finished_at': self.finished_at, 'provider': self.provider, 'model': self.model, 'mode': self.mode, 'prompt_language': self.prompt_language, 'ui_language': self.ui_language, 'original_prompt': self.original_prompt, 'analysis': {'language': self.analysis.language, 'score': self.analysis.score, 'summary': self.analysis.summary, 'issues': [{'category': issue.category, 'severity': issue.severity, 'title': issue.title, 'detail': issue.detail, 'evidence': issue.evidence} for issue in self.analysis.issues]}, 'questions': [{'id': question.id, 'text': question.text, 'why': question.why, 'kind': question.kind, 'options': list(question.options)} for question in self.questions], 'answers': dict(self.answers), 'translated_prompt': self.translated_prompt, 'rewrite': None if self.rewrite is None else {'improved_prompt': self.rewrite.improved_prompt, 'changes': list(self.rewrite.changes), 'language': self.rewrite.language}, 'duration_ms': self.duration_ms, 'tokens_in': self.tokens_in, 'tokens_out': self.tokens_out, 'warnings': list(self.warnings)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> 'SessionResult':
        analysis_raw = data.get('analysis') or {}
        issues = tuple((Issue(category=str(entry.get('category', 'clarity')), severity=str(entry.get('severity', 'medium')), title=str(entry.get('title', '')), detail=str(entry.get('detail', '')), evidence=str(entry.get('evidence', ''))) for entry in analysis_raw.get('issues', []) if isinstance(entry, Mapping)))
        analysis = Analysis(language=str(analysis_raw.get('language', 'unknown')), score=int(analysis_raw.get('score', 0) or 0), summary=str(analysis_raw.get('summary', '')), issues=issues)
        questions = tuple((Question(id=str(entry.get('id', '')), text=str(entry.get('text', '')), why=str(entry.get('why', '')), kind=str(entry.get('kind', 'free')), options=tuple((str(option) for option in entry.get('options', [])))) for entry in data.get('questions', []) if isinstance(entry, Mapping)))
        rewrite_raw = data.get('rewrite')
        rewrite = None
        if isinstance(rewrite_raw, Mapping):
            rewrite = Rewrite(improved_prompt=str(rewrite_raw.get('improved_prompt', '')), changes=tuple((str(change) for change in rewrite_raw.get('changes', []))), language=str(rewrite_raw.get('language', 'unknown')))
        return cls(id=str(data.get('id', '')), started_at=str(data.get('started_at', '')), finished_at=str(data.get('finished_at', '')), provider=str(data.get('provider', '')), model=str(data.get('model', '')), mode=str(data.get('mode', MODE_LLM)), prompt_language=str(data.get('prompt_language', 'unknown')), ui_language=str(data.get('ui_language', 'ru')), original_prompt=str(data.get('original_prompt', '')), analysis=analysis, questions=questions, answers={str(key): str(value) for key, value in (data.get('answers') or {}).items()}, translated_prompt=str(data.get('translated_prompt', '')), rewrite=rewrite, duration_ms=_as_count(data.get('duration_ms')), tokens_in=_as_count(data.get('tokens_in')), tokens_out=_as_count(data.get('tokens_out')), warnings=tuple((str(item) for item in data.get('warnings', []))), version=str(data.get('version', '0')))

    @property
    def mode_label(self) -> str:
        return self.mode

def _as_count(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0

def _elapsed_ms(started_at: str) -> int:
    try:
        started = datetime.fromisoformat(started_at)
    except (TypeError, ValueError):
        return 0
    return max(0, int((datetime.now().astimezone() - started).total_seconds() * 1000))

def _try_complete(provider: LLMProvider, translator: Translator, request: LLMRequest) -> tuple[str | None, str | None]:
    try:
        return (provider.complete(request).text, None)
    except ProviderError as exc:
        reason = getattr(exc, 'message', str(exc))
        hint_key = getattr(exc, 'hint_key', None)
        if hint_key:
            hint = translator.get(hint_key, **getattr(exc, 'hint_kwargs', {}))
            if hint and hint != hint_key:
                reason = f'{reason}. {hint}'
        return (None, reason)
    except ValueError as exc:
        return (None, str(exc))

class Session:

    def __init__(self, config: Config, translator: Translator, prompt: str, *, provider: LLMProvider | None=None, allow_fallback: bool=True) -> None:
        self.config = config
        self.translator = translator
        self.prompt = prompt
        self.provider = provider or build_provider(config)
        self.allow_fallback = allow_fallback
        self.started_at = _now()
        self.warnings: list[str] = []
        language = detect_text_language(prompt)
        self.prompt_language = language if language in LANGUAGES else config.lang
        self.prompt_translator = get_translator(self.prompt_language)
        self.offline = self.provider.kind == 'offline'
        self.analysis: Analysis | None = None
        self.questions: tuple[Question, ...] = ()
        self.answers: dict[str, str] = {}
        self.rewrite: Rewrite | None = None
        self.translated_prompt: str | None = None
        self.tokens_in = 0
        self.tokens_out = 0

    @property
    def analyzed_prompt(self) -> str:
        return self.translated_prompt or self.prompt

    def ensure_translation(self, target_language: str) -> str:
        if self.offline or (not self.config.translate_prompt) or self.prompt_language == target_language:
            return ''
        if self.translated_prompt is not None:
            return self.translated_prompt
        request = LLMRequest(prompt=translate_user(self.prompt), system=translate_system(self.translator, target_language, self.config.system_analyzer), json_mode=True)
        text, reason = self._complete(request)
        translation = ''
        if text:
            try:
                translation = translate_parse(text)
            except LLMResponseError as exc:
                reason = getattr(exc, 'message', str(exc))
        if not translation:
            self.translated_prompt = ''
            if reason:
                self.warnings.append(reason)
            return ''
        self.translated_prompt = translation
        return translation

    def _complete(self, request: LLMRequest) -> tuple[str | None, str | None]:
        text, reason = _try_complete(self.provider, self.translator, request)
        self.tokens_in += estimate_tokens(request.system) + estimate_tokens(request.prompt)
        self.tokens_out += estimate_tokens(text or '')
        return (text, reason)

    def analyze(self) -> Analysis:
        if self.analysis is not None:
            return self.analysis
        self.ensure_translation(self.config.lang)
        analysis: Analysis | None = None
        if not self.offline:
            request = LLMRequest(prompt=analysis_user(self.analyzed_prompt), system=analysis_system(self.translator, self.config.system_analyzer), json_mode=True)
            text, reason = self._complete(request)
            if text:
                try:
                    analysis = analysis_parse(text, self.prompt_language)
                except LLMResponseError as exc:
                    reason = getattr(exc, 'message', str(exc))
            if analysis is None:
                if not self.allow_fallback and reason:
                    raise ProviderError(reason)
                self.warnings.append(reason or 'analysis: the model returned no usable answer')
        if analysis is None:
            analysis = analysis_heuristic(self.prompt, self.prompt_language, self.translator)
        self.analysis = analysis
        return analysis

    def make_questions(self, *, limit: int | None=None, no_questions: bool=False) -> tuple[Question, ...]:
        if self.questions:
            return self.questions
        if no_questions:
            return ()
        analysis = self.analyze()
        effective_limit = self.config.max_questions if limit is None else int(limit)
        if effective_limit <= 0:
            return ()
        self.ensure_translation(self.config.lang)
        questions: tuple[Question, ...] = ()
        if self.offline:
            questions = questions_heuristic(self.prompt, analysis, self.translator, effective_limit)
        else:
            request = LLMRequest(prompt=questions_user(self.analyzed_prompt, analysis), system=questions_system(self.translator, effective_limit), json_mode=True)
            text, reason = self._complete(request)
            if text:
                try:
                    questions = questions_parse(text, effective_limit)
                except LLMResponseError:
                    questions = ()
            if not questions:
                questions = questions_heuristic(self.prompt, analysis, self.translator, effective_limit)
                if reason:
                    self.warnings.append(reason)
        self.questions = questions
        return questions

    def set_answers(self, answers: Mapping[str, str] | None) -> None:
        self.answers = {str(key): str(value) for key, value in (answers or {}).items() if str(value).strip()}

    def run_rewrite(self) -> Rewrite:
        if self.rewrite is not None:
            return self.rewrite
        analysis = self.analyze()
        rewrite: Rewrite | None = None
        if not self.offline:
            request = LLMRequest(prompt=rewrite_user(self.prompt, analysis, self.questions, self.answers), system=rewrite_system(self.translator, self.prompt_language, self.config.system_rewriter), json_mode=True)
            text, reason = self._complete(request)
            if text:
                try:
                    rewrite = rewrite_parse(text, self.prompt_language)
                except LLMResponseError as exc:
                    reason = getattr(exc, 'message', str(exc))
            if rewrite is None:
                if not self.allow_fallback and reason:
                    raise ProviderError(reason)
                self.warnings.append(reason or 'rewrite: the model returned no usable answer')
        if rewrite is None:
            rewrite = rewrite_heuristic(self.prompt, analysis, self.answers, self.prompt_translator, self.translator)
        self.rewrite = rewrite
        return rewrite

    def mode(self) -> str:
        if self.offline:
            return MODE_OFFLINE
        if self.warnings:
            return MODE_TEMPLATE
        return MODE_LLM

    def result(self) -> SessionResult:
        analysis = self.analysis or self.analyze()
        return SessionResult(id=new_session_id(), started_at=self.started_at, finished_at=_now(), duration_ms=_elapsed_ms(self.started_at), provider=self.provider.name, model=self.provider.model or '-', mode=self.mode(), prompt_language=self.prompt_language, ui_language=self.config.lang, original_prompt=self.prompt, analysis=analysis, questions=self.questions, answers=dict(self.answers), rewrite=self.rewrite, warnings=tuple(self.warnings), translated_prompt=self.translated_prompt or '', tokens_in=self.tokens_in, tokens_out=self.tokens_out)

def run(config: Config, translator: Translator, prompt: str, *, provider: LLMProvider | None=None, ask: AskCallback | None=None, max_questions: int | None=None, no_questions: bool=False, allow_fallback: bool=True) -> SessionResult:
    session = Session(config, translator, prompt, provider=provider, allow_fallback=allow_fallback)
    session.analyze()
    questions = session.make_questions(limit=max_questions, no_questions=no_questions)
    if ask is not None and questions:
        session.set_answers(ask(questions))
    session.run_rewrite()
    return session.result()
