"""Internationalization (RU/EN) for PromptWizard.

Two independent language notions live here, and mixing them up is the classic
bug in a tool like this:

* **UI language** (``--lang``, config ``lang``, the GUI switch) decides the
  language of menus, questions, issue descriptions and explanations.
* **Prompt language** is *detected from the user's prompt* and decides the
  language of the rewritten prompt itself.  A Russian prompt rewritten with
  ``--lang en`` still yields a Russian prompt, because the output is fed to a
  model and has to match the material the user is working with.

Catalogs are plain JSON files in ``promptwizard/locales/<lang>.json``.  A
missing key falls back to the fallback catalog (English) and then to the key
itself, so a half-translated catalog degrades instead of crashing.
"""

from __future__ import annotations

import json
import os
import re
import sys
from functools import lru_cache
from importlib import resources
from typing import Any, Mapping

__all__ = [
    "LANGUAGES",
    "DEFAULT_LANGUAGE",
    "FALLBACK_LANGUAGE",
    "Translator",
    "available_languages",
    "detect_system_language",
    "detect_text_language",
    "get_translator",
    "load_catalog",
    "normalize_language",
]

LANGUAGES: tuple[str, ...] = ("ru", "en")
DEFAULT_LANGUAGE = "ru"
FALLBACK_LANGUAGE = "en"

_LOCALES_PACKAGE = "promptwizard.locales"
_LOCALE_ALIASES = {
    "ru": "ru",
    "rus": "ru",
    "russian": "ru",
    "рус": "ru",
    "русский": "ru",
    "en": "en",
    "eng": "en",
    "english": "en",
    "англ": "en",
    "английский": "en",
}

_CYRILLIC_RE = re.compile(r"[а-яёА-ЯЁ]")
_LATIN_RE = re.compile(r"[a-zA-Z]")


def normalize_language(lang: str | None) -> str:
    """Map any user-supplied language tag onto a supported language code.

    ``ru-RU``, ``ru_RU.UTF-8``, ``Russian``, ``Русский`` all become ``ru``;
    unknown values become :data:`DEFAULT_LANGUAGE`.
    """
    if not lang:
        return DEFAULT_LANGUAGE
    raw = str(lang).strip().lower()
    for separator in (".", "-", "_", "@"):
        raw = raw.split(separator)[0]
    return _LOCALE_ALIASES.get(raw, DEFAULT_LANGUAGE if raw not in LANGUAGES else raw)


def available_languages() -> tuple[str, ...]:
    """Return the languages that actually have a catalog on disk."""
    found = []
    for lang in LANGUAGES:
        try:
            load_catalog(lang)
        except FileNotFoundError:
            continue
        found.append(lang)
    return tuple(found)


@lru_cache(maxsize=None)
def load_catalog(lang: str) -> dict[str, str]:
    """Load and flatten a locale catalog into a ``{"a.b.c": "text"}`` mapping.

    Flattening at load time keeps lookups a single dict hit and makes the
    "every key exists" test trivial.
    """
    normalized = normalize_language(lang)
    try:
        resource = resources.files(_LOCALES_PACKAGE).joinpath(f"{normalized}.json")
        raw = resource.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:  # pragma: no cover - packaging issue
        raise FileNotFoundError(f"locale catalog for {normalized!r} not found") from exc
    data = json.loads(raw)
    return _flatten(data)


def _flatten(data: Mapping[str, Any], prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in data.items():
        full = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            flat.update(_flatten(value, full))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    flat.update(_flatten(item, f"{full}.{index}"))
                else:
                    flat[f"{full}.{index}"] = str(item)
        else:
            flat[full] = str(value)
    return flat


class Translator:
    """Resolves i18n keys for one UI language.

    Callable so that call sites read as ``_("cli.title")``; supports ``str.format``
    style interpolation through keyword arguments.
    """

    def __init__(self, lang: str = DEFAULT_LANGUAGE) -> None:
        self.lang = normalize_language(lang)
        self._catalog = load_catalog(self.lang)
        self._fallback = load_catalog(FALLBACK_LANGUAGE)

    def __call__(self, key: str, /, **kwargs: object) -> str:
        return self.get(key, **kwargs)

    def get(self, key: str, /, default: str | None = None, **kwargs: object) -> str:
        """Return the localized string for ``key``.

        Resolution order: requested language -> fallback language -> ``default``
        -> the key itself.  Interpolation failures return the raw template
        rather than raising, because a broken placeholder must not break a run.
        """
        text = self._catalog.get(key)
        if text is None:
            text = self._fallback.get(key, default if default is not None else key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return text
        return text

    def has(self, key: str) -> bool:
        return key in self._catalog or key in self._fallback

    def keys(self, prefix: str = "") -> tuple[str, ...]:
        """Sorted keys of this catalog, optionally restricted to a prefix."""
        keys = set(self._catalog) | set(self._fallback)
        if not prefix:
            return tuple(sorted(keys))
        head = f"{prefix}."
        return tuple(sorted(key for key in keys if key.startswith(head)))


@lru_cache(maxsize=None)
def get_translator(lang: str | None = None) -> Translator:
    """Cached :class:`Translator` factory (one instance per language)."""
    return Translator(lang or DEFAULT_LANGUAGE)


def detect_system_language() -> str | None:
    """Best-effort detection of the OS language, or ``None`` when unknown.

    Checks (in order): ``PROMPTWIZARD_LANG``, ``LC_ALL``/``LC_MESSAGES``/``LANG``
    on POSIX, ``LANGUAGE``, and the Windows user default locale.
    """
    override = os.environ.get("PROMPTWIZARD_LANG")
    if override:
        return normalize_language(override)
    for variable in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = os.environ.get(variable)
        if value:
            candidate = value.split(":")[0]
            normalized = normalize_language(candidate) if _looks_like_locale(candidate) else None
            if normalized:
                return normalized
    if sys.platform == "win32":  # pragma: no cover - platform specific
        try:
            import locale

            code = locale.getlocale()[0] or ""
            if code:
                return normalize_language(code)
        except (ValueError, TypeError):
            return None
    return None


def _looks_like_locale(value: str) -> bool:
    head = re.split(r"[._@-]", value.strip().lower())[0]
    return head in _LOCALE_ALIASES


def detect_text_language(text: str) -> str:
    """Guess the language of a prompt: ``"ru"``, ``"en"`` or ``"unknown"``.

    Purely script based (Cyrillic vs Latin letter counts).  This decides which
    language the *rewritten prompt* is produced in, so it errs toward ``ru``
    when the text is mixed but clearly Cyrillic-leaning, and returns
    ``"unknown"`` for symbol-only input.
    """
    cyrillic = len(_CYRILLIC_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    total = cyrillic + latin
    if total == 0:
        return "unknown"
    if cyrillic / total >= 0.3:
        return "ru"
    return "en"
