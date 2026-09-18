from __future__ import annotations
from collections.abc import Sequence
import pytest
from promptwizard.config import Config, ProviderSettings
from promptwizard.i18n import get_translator
from promptwizard.llm.base import LLMProvider, LLMRequest, LLMResponse, ProviderStatus

class FakeProvider(LLMProvider):
    name = 'fake'
    kind = 'openai_compatible'
    requires_key = False

    def __init__(self, answers: Sequence[str]=(), *, model: str='fake-model') -> None:
        super().__init__(ProviderSettings(name='fake', base_url='http://fake.invalid', model=model))
        self._answers = list(answers)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        text = self._answers.pop(0) if self._answers else '{}'
        return LLMResponse(text=text, provider=self.name, model=self.model)

    def status(self) -> ProviderStatus:
        return ProviderStatus(name=self.name, available=True, detail='fake provider')

@pytest.fixture()
def translator():
    return get_translator('en')

@pytest.fixture()
def config(tmp_path):
    return Config.load(home=tmp_path, dotenv=False)

@pytest.fixture()
def make_provider():

    def factory(answers: Sequence[str]=()) -> FakeProvider:
        return FakeProvider(answers)
    return factory
