from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from typing import Any
from urllib.parse import parse_qs, urlsplit

from promptwizard import __version__
from promptwizard.batch import run_batch, split_prompts
from promptwizard.config import THEMES, Config
from promptwizard.drafts import add_draft, clear_drafts as drop_all_drafts, list_drafts, remove_draft
from promptwizard.errors import PromptWizardError
from promptwizard.export import autosave_result
from promptwizard.i18n import LANGUAGES, Translator, get_translator, load_catalog, normalize_language
from promptwizard.llm.registry import describe_providers
from promptwizard.pipeline import Session, SessionResult
from promptwizard.settings import available_models, save_settings, settings_view
from promptwizard.settings import open_config as open_settings_file
from promptwizard.storage import save_session
from promptwizard.update import check_for_update

CONTENT_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.json': 'application/json; charset=utf-8',
}


def _asset(name: str) -> tuple[bytes, str]:
    suffix = name[name.rfind('.'):] if '.' in name else ''
    resource = resources.files('promptwizard.webui').joinpath('assets', name)
    data = resource.read_bytes()
    if name == 'index.html':
        data = data.replace(b'{{v}}', __version__.encode('ascii'))
    return data, CONTENT_TYPES.get(suffix, 'application/octet-stream')


def _hint(translator: Translator, exc: PromptWizardError) -> str:
    if not exc.hint_key:
        return ''
    value = translator.get(exc.hint_key, **exc.hint_kwargs)
    return '' if value == exc.hint_key else value


def _settings_error(translator: Translator, exc: PromptWizardError) -> dict[str, Any]:
    return {'error': {'message': exc.message, 'hint': _hint(translator, exc)}}


def _analysis_json(analysis: Any) -> dict[str, Any]:
    return {
        'language': analysis.language,
        'score': analysis.score,
        'summary': analysis.summary,
        'issues': [
            {
                'category': issue.category,
                'severity': issue.severity,
                'title': issue.title,
                'detail': issue.detail,
                'evidence': issue.evidence,
            }
            for issue in analysis.issues
        ],
    }


def _result_json(result: SessionResult, saved: str='') -> dict[str, Any]:
    rewrite = result.rewrite
    return {
        'id': result.id,
        'mode': result.mode,
        'warnings': list(result.warnings),
        'provider': result.provider,
        'model': result.model,
        'language': result.prompt_language,
        'original_prompt': result.original_prompt,
        'translation': result.translated_prompt,
        'stats': {
            'duration_ms': result.duration_ms,
            'tokens_in': result.tokens_in,
            'tokens_out': result.tokens_out,
            'tokens_total': result.tokens_in + result.tokens_out,
        },
        'saved': saved,
        'rewrite': None
        if rewrite is None
        else {
            'improved_prompt': rewrite.improved_prompt,
            'changes': list(rewrite.changes),
            'language': rewrite.language,
        },
    }


class AppState:
    def __init__(self, config: Config, translator: Translator) -> None:
        self.config = config
        self.translator = translator
        self.sessions: dict[str, Session] = {}
        self.lock = threading.Lock()

    def state(self, lang: str | None=None) -> dict[str, Any]:
        requested = normalize_language(lang) if lang else self.config.lang
        return {
            'version': __version__,
            'lang': requested,
            'languages': list(LANGUAGES),
            'themes': list(THEMES),
            'strings': load_catalog(requested),
            'settings': settings_view(self.config),
            'provider': self.config.provider,
            'model': self.config.provider_settings().model,
        }

    def models(self, provider: str | None=None) -> dict[str, Any]:
        return available_models(self.config, provider)

    def providers(self) -> dict[str, Any]:
        return {'providers': [
            {
                'name': status.name,
                'available': status.available,
                'detail': status.detail,
                'models': list(status.models),
                'requires_key': status.requires_key,
                'key_present': status.key_present,
            }
            for status in describe_providers(self.config)
        ]}

    def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        for key in ('lang', 'theme', 'provider', 'model', 'temperature', 'max_tokens', 'timeout', 'max_questions', 'font', 'font_size', 'system_analyzer', 'system_rewriter', 'auto_copy', 'autosave_dir', 'theme_day_start', 'theme_night_start', 'translate_prompt', 'check_updates'):
            if key not in payload:
                continue
            value = payload[key]
            if key in ('system_analyzer', 'system_rewriter', 'autosave_dir'):
                updates[key] = '' if value is None else str(value)
            elif key in ('auto_copy', 'translate_prompt', 'check_updates'):
                updates[key] = bool(value)
            elif value not in (None, ''):
                updates[key] = value
        blocks: dict[str, Any] = {}
        custom = payload.get('providers')
        if custom:
            if not isinstance(custom, dict):
                raise ValueError('providers must be an object')
            blocks.update({str(name): dict(block) for name, block in custom.items()})
        model = payload.get('model')
        if model:
            target = str(payload.get('provider') or self.config.provider)
            blocks.setdefault(target, {})['model'] = model
        if blocks:
            updates['providers'] = blocks
        if not updates:
            raise ValueError('no settings to change')
        save_settings(self.config, updates)
        self.config = Config.load(path=self.config.config_path, home=self.config.home)
        self.translator = get_translator(self.config.lang)
        return {'settings': settings_view(self.config), 'strings': load_catalog(self.config.lang), 'lang': self.config.lang}

    def open_config(self, launch: bool=True) -> dict[str, Any]:
        path = open_settings_file(self.config, launch=bool(launch))
        return {'path': str(path), 'settings': settings_view(self.config)}

    def saved_sessions(self, limit: int=30) -> dict[str, Any]:
        from promptwizard.storage import list_sessions
        records = list_sessions(self.config, max(1, min(int(limit), 200)))
        return {'sessions': [
            {
                'id': record.get('id', ''),
                'finished_at': record.get('finished_at', ''),
                'provider': record.get('provider', ''),
                'model': record.get('model', ''),
                'mode': record.get('mode', ''),
                'language': record.get('prompt_language', ''),
                'score': (record.get('analysis') or {}).get('score', 0),
                'prompt': record.get('original_prompt', '')[:160],
            }
            for record in records
        ]}

    def session(self, identifier: str) -> dict[str, Any]:
        from promptwizard.storage import get_session
        record = get_session(self.config, identifier)
        if record is None:
            raise LookupError(identifier)
        rewrite = record.get('rewrite') or {}
        return {
            'id': record.get('id', ''),
            'warnings': record.get('warnings', []),
            'provider': record.get('provider', ''),
            'model': record.get('model', ''),
            'language': record.get('prompt_language', ''),
            'original_prompt': record.get('original_prompt', ''),
            'translation': record.get('translated_prompt', ''),
            'stats': {
                'duration_ms': int(record.get('duration_ms') or 0),
                'tokens_in': int(record.get('tokens_in') or 0),
                'tokens_out': int(record.get('tokens_out') or 0),
                'tokens_total': int(record.get('tokens_in') or 0) + int(record.get('tokens_out') or 0),
            },
            'saved': '',
            'mode': record.get('mode', ''),
            'rewrite': {
                'improved_prompt': rewrite.get('improved_prompt', ''),
                'changes': rewrite.get('changes', []),
                'language': rewrite.get('language', ''),
            },
        }

    def set_autostart(self, enabled: Any=None) -> dict[str, Any]:
        from promptwizard.autostart import set_enabled, state
        if enabled is None:
            return state()
        set_enabled(bool(enabled))
        return state()

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = str(payload.get('prompt') or '').strip()
        if not prompt:
            raise ValueError('empty prompt')
        add_draft(self.config, prompt)
        lang = normalize_language(str(payload.get('lang') or self.config.lang))
        config = self.config
        provider = payload.get('provider') or None
        model = payload.get('model') or None
        if provider or model:
            config.set_provider_override(provider=provider, model=model)
        session = Session(config, get_translator(lang), prompt)
        session.analyze()
        questions = session.make_questions()
        identifier = uuid.uuid4().hex[:12]
        with self.lock:
            self.sessions[identifier] = session
        return {
            'id': identifier,
            'analysis': _analysis_json(session.analysis),
            'questions': [
                {
                    'id': question.id,
                    'text': question.text,
                    'why': question.why,
                    'kind': question.kind,
                    'options': list(question.options),
                }
                for question in questions
            ],
            'warnings': list(session.warnings),
            'provider': session.provider.name,
            'model': session.provider.model or '-',
            'language': session.prompt_language,
            'translation': session.translated_prompt or '',
        }

    def rewrite(self, payload: dict[str, Any]) -> dict[str, Any]:
        identifier = str(payload.get('id') or '')
        with self.lock:
            session = self.sessions.get(identifier)
        if session is None:
            raise LookupError(identifier)
        answers = payload.get('answers') or {}
        session.set_answers({str(key): str(value) for key, value in answers.items()})
        session.run_rewrite()
        result = session.result()
        path = save_session(self.config, result.to_dict())
        response = _result_json(result, str(path))
        saved = autosave_result(result, self.translator, self.config.autosave_dir)
        response['autosaved'] = str(saved or '')
        return response

    def drafts(self) -> dict[str, Any]:
        return {'drafts': list_drafts(self.config)}

    def drop_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {'drafts': remove_draft(self.config, str(payload.get('prompt') or ''))}

    def clear_drafts(self) -> dict[str, Any]:
        return {'drafts': drop_all_drafts(self.config)}

    def batch(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw = payload.get('prompts')
        prompts = split_prompts(raw) if isinstance(raw, str) else [str(item) for item in (raw or [])]
        if not prompts:
            raise ValueError('no prompts')
        translator = get_translator(normalize_language(str(payload.get('lang') or self.config.lang)))
        results: list[dict[str, Any]] = []
        for result in run_batch(self.config, translator, prompts):
            path = save_session(self.config, result.to_dict())
            autosaved = autosave_result(result, translator, self.config.autosave_dir)
            entry = _result_json(result, str(path))
            entry['autosaved'] = str(autosaved or '')
            entry['prompt'] = result.original_prompt
            entry['score'] = result.analysis.score
            entry['summary'] = result.analysis.summary
            results.append(entry)
            add_draft(self.config, result.original_prompt)
        return {'results': results}

    def update(self) -> dict[str, Any]:
        try:
            return check_for_update(__version__)
        except Exception as exc:
            return {'current': __version__, 'latest': '', 'url': '', 'newer': False, 'error': str(getattr(exc, 'message', exc))}


class Handler(BaseHTTPRequestHandler):
    server_version = 'PromptWizard'

    def log_message(self, *args: Any) -> None:
        return

    @property
    def app(self) -> AppState:
        return self.server.app

    def _send(self, body: bytes, content_type: str, status: int=200) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any], status: int=200) -> None:
        self._send(json.dumps(payload, ensure_ascii=False).encode('utf-8'), CONTENT_TYPES['.json'], status)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(length) if length else b''
        if not raw:
            return {}
        try:
            parsed = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f'invalid JSON body: {exc}') from exc
        if not isinstance(parsed, dict):
            raise ValueError('the body must be a JSON object')
        return parsed

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path in ('/', '/index.html'):
            body, content_type = _asset('index.html')
            return self._send(body, content_type)
        if parsed.path.startswith('/assets/'):
            name = parsed.path[len('/assets/'):]
            if not name or '/' in name or '\\' in name or name.startswith('.'):
                return self._send_json({'error': {'message': 'asset not found'}}, 404)
            try:
                body, content_type = _asset(name)
            except (FileNotFoundError, IsADirectoryError):
                return self._send_json({'error': {'message': 'asset not found'}}, 404)
            return self._send(body, content_type)
        if parsed.path == '/api/state':
            requested = parse_qs(parsed.query).get('lang', [None])[0]
            return self._send_json(self.app.state(requested))
        if parsed.path == '/api/models':
            requested = parse_qs(parsed.query).get('provider', [None])[0]
            try:
                return self._send_json(self.app.models(requested))
            except PromptWizardError as exc:
                return self._send_json(_settings_error(self.app.translator, exc), 400)
        if parsed.path == '/api/providers':
            return self._send_json(self.app.providers())
        if parsed.path == '/api/drafts':
            return self._send_json(self.app.drafts())
        if parsed.path == '/api/update':
            return self._send_json(self.app.update())
        if parsed.path == '/api/sessions':
            limit = parse_qs(parsed.query).get('limit', ['30'])[0]
            try:
                return self._send_json(self.app.saved_sessions(int(limit)))
            except ValueError:
                return self._send_json({'error': {'message': 'limit must be a number'}}, 400)
        if parsed.path.startswith('/api/sessions/'):
            identifier = parsed.path[len('/api/sessions/'):]
            try:
                return self._send_json(self.app.session(identifier))
            except LookupError:
                return self._send_json({'error': {'message': 'unknown session'}}, 404)
        return self._send_json({'error': {'message': 'not found'}}, 404)

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        try:
            payload = self._read_json()
        except ValueError as exc:
            return self._send_json({'error': {'message': str(exc)}}, 400)
        try:
            if parsed.path == '/api/analyze':
                return self._send_json(self.app.analyze(payload))
            if parsed.path == '/api/rewrite':
                return self._send_json(self.app.rewrite(payload))
            if parsed.path == '/api/batch':
                return self._send_json(self.app.batch(payload))
            if parsed.path == '/api/settings':
                return self._send_json(self.app.update_settings(payload))
            if parsed.path == '/api/config/open':
                return self._send_json(self.app.open_config(payload.get('launch', True)))
            if parsed.path == '/api/autostart':
                return self._send_json(self.app.set_autostart(payload.get('enabled')))
            if parsed.path == '/api/drafts':
                return self._send_json(self.app.drop_draft(payload))
            if parsed.path == '/api/drafts/clear':
                return self._send_json(self.app.clear_drafts())
        except LookupError:
            return self._send_json({'error': {'message': 'unknown session'}}, 404)
        except PromptWizardError as exc:
            return self._send_json(_settings_error(self.app.translator, exc), 400)
        except ValueError as exc:
            return self._send_json({'error': {'message': str(exc)}}, 400)
        return self._send_json({'error': {'message': 'not found'}}, 404)


def build_server(config: Config, translator: Translator, host: str='127.0.0.1', port: int=0) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.app = AppState(config, translator)
    return server


def serve(
    config: Config,
    translator: Translator,
    *,
    host: str='127.0.0.1',
    port: int=0,
) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    server = build_server(config, translator, host, port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    bound_host, bound_port = server.server_address[0], server.server_address[1]
    return server, thread, f'http://{bound_host}:{bound_port}/'
