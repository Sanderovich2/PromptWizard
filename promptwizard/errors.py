"""Exception hierarchy for PromptWizard.

Every error that can reach a user carries an optional ``hint_key``: an i18n key
that the CLI/GUI resolves into an actionable message ("set GROQ_API_KEY...",
"start ollama serve...").  That is the mechanism behind the rule "no raw
traceback reaches the user": the top-level handler in :mod:`promptwizard.cli`
prints ``message`` plus the localized ``hint_key`` instead of a stack trace.
"""

from __future__ import annotations

__all__ = [
    "PromptWizardError",
    "ConfigError",
    "InputError",
    "ProviderError",
    "ProviderUnavailable",
    "MissingCredentials",
    "ProviderTimeout",
    "ProviderHTTPError",
    "LLMResponseError",
    "StorageError",
    "GUIUnavailable",
]


class PromptWizardError(Exception):
    """Base class for all PromptWizard errors.

    Args:
        message: Human readable, already-formatted message.
        hint_key: Optional i18n key with a fix-it hint for the user.
        hint_kwargs: Values interpolated into the hint.
    """

    def __init__(
        self,
        message: str,
        *,
        hint_key: str | None = None,
        hint_kwargs: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint_key = hint_key
        self.hint_kwargs: dict[str, object] = dict(hint_kwargs or {})


class ConfigError(PromptWizardError):
    """The configuration file or a configuration value is invalid."""


class InputError(PromptWizardError):
    """The user gave no usable prompt text (empty input, missing file)."""


class StorageError(PromptWizardError):
    """A session file or the storage directory could not be read/written."""


class GUIUnavailable(PromptWizardError):
    """The optional tkinter GUI cannot be started in this environment."""


class ProviderError(PromptWizardError):
    """Base class for LLM provider failures (always recoverable: template mode)."""


class ProviderUnavailable(ProviderError):
    """The provider cannot be reached (no server, no network, DNS failure)."""


class MissingCredentials(ProviderError):
    """The provider needs an API key and none was found in env or config."""


class ProviderTimeout(ProviderError):
    """The provider did not answer within the configured timeout."""


class ProviderHTTPError(ProviderError):
    """The provider answered with a non-2xx HTTP status."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        body: str = "",
        hint_key: str | None = None,
        hint_kwargs: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message, hint_key=hint_key, hint_kwargs=hint_kwargs)
        self.status = status
        self.body = body[:500]


class LLMResponseError(ProviderError):
    """The provider answered with something this client could not parse."""
