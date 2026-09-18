from __future__ import annotations
import abc
from dataclasses import dataclass, field
from typing import Any, Mapping
from promptwizard.config import ProviderSettings
__all__ = ['LLMProvider', 'LLMRequest', 'LLMResponse', 'ProviderStatus']

@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    system: str = ''
    temperature: float | None = None
    max_tokens: int | None = None
    json_mode: bool = False

@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    raw: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError('provider returned an empty completion')

@dataclass(frozen=True)
class ProviderStatus:
    name: str
    available: bool
    detail: str
    models: tuple[str, ...] = ()
    requires_key: bool = False
    key_present: bool = False

class LLMProvider(abc.ABC):
    name: str = 'provider'
    kind: str = 'openai_compatible'
    requires_key: bool = False
    api_key_env: str = ''

    def __init__(self, settings: ProviderSettings, *, api_key: str | None=None, timeout: float=60.0, default_temperature: float=0.3, default_max_tokens: int=1200) -> None:
        self.settings = settings
        self.api_key = (api_key or '').strip() or None
        self.timeout = float(timeout)
        self.default_temperature = float(default_temperature)
        self.default_max_tokens = int(default_max_tokens)

    @property
    def model(self) -> str:
        return (self.settings.model or '').strip()

    @property
    def label(self) -> str:
        return f'{self.name}/{self.model}' if self.model else self.name

    def prepare(self, request: LLMRequest) -> LLMRequest:
        return LLMRequest(prompt=request.prompt, system=request.system, temperature=self.default_temperature if request.temperature is None else float(request.temperature), max_tokens=self.default_max_tokens if request.max_tokens is None else int(request.max_tokens), json_mode=request.json_mode)

    @abc.abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        pass

    @abc.abstractmethod
    def status(self) -> ProviderStatus:
        pass

    def available(self) -> bool:
        try:
            return self.status().available
        except Exception:
            return False

    def __repr__(self) -> str:
        return f'<{type(self).__name__} {self.label}>'
