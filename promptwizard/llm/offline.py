from __future__ import annotations
from promptwizard.errors import ProviderUnavailable
from promptwizard.llm.base import LLMProvider, LLMRequest, LLMResponse, ProviderStatus
__all__ = ['OfflineProvider']

class OfflineProvider(LLMProvider):
    name = 'offline'
    kind = 'offline'
    requires_key = False

    def complete(self, request: LLMRequest) -> LLMResponse:
        raise ProviderUnavailable('offline: this provider never calls an LLM; the pipeline uses its deterministic path')

    def status(self) -> ProviderStatus:
        return ProviderStatus(name=self.name, available=True, detail='deterministic mode, no LLM is called')
