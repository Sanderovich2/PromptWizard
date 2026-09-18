from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from promptwizard.errors import ConfigError
from promptwizard.i18n import DEFAULT_LANGUAGE, normalize_language
__all__ = ['CONFIG_FILENAME', 'DEFAULT_HOME', 'HOME_ENV_VAR', 'PROVIDER_DEFAULTS', 'PROVIDER_NAMES', 'Config', 'ProviderSettings', 'load_dotenv', 'resolve_home']
HOME_ENV_VAR = 'PROMPTWIZARD_HOME'
CONFIG_FILENAME = 'config.json'
DEFAULT_HOME = Path.home() / '.promptwizard'
PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {'pollinations': {'base_url': 'https://text.pollinations.ai/openai', 'model': 'openai', 'api_key_env': '', 'kind': 'openai_compatible'}, 'ollama': {'base_url': 'http://localhost:11434', 'model': 'llama3.2', 'api_key_env': '', 'kind': 'ollama'}, 'gemini': {'base_url': 'https://generativelanguage.googleapis.com', 'model': 'gemini-2.5-flash', 'api_key_env': 'GEMINI_API_KEY', 'kind': 'gemini'}, 'groq': {'base_url': 'https://api.groq.com/openai/v1', 'model': 'llama-3.3-70b-versatile', 'api_key_env': 'GROQ_API_KEY', 'kind': 'openai_compatible'}, 'openrouter': {'base_url': 'https://openrouter.ai/api/v1', 'model': 'meta-llama/llama-3.3-70b-instruct:free', 'api_key_env': 'OPENROUTER_API_KEY', 'kind': 'openai_compatible'}, 'openai_compatible': {'base_url': '', 'model': '', 'api_key_env': 'OPENAI_API_KEY', 'kind': 'openai_compatible'}, 'offline': {'base_url': '', 'model': 'deterministic-stub', 'api_key_env': '', 'kind': 'offline'}}
PROVIDER_NAMES: tuple[str, ...] = tuple(PROVIDER_DEFAULTS)

THEMES: tuple[str, ...] = ('light', 'dark', 'auto')

FONTS: tuple[str, ...] = (
    '',
    'Segoe UI',
    'Inter',
    'IBM Plex Sans',
    'Roboto',
    'Verdana',
    'Tahoma',
    'Trebuchet MS',
    'Georgia',
    'Palatino Linotype',
    'Times New Roman',
    'Cascadia Mono',
    'Consolas',
    'JetBrains Mono',
    'Courier New',
)
_DOTENV_SEARCH = (Path('.env'), Path.home() / '.promptwizard' / '.env')

def resolve_home(home: str | os.PathLike[str] | None=None) -> Path:
    if home is not None:
        return Path(home).expanduser()
    env_home = os.environ.get(HOME_ENV_VAR)
    if env_home:
        return Path(env_home).expanduser()
    return DEFAULT_HOME

def load_dotenv(paths: tuple[Path, ...] | list[Path] | None=None, *, override: bool=False) -> list[Path]:
    loaded: list[Path] = []
    for path in paths if paths is not None else _DOTENV_SEARCH:
        candidate = Path(path)
        try:
            raw = candidate.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        loaded.append(candidate)
        for line in raw.splitlines():
            entry = line.strip()
            if not entry or entry.startswith('#') or '=' not in entry:
                continue
            if entry.startswith('export '):
                entry = entry[len('export '):].lstrip()
            key, _, value = entry.partition('=')
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and (value[0] in '"\''):
                value = value[1:-1]
            if not key or (key in os.environ and (not override)):
                continue
            os.environ[key] = value
    return loaded

@dataclass
class ModelPreset:
    name: str = ''
    provider: str = ''
    model: str = ''
    base_url: str = ''
    api_key_env: str = ''
    alias: str = ''
    tooltip: str = ''

    @property
    def label(self) -> str:
        return self.alias or self.name

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {'provider': self.provider, 'model': self.model}
        if self.alias:
            data['alias'] = self.alias
        if self.base_url:
            data['base_url'] = self.base_url
        if self.api_key_env:
            data['api_key_env'] = self.api_key_env
        if self.tooltip:
            data['tooltip'] = self.tooltip
        return data


@dataclass
class ProviderSettings:
    name: str
    base_url: str = ''
    model: str = ''
    api_key_env: str = ''
    api_key: str = ''
    kind: str = 'openai_compatible'
    extra: dict[str, str] = field(default_factory=dict)

    def to_dict(self, *, redact: bool=True) -> dict[str, Any]:
        data: dict[str, Any] = {'kind': self.kind}
        if self.base_url:
            data['base_url'] = self.base_url
        if self.model:
            data['model'] = self.model
        if self.api_key_env:
            data['api_key_env'] = self.api_key_env
        if self.api_key:
            data['api_key'] = '***' if redact else self.api_key
        data.update(self.extra)
        return data

@dataclass
class Config:
    home: Path = DEFAULT_HOME
    lang: str = DEFAULT_LANGUAGE
    theme: str = 'light'
    font: str = ''
    font_size: int = 15
    provider: str = 'pollinations'
    model: str = ''
    temperature: float = 0.3
    max_tokens: int = 1200
    timeout: float = 60.0
    max_questions: int = 6
    providers: dict[str, ProviderSettings] = field(default_factory=dict)
    presets: dict[str, ModelPreset] = field(default_factory=dict)
    source: Path | None = None

    @property
    def config_path(self) -> Path:
        return self.source or self.home / CONFIG_FILENAME

    @property
    def sessions_dir(self) -> Path:
        return self.home / 'sessions'

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None=None, *, home: str | os.PathLike[str] | None=None, overrides: Mapping[str, Any] | None=None, dotenv: bool=True) -> 'Config':
        if dotenv:
            load_dotenv()
        resolved_home = resolve_home(home)
        config_path = Path(path).expanduser() if path is not None else resolved_home / CONFIG_FILENAME
        raw: dict[str, Any] = {}
        if config_path.exists():
            raw = _read_json_object(config_path)
        config = cls(home=resolved_home, source=config_path if config_path.exists() else None)
        config.lang = normalize_language(_pick(raw, 'lang', os.environ.get('PROMPTWIZARD_LANG'), config.lang))
        config.theme = str(_pick(raw, 'theme', os.environ.get('PROMPTWIZARD_THEME'), config.theme)).strip().lower()
        config.font = str(_pick(raw, 'font', os.environ.get('PROMPTWIZARD_FONT'), config.font) or '').strip()
        config.font_size = _as_int(_pick(raw, 'font_size', os.environ.get('PROMPTWIZARD_FONT_SIZE'), config.font_size), 'font_size')
        config.provider = str(_pick(raw, 'provider', os.environ.get('PROMPTWIZARD_PROVIDER'), config.provider))
        config.model = str(_pick(raw, 'model', os.environ.get('PROMPTWIZARD_MODEL'), config.model) or '')
        config.temperature = _as_float(_pick(raw, 'temperature', os.environ.get('PROMPTWIZARD_TEMPERATURE'), config.temperature), 'temperature')
        config.max_tokens = _as_int(_pick(raw, 'max_tokens', os.environ.get('PROMPTWIZARD_MAX_TOKENS'), config.max_tokens), 'max_tokens')
        config.timeout = _as_float(_pick(raw, 'timeout', os.environ.get('PROMPTWIZARD_TIMEOUT'), config.timeout), 'timeout')
        config.max_questions = _as_int(_pick(raw, 'max_questions', os.environ.get('PROMPTWIZARD_MAX_QUESTIONS'), config.max_questions), 'max_questions')
        config.providers = _build_providers(raw.get('providers'))
        config.presets = _build_presets(raw.get('models'))
        if overrides:
            for key, value in overrides.items():
                if value is None:
                    continue
                if key == 'providers':
                    continue
                if key == 'provider_kind':
                    continue
                if not hasattr(config, key):
                    raise ConfigError(f'unknown configuration override: {key!r}')
                setattr(config, key, value)
        config.lang = normalize_language(config.lang)
        config.validate()
        return config

    def validate(self) -> None:
        if self.theme not in THEMES:
            raise ConfigError(f"theme must be one of {', '.join(THEMES)}, got {self.theme!r}", hint_key='error.config.range')
        if not 11 <= int(self.font_size) <= 24:
            raise ConfigError(f'font_size must be between 11 and 24, got {self.font_size}', hint_key='error.config.range')
        if not 0.0 <= float(self.temperature) <= 2.0:
            raise ConfigError(f'temperature must be between 0 and 2, got {self.temperature}', hint_key='error.config.range')
        if float(self.timeout) <= 0:
            raise ConfigError(f'timeout must be > 0, got {self.timeout}', hint_key='error.config.range')
        if int(self.max_tokens) <= 0:
            raise ConfigError(f'max_tokens must be > 0, got {self.max_tokens}', hint_key='error.config.range')
        if not 0 <= int(self.max_questions) <= 20:
            raise ConfigError(f'max_questions must be between 0 and 20, got {self.max_questions}', hint_key='error.config.range')
        if not str(self.provider).strip():
            raise ConfigError('provider must not be empty', hint_key='error.config.range')

    def provider_settings(self, name: str | None=None) -> ProviderSettings:
        target = (name or self.provider).strip()
        if target in self.providers:
            return self.providers[target]
        default_kind = 'openai_compatible'
        return ProviderSettings(name=target, kind=default_kind)

    def apply_preset(self, name: str) -> 'ModelPreset':
        key = str(name).strip().lower()
        if key not in self.presets:
            available = ', '.join(sorted(self.presets)) or 'none defined'
            raise ConfigError(f'unknown model preset {name!r} (available: {available})', hint_key='error.config.preset')
        preset = self.presets[key]
        if preset.provider:
            self.provider = preset.provider
        target = self.provider
        if target not in self.providers:
            self.providers[target] = ProviderSettings(name=target)
        if preset.model:
            self.providers[target].model = preset.model
        if preset.base_url:
            self.providers[target].base_url = preset.base_url
        if preset.api_key_env:
            self.providers[target].api_key_env = preset.api_key_env
        return preset

    def resolve_api_key(self, name: str | None=None) -> str | None:
        settings = self.provider_settings(name)
        if settings.api_key_env:
            value = os.environ.get(settings.api_key_env)
            if value:
                return value.strip()
        if settings.api_key:
            return settings.api_key.strip()
        return None

    def set_provider_override(self, *, provider: str | None=None, model: str | None=None, base_url: str | None=None) -> None:
        if provider:
            self.provider = provider
        target = self.provider
        if target not in self.providers:
            self.providers[target] = ProviderSettings(name=target)
        if model:
            self.providers[target].model = model
        if base_url:
            self.providers[target].base_url = base_url
        if model:
            self.model = model

    def to_dict(self, *, redact: bool=True) -> dict[str, Any]:
        return {'lang': self.lang, 'theme': self.theme, 'font': self.font, 'font_size': self.font_size, 'provider': self.provider, 'model': self.model, 'temperature': self.temperature, 'max_tokens': self.max_tokens, 'timeout': self.timeout, 'max_questions': self.max_questions, 'providers': {name: settings.to_dict(redact=redact) for name, settings in sorted(self.providers.items())}}

    def save(self, path: str | os.PathLike[str] | None=None) -> Path:
        target = Path(path).expanduser() if path is not None else self.config_path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        except OSError as exc:
            raise ConfigError(f'cannot write config to {target}: {exc}', hint_key='error.config.write') from exc
        self.source = target
        return target

def _pick(raw: Mapping[str, Any], key: str, env_value: str | None, fallback: Any) -> Any:
    if env_value not in (None, ''):
        return env_value
    value = raw.get(key)
    if value not in (None, ''):
        return value
    return fallback

def _as_float(value: Any, key: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f'{key} must be a number, got {value!r}', hint_key='error.config.range') from exc

def _as_int(value: Any, key: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f'{key} must be an integer, got {value!r}', hint_key='error.config.range') from exc

def _build_providers(raw: Any) -> dict[str, ProviderSettings]:
    providers: dict[str, ProviderSettings] = {}
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise ConfigError("'providers' must be an object", hint_key='error.config.invalid')
    for name, defaults in PROVIDER_DEFAULTS.items():
        providers[name] = ProviderSettings(name=name, base_url=defaults.get('base_url', ''), model=defaults.get('model', ''), api_key_env=defaults.get('api_key_env', ''), kind=defaults.get('kind', 'openai_compatible'))
    if os.environ.get('OLLAMA_HOST'):
        providers['ollama'].base_url = os.environ['OLLAMA_HOST'].strip()
    known_keys = {'base_url', 'model', 'api_key_env', 'api_key', 'kind'}
    for name, block in raw.items():
        if not isinstance(block, Mapping):
            raise ConfigError(f'provider {name!r} must be an object', hint_key='error.config.invalid')
        settings = providers.get(name) or ProviderSettings(name=str(name))
        for key, value in block.items():
            if key == 'extra' and isinstance(value, Mapping):
                settings.extra.update({str(k): str(v) for k, v in value.items()})
            elif key in known_keys:
                setattr(settings, key, '' if value is None else str(value))
            else:
                settings.extra[str(key)] = str(value)
        if not settings.kind:
            settings.kind = 'openai_compatible'
        providers[str(name)] = settings
    return providers

def _build_presets(raw: Any) -> dict[str, ModelPreset]:
    presets: dict[str, ModelPreset] = {}
    if not isinstance(raw, Mapping):
        return presets
    entries: list[tuple[str, Mapping[str, Any]]] = []
    for name, block in raw.items():
        if name == 'catalog' and isinstance(block, list):
            for index, item in enumerate(block):
                if isinstance(item, Mapping):
                    entries.append((str(item.get('alias') or item.get('name') or f'catalog-{index + 1}'), item))
            continue
        if isinstance(block, Mapping):
            entries.append((str(name), block))
    for name, block in entries:
        key = str(block.get('name') or name).strip().lower().replace(' ', '-')
        if not key:
            continue
        presets[key] = ModelPreset(
            name=key,
            provider=str(block.get('provider') or '').strip(),
            model=str(block.get('model') or '').strip(),
            base_url=str(block.get('base_url') or block.get('baseURL') or '').strip(),
            api_key_env=str(block.get('api_key_env') or block.get('apiKeyEnv') or '').strip(),
            alias=str(block.get('alias') or '').strip(),
            tooltip=str(block.get('tooltip') or '').strip(),
        )
    return presets


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding='utf-8')
    except OSError as exc:
        raise ConfigError(f'cannot read {path}: {exc}', hint_key='error.config.read') from exc
    try:
        data = json.loads(raw or '{}')
    except json.JSONDecodeError as exc:
        raise ConfigError(f'{path} is not valid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})', hint_key='error.config.invalid') from exc
    if not isinstance(data, dict):
        raise ConfigError(f'{path} must contain a JSON object', hint_key='error.config.invalid')
    return data
