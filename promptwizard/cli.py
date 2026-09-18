from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence
from promptwizard import __app_name__, __version__
from promptwizard.config import Config
from promptwizard.errors import GUIUnavailable, InputError, PromptWizardError
from promptwizard.export import FORMATS, render, session_to_markdown, write_output
from promptwizard.i18n import DEFAULT_LANGUAGE, LANGUAGES, Translator, detect_system_language, get_translator, normalize_language
from promptwizard.llm.registry import build_provider, describe_providers
from promptwizard.pipeline import SessionResult, run
from promptwizard.questions import Question
from promptwizard.storage import get_session, list_sessions, save_session
__all__ = ['COMMANDS', 'build_parser', 'main']
COMMANDS: tuple[str, ...] = ('run', 'gui', 'providers', 'models', 'sessions', 'config', 'version')

class Printer:

    def __init__(self, translator: Translator, *, quiet: bool=False) -> None:
        self.translator = translator
        self.quiet = quiet

    def info(self, message: str='') -> None:
        if not self.quiet:
            print(message)

    def out(self, message: str='') -> None:
        print(message)
_VALUE_FLAGS: frozenset[str] = frozenset({'--lang', '--home', '--config', '--provider', '--model', '--base-url', '--temperature', '--max-tokens', '--timeout', '--max-questions', '--file', '--out', '--format', '--show', '--limit'})

def _prescan_lang(argv: Sequence[str]) -> str | None:
    for index, token in enumerate(argv):
        if token == '--lang' and index + 1 < len(argv):
            return normalize_language(argv[index + 1])
        if token.startswith('--lang='):
            return normalize_language(token.split('=', 1)[1])
    return None

def _split_command(argv: Sequence[str]) -> tuple[str, list[str]]:
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == '--':
            break
        if token in ('-V', '--version'):
            return ('version', list(argv[:index]) + list(argv[index + 1:]))
        if token in _VALUE_FLAGS:
            index += 2
            continue
        if token.startswith('-'):
            index += 1
            continue
        if token in COMMANDS:
            return (token, list(argv[:index]) + list(argv[index + 1:]))
        return ('run', list(argv))
    return ('run', list(argv))

def build_parser(translator: Translator, command: str='run') -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--lang', choices=list(LANGUAGES), help=translator('arg.lang.help'))
    common.add_argument('--home', help=translator('arg.home.help'))
    common.add_argument('--config', help=translator('arg.config.help'))
    common.add_argument('--quiet', action='store_true', help=translator('arg.quiet.help'))
    llm = argparse.ArgumentParser(add_help=False)
    llm.add_argument('--provider', help=translator('arg.provider.help'))
    llm.add_argument('--model', help=translator('arg.model.help'))
    llm.add_argument('--base-url', dest='base_url', help=translator('arg.base_url.help'))
    llm.add_argument('--temperature', type=float, help=translator('arg.temperature.help'))
    llm.add_argument('--max-tokens', dest='max_tokens', type=int, help=translator('arg.max_tokens.help'))
    llm.add_argument('--timeout', type=float, help=translator('arg.timeout.help'))
    llm.add_argument('--max-questions', dest='max_questions', type=int, help=translator('arg.max_questions.help'))
    prog = 'promptwizard' if command == 'run' else f'promptwizard {command}'
    parents = [common, llm]
    parser = argparse.ArgumentParser(prog=prog, description=translator('cli.description'), epilog=translator('cli.epilog'), formatter_class=argparse.RawDescriptionHelpFormatter, parents=parents)
    if command == 'run':
        parser.add_argument('prompt', nargs='*', help=translator('arg.prompt.help'))
        parser.add_argument('--file', help=translator('arg.file.help'))
        parser.add_argument('--out', help=translator('arg.out.help'))
        parser.add_argument('--format', choices=list(FORMATS), default='md', help=translator('arg.format.help'))
        parser.add_argument('--no-questions', dest='no_questions', action='store_true', help=translator('arg.no_questions.help'))
        parser.add_argument('--no-save', dest='no_save', action='store_true', help=translator('arg.no_save.help'))
        parser.add_argument('--json', action='store_true', help=translator('arg.json.help'))
        parser.add_argument('--no-fallback', dest='fallback', action='store_false', help=translator('arg.fallback.help'))
        parser.set_defaults(fallback=True)
        parser.add_argument('-V', '--version', action='version', version=f'%(prog)s {__version__}')
    elif command == 'gui':
        parser.add_argument('--tk', action='store_true', help=translator('arg.tk.help'))
        parser.add_argument('--port', type=int, default=0, help=translator('arg.port.help'))
    elif command == 'sessions':
        parser.add_argument('--show', help=translator('arg.show.help'))
        parser.add_argument('--limit', type=int, default=20, help=translator('arg.limit.help'))
        parser.add_argument('--json', action='store_true', help=translator('arg.json.help'))
    elif command == 'config':
        parser.add_argument('--init', action='store_true', help=translator('arg.init.help'))
        parser.add_argument('--set', action='append', metavar='KEY=VALUE', help=translator('arg.set.help'))
    return parser

def build_config(args: argparse.Namespace, command: str) -> Config:
    overrides: dict[str, Any] = {}
    for key in ('lang', 'temperature', 'max_tokens', 'timeout', 'max_questions'):
        value = getattr(args, key, None)
        if value is not None:
            overrides[key] = value
    config = Config.load(path=getattr(args, 'config', None), home=getattr(args, 'home', None), overrides=overrides)
    if command in ('run', 'gui'):
        provider = getattr(args, 'provider', None)
        model = getattr(args, 'model', None)
        base_url = getattr(args, 'base_url', None)
        if provider or model or base_url:
            config.set_provider_override(provider=provider, model=model, base_url=base_url)
    return config

def _print_error(exc: PromptWizardError, translator: Translator) -> None:
    print(f"{translator('cli.error_prefix')} {exc.message}")
    if exc.hint_key:
        hint = translator.get(exc.hint_key, **exc.hint_kwargs)
        if hint and hint != exc.hint_key:
            print(f"{translator('cli.hint_prefix')} {hint}")

def _read_prompt(args: argparse.Namespace, translator: Translator) -> str:
    if getattr(args, 'file', None):
        path = Path(args.file).expanduser()
        try:
            return path.read_text(encoding='utf-8')
        except OSError as exc:
            raise InputError(f'cannot read the prompt file {path}: {exc}', hint_key='error.input.file', hint_kwargs={'path': str(path)}) from exc
    if getattr(args, 'prompt', None):
        return ' '.join(args.prompt).strip()
    if not sys.stdin.isatty():
        return sys.stdin.read()
    print(translator('run.prompt_enter'))
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)
    return '\n'.join(lines)

def _ask_batch(questions: Sequence[Question], translator: Translator) -> dict[str, str]:
    print()
    print(f"{translator('run.questions_header')}:")
    for index, question in enumerate(questions, start=1):
        print(translator('run.question_item', index=index, text=question.text))
        if question.why:
            print(translator('run.question_why', why=question.why))
        if question.options:
            print(translator('run.question_options', options=' | '.join(question.options)))
    print(translator('run.answers_batch_hint'))
    answers: dict[str, str] = {}
    for question in questions:
        try:
            value = input(f'[{question.id}] > ')
        except EOFError:
            break
        answers[question.id] = value.strip()
    return answers

def _print_result(result: SessionResult, translator: Translator, printer: Printer, *, as_json: bool) -> None:
    if as_json:
        printer.out(render(result, 'json', translator).rstrip())
        return
    printer.out()
    printer.out(f"{translator('run.original_header')}:")
    printer.out(result.original_prompt.strip())
    printer.out()
    printer.out(f"{translator('run.issues_header')}:")
    printer.out(translator('run.score', score=result.analysis.score))
    if result.analysis.issues:
        for index, issue in enumerate(result.analysis.issues, start=1):
            printer.out(translator('run.issue_item', index=index, severity=translator(f'severity.{issue.severity}'), category=translator(f'category.{issue.category}'), title=issue.title))
            if issue.detail:
                printer.out(translator('run.issue_detail', detail=issue.detail))
    else:
        printer.out(translator('run.no_issues'))
    if result.questions:
        printer.out()
        printer.out(f"{translator('run.questions_header')}:")
        for index, question in enumerate(result.questions, start=1):
            printer.out(translator('run.question_item', index=index, text=question.text))
            answer = result.answers.get(question.id, '').strip()
            if answer:
                printer.out(f'   > {answer}')
    if result.rewrite is not None:
        printer.out()
        printer.out(f"{translator('run.improved_header')}:")
        printer.out(result.rewrite.improved_prompt)
        if result.rewrite.changes:
            printer.out()
            printer.out(f"{translator('run.changes_header')}:")
            for change in result.rewrite.changes:
                printer.out(translator('run.change_item', change=change))
    if result.warnings:
        printer.out()
        for warning in result.warnings:
            printer.out(translator('run.template_warning', reason=warning))
    printer.out()
    printer.out(translator('run.mode_label', mode=translator(f'run.mode.{result.mode}')))

def _cmd_run(args: argparse.Namespace, config: Config, translator: Translator, printer: Printer) -> int:
    prompt = _read_prompt(args, translator)
    if not prompt.strip():
        raise InputError(translator('run.empty_prompt'), hint_key='error.input.empty')
    if getattr(args, 'file', None):
        printer.info(translator('run.from_file', path=args.file))
    provider = build_provider(config)
    printer.info(translator('run.analyzing', provider=provider.label))
    interactive = sys.stdin.isatty()
    ask = None
    if interactive and (not args.no_questions) and (args.max_questions != 0):
        ask = lambda questions: _ask_batch(questions, translator)
    session = run(config, translator, prompt, provider=provider, ask=ask, max_questions=args.max_questions, no_questions=args.no_questions, allow_fallback=args.fallback)
    result = session
    if result.warnings:
        for warning in result.warnings:
            printer.info(translator('run.template_warning', reason=warning))
    _print_result(result, translator, printer, as_json=args.json)
    if not args.no_save:
        path = save_session(config, result.to_dict())
        printer.info(translator('run.saved', path=path))
    if args.out:
        text = render(result, args.format, translator)
        target = write_output(text, args.out)
        printer.info(translator('run.exported', path=target))
    return 0

def _cmd_providers(config: Config, translator: Translator, printer: Printer) -> int:
    printer.out(translator('providers.header'))
    for status in describe_providers(config):
        state = translator('providers.available') if status.available else translator('providers.unavailable')
        printer.out(translator('providers.row', name=status.name, status=state, detail=status.detail))
        if status.models:
            printer.out('    ' + translator('providers.models', models=', '.join(status.models[:8])))
    printer.out(translator('providers.hint'))
    return 0

def _cmd_sessions(args: argparse.Namespace, config: Config, translator: Translator, printer: Printer) -> int:
    if getattr(args, 'show', None):
        record = get_session(config, args.show)
        if record is None:
            printer.out(translator('sessions.not_found', id=args.show))
            return 1
        if getattr(args, 'json', False):
            printer.out(json.dumps(record, ensure_ascii=False, indent=2))
        else:
            printer.out(session_to_markdown(record, translator).rstrip())
        return 0
    records = list_sessions(config, args.limit)
    if not records:
        printer.out(translator('sessions.empty'))
        return 0
    if getattr(args, 'json', False):
        printer.out(json.dumps(records, ensure_ascii=False, indent=2))
        return 0
    printer.out(translator('sessions.header'))
    for record in records:
        printer.out(translator('sessions.row', id=record.get('id', ''), finished_at=record.get('finished_at', ''), provider=record.get('provider', ''), model=record.get('model', ''), language=record.get('prompt_language', '')))
    printer.out(translator('sessions.saved_count', count=len(records)))
    return 0

def _coerce(value: str) -> Any:
    lowered = value.strip().lower()
    if lowered in ('true', 'false'):
        return lowered == 'true'
    for cast in (int, float):
        try:
            return cast(value)
        except ValueError:
            continue
    return value


def _cmd_models(args: argparse.Namespace, config: Config, translator: Translator, printer: Printer) -> int:
    from promptwizard.settings import available_models
    data = available_models(config, getattr(args, 'provider', None))
    printer.out(translator('models.header', provider=data['provider']))
    for name in data['models']:
        printer.out(('* ' if name == data['current'] else '  ') + name)
    if data['note']:
        printer.out(translator('models.note', reason=data['note']))
    return 0


def _cmd_config(args: argparse.Namespace, config: Config, translator: Translator, printer: Printer) -> int:
    updates = getattr(args, 'set', None)
    if updates:
        from promptwizard.errors import ConfigError
        from promptwizard.settings import save_settings
        payload: dict[str, Any] = {}
        for entry in updates:
            key, separator, value = entry.partition('=')
            if not separator or not key.strip():
                raise ConfigError(f'expected KEY=VALUE, got {entry!r}', hint_key='error.config.invalid')
            payload[key.strip()] = _coerce(value)
        printer.out(translator('config.written', path=save_settings(config, payload)))
        return 0
    if getattr(args, 'init', False):
        if config.config_path.exists():
            printer.out(translator('config.path', path=config.config_path))
        else:
            printer.out(translator('config.written', path=config.save()))
        return 0
    printer.out(translator('config.header'))
    printer.out(translator('config.path', path=config.config_path))
    printer.out(json.dumps(config.to_dict(), ensure_ascii=False, indent=2))
    printer.out(translator('config.note'))
    return 0

def _cmd_gui(config: Config, translator: Translator, args: argparse.Namespace) -> int:
    if getattr(args, 'tk', False):
        from promptwizard.gui import launch as launch_tk
        return launch_tk(config, translator)
    from promptwizard.webui import launch as launch_web
    return launch_web(config, translator, port=getattr(args, 'port', 0) or 0)

def main(argv: Sequence[str] | None=None) -> int:
    raw = list(sys.argv[1:]) if argv is None else [str(item) for item in argv]
    command, raw = _split_command(raw)
    translator = get_translator(_prescan_lang(raw) or detect_system_language() or DEFAULT_LANGUAGE)
    parser = build_parser(translator, command)
    args = parser.parse_args(raw)
    try:
        if command == 'version':
            print(f'{__app_name__} {__version__}')
            return 0
        config = build_config(args, command)
        translator = get_translator(config.lang)
        printer = Printer(translator, quiet=getattr(args, 'quiet', False))
    except PromptWizardError as exc:
        _print_error(exc, translator)
        return 1
    try:
        if command == 'providers':
            return _cmd_providers(config, translator, printer)
        if command == 'models':
            return _cmd_models(args, config, translator, printer)
        if command == 'sessions':
            return _cmd_sessions(args, config, translator, printer)
        if command == 'config':
            return _cmd_config(args, config, translator, printer)
        if command == 'gui':
            return _cmd_gui(config, translator, args)
        return _cmd_run(args, config, translator, printer)
    except GUIUnavailable as exc:
        _print_error(exc, translator)
        return 1
    except PromptWizardError as exc:
        _print_error(exc, translator)
        return 1
    except KeyboardInterrupt:
        print(translator('cli.interrupt'))
        return 130
    except Exception as exc:
        print(f"{translator('cli.error_prefix')} {translator('error.internal')} ({exc})")
        return 1
if __name__ == '__main__':
    raise SystemExit(main())
