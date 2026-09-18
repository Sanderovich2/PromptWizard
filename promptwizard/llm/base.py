"""The provider contract shared by every LLM adapter."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Mapping

from promptwizard.config import ProviderSettings

__all__ = ["LLMProvider", "LLMRequest", "LLMResponse", "ProviderStatus"]


@dataclass(frozen=True)
class LLMRequest:
    """A single completion request.

    Attributes:
        prompt: The user turn.
        system: Optional system instruction.
        temperature: Sampling temperature (0.0-2.0); ``None`` means "use the
            provider default" (see :meth:`LLMProvider.prepare`).
        max_tokens: Upper bound on generated tokens; ``None`` means provider default.
        json_mode: Ask the provider for strict JSON when it supports it.  The
            rewrites rely on JSON, but every adapter still parses leniently, so
            a provider that ignores json_mode stays usable.
    """

    prompt: str
    system: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    json_mode: bool = False


@dataclass(frozen=True)
class LLMResponse:
    """A completion plus the provenance needed for the session log."""

    text: str
    provider: str
    model: str
    raw: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            # Never let an empty answer travel further: the callers treat "" as
            # "no answer" and would silently produce an empty rewrite.
            raise ValueError("provider returned an empty completion")


@dataclass(frozen=True)
class ProviderStatus:
    """Result of a cheap availability probe, used by ``promptwizard providers``."""

    name: str
    available: bool
    detail: str
    models: tuple[str, ...] = ()
    requires_key: bool = False
    key_present: bool = False


class LLMProvider(abc.ABC):
    """Base class for LLM adapters.

    Args:
        settings: Per-provider settings from :class:`promptwizard.config.Config`.
        api_key: Resolved API key, or ``None`` for keyless providers.
        timeout: Socket timeout in seconds.
        default_temperature: Used when a request does not override it.
        default_max_tokens: Used when a request does not override it.
    """

    #: Stable provider id used in config, CLI flags and the session log.
    name: str = "provider"
    #: Adapter family: ``ollama``, ``gemini``, ``openai_compatible``, ``offline``.
    kind: str = "openai_compatible"
    #: Whether this provider needs an API key at all.
    requires_key: bool = False
    #: Environment variable that is checked for the key (for hints only).
    api_key_env: str = ""

    def __init__(
        self,
        settings: ProviderSettings,
        *,
        api_key: str | None = None,
        timeout: float = 60.0,
        default_temperature: float = 0.3,
        default_max_tokens: int = 1200,
    ) -> None:
        self.settings = settings
        self.api_key = (api_key or "").strip() or None
        self.timeout = float(timeout)
        self.default_temperature = float(default_temperature)
        self.default_max_tokens = int(default_max_tokens)

    # ---------------------------------------------------------------- helpers
    @property
    def model(self) -> str:
        """Configured model id, falling back to the adapter's default."""
        return (self.settings.model or "").strip()

    @property
    def label(self) -> str:
        """Human readable ``provider/model`` for status lines and session logs."""
        return f"{self.name}/{self.model}" if self.model else self.name

    def prepare(self, request: LLMRequest) -> LLMRequest:
        """Return ``request`` with unset sampling fields filled from the defaults."""
        return LLMRequest(
            prompt=request.prompt,
            system=request.system,
            temperature=self.default_temperature if request.temperature is None else float(request.temperature),
            max_tokens=self.default_max_tokens if request.max_tokens is None else int(request.max_tokens),
            json_mode=request.json_mode,
        )

    # ------------------------------------------------------------- interface
    @abc.abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run one completion. Raises :class:`promptwizard.errors.ProviderError`."""

    @abc.abstractmethod
    def status(self) -> ProviderStatus:
        """Cheap availability probe (HTTP HEAD/GET or a local check)."""

    def available(self) -> bool:
        """``True`` when :meth:`status` reports the provider usable right now."""
        try:
            return self.status().available
        except Exception:  # pragma: no cover - defensive: status must never raise
            return False

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} {self.label}>"
