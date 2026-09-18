"""Deterministic provider: no LLM, no network, no API key.

The ``offline`` provider makes the tool usable before any model is configured,
in CI, and in tests.  It never answers a completion: the pipeline sees
``kind == "offline"`` and runs its deterministic analysis/rewrite path instead
(see :mod:`promptwizard.pipeline`).  Asking it for a completion is a programming
error, so it raises rather than inventing text.
"""

from __future__ import annotations

from promptwizard.errors import ProviderUnavailable
from promptwizard.llm.base import LLMProvider, LLMRequest, LLMResponse, ProviderStatus

__all__ = ["OfflineProvider"]


class OfflineProvider(LLMProvider):
    """Placeholder adapter that marks a run as "template mode"."""

    name = "offline"
    kind = "offline"
    requires_key = False

    def complete(self, request: LLMRequest) -> LLMResponse:
        raise ProviderUnavailable(
            "offline: this provider never calls an LLM; the pipeline uses its deterministic path"
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            available=True,
            detail="deterministic mode, no LLM is called",
        )
