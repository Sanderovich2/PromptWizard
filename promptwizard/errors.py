from __future__ import annotations
__all__ = ['PromptWizardError', 'ConfigError', 'InputError', 'ProviderError', 'ProviderUnavailable', 'MissingCredentials', 'ProviderTimeout', 'ProviderHTTPError', 'LLMResponseError', 'StorageError', 'GUIUnavailable']

class PromptWizardError(Exception):

    def __init__(self, message: str, *, hint_key: str | None=None, hint_kwargs: dict[str, object] | None=None) -> None:
        super().__init__(message)
        self.message = message
        self.hint_key = hint_key
        self.hint_kwargs: dict[str, object] = dict(hint_kwargs or {})

class ConfigError(PromptWizardError):
    pass

class InputError(PromptWizardError):
    pass

class StorageError(PromptWizardError):
    pass

class GUIUnavailable(PromptWizardError):
    pass

class ProviderError(PromptWizardError):
    pass

class ProviderUnavailable(ProviderError):
    pass

class MissingCredentials(ProviderError):
    pass

class ProviderTimeout(ProviderError):
    pass

class ProviderHTTPError(ProviderError):

    def __init__(self, message: str, *, status: int, body: str='', hint_key: str | None=None, hint_kwargs: dict[str, object] | None=None) -> None:
        super().__init__(message, hint_key=hint_key, hint_kwargs=hint_kwargs)
        self.status = status
        self.body = body[:500]

class LLMResponseError(ProviderError):
    pass
