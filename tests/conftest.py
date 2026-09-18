"""Shared fixtures: a fake provider, a throwaway home, an English translator.

Tests never touch the network.  ``FakeProvider`` replays queued answers so a test
can drive the pipeline through its LLM path deterministically, and it records the
requests so a test can assert what the model was actually asked.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from promptwizard.config import Config, ProviderSettings
from promptwizard.i18n import get_translator
from promptwizard.llm.base import LLMProvider, LLMRequest, LLMResponse, ProviderStatus


class FakeProvider(LLMProvider):
    """Provider double: replays queued answers and records the requests."""

    name = "fake"
    kind = "openai_compatible"
    requires_key = False

    def __init__(self, answers: Sequence[str] = (), *, model: str = "fake-model") -> None:
        super().__init__(ProviderSettings(name="fake", base_url="http://fake.invalid", model=model))
        self._answers = list(answers)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        text = self._answers.pop(0) if self._answers else "{}"
        return LLMResponse(text=text, provider=self.name, model=self.model)

    def status(self) -> ProviderStatus:
        return ProviderStatus(name=self.name, available=True, detail="fake provider")


@pytest.fixture()
def translator():
    """Translator for the UI language used by the tests."""
    return get_translator("en")


@pytest.fixture()
def config(tmp_path):
    """A Config whose home lives under tmp_path (no dotenv, no real files)."""
    return Config.load(home=tmp_path, dotenv=False)


@pytest.fixture()
def make_provider():
    """Factory for provider doubles with a queue of canned answers."""

    def factory(answers: Sequence[str] = ()) -> FakeProvider:
        return FakeProvider(answers)

    return factory
