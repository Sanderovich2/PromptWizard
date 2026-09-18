from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from promptwizard.autostart import state as autostart_state
from promptwizard.config import FONTS, PROVIDER_DEFAULTS, THEMES, Config
from promptwizard.errors import ConfigError
from promptwizard.i18n import LANGUAGES

__all__ = ["available_models", "open_config", "save_settings", "settings_view"]

SETTING_KEYS = (
    "lang",
    "theme",
    "provider",
    "model",
    "temperature",
    "max_tokens",
    "timeout",
    "max_questions",
    "auto_copy",
    "autosave_dir",
    "translate_prompt",
    "check_updates",
    "theme_day_start",
    "theme_night_start",
    "system_analyzer",
    "system_rewriter",
    "models",
    "font",
    "font_size",
)
PROVIDER_KEYS = ("base_url", "model", "api_key_env", "api_key", "kind")


def settings_view(config: Config) -> dict[str, Any]:
    settings = config.provider_settings()
    return {
        "lang": config.lang,
        "theme": config.theme,
        "font": config.font,
        "font_size": config.font_size,
        "provider": config.provider,
        "model": settings.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "timeout": config.timeout,
        "max_questions": config.max_questions,
        "auto_copy": config.auto_copy,
        "autosave_dir": config.autosave_dir,
        "translate_prompt": config.translate_prompt,
        "check_updates": config.check_updates,
        "theme_day_start": config.theme_day_start,
        "theme_night_start": config.theme_night_start,
        "system_analyzer": config.system_analyzer,
        "system_rewriter": config.system_rewriter,
        "languages": list(LANGUAGES),
        "themes": list(THEMES),
        "providers": {name: block.to_dict() for name, block in sorted(config.providers.items())},
        "presets": {name: preset.to_dict() for name, preset in sorted(config.presets.items())},
        "fonts": list(FONTS),
        "autostart": autostart_state(),
        "path": str(config.config_path),
    }


def open_config(config: Config, *, launch: bool = True) -> Path:
    target = config.config_path
    if not target.exists():
        save_settings(config, {})
    if not launch:
        return target
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(target))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
    except OSError as exc:
        raise ConfigError(f"cannot open {target}: {exc}", hint_key="error.config.open") from exc
    return target


def available_models(config: Config, provider: str | None = None) -> dict[str, Any]:
    target = (provider or config.provider).strip()
    settings = config.provider_settings(target)
    builtin = PROVIDER_DEFAULTS.get(target, {}).get("model", "")
    known = [name for name in (settings.model, builtin) if name]
    live: list[str] = []
    note = ""
    try:
        from promptwizard.llm.registry import build_provider

        adapter = build_provider(config, target)
        lister = getattr(adapter, "list_models", None)
        if callable(lister):
            live = [str(name) for name in lister()]
    except Exception as exc:
        note = str(getattr(exc, "message", exc))
    return {
        "provider": target,
        "current": settings.model or builtin,
        "models": list(dict.fromkeys(live + known)),
        "source": "provider" if live else "builtin",
        "note": note,
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}", hint_key="error.config.read") from exc
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"{path} is not valid JSON: {exc.msg} (line {exc.lineno})",
            hint_key="error.config.invalid",
        ) from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a JSON object", hint_key="error.config.invalid")
    return data


def save_settings(
    config: Config,
    updates: Mapping[str, Any],
    path: str | os.PathLike[str] | None = None,
) -> Path:
    target = Path(path).expanduser() if path is not None else config.config_path
    raw = _read_json(target)
    for key, value in updates.items():
        if value is None:
            continue
        if key == "providers":
            if not isinstance(value, Mapping):
                raise ConfigError("providers must be an object", hint_key="error.config.invalid")
            blocks = raw.setdefault("providers", {})
            if not isinstance(blocks, dict):
                raise ConfigError("providers must be an object", hint_key="error.config.invalid")
            for name, block in value.items():
                if not isinstance(block, Mapping):
                    raise ConfigError(f"provider {name!r} must be an object", hint_key="error.config.invalid")
                entry = blocks.setdefault(str(name), {})
                for field, field_value in block.items():
                    if field == "extra" and isinstance(field_value, Mapping):
                        extra = entry.setdefault("extra", {})
                        extra.update({str(k): str(v) for k, v in field_value.items()})
                    else:
                        entry[str(field)] = field_value
        elif key in SETTING_KEYS:
            raw[key] = value
        else:
            raise ConfigError(f"unknown setting {key!r}", hint_key="error.config.invalid")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot write config to {target}: {exc}", hint_key="error.config.write") from exc
    return target
