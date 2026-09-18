"""Google Gemini adapter (free tier).

Uses the native ``generateContent`` REST API rather than the OpenAI-compatibility
shim: one extra adapter, no proxy assumption, and the free-tier model list stays
visible through ``ListModels``.  Free-tier model ids change often; the default
lives in :data:`promptwizard.config.PROVIDER_DEFAULTS` and can be overridden with
``--model`` or ``config.json``.
"""

from __future__ import annotations

from typing import Any, Mapping

from promptwizard.errors import LLMResponseError, MissingCredentials
from promptwizard.llm.base import LLMProvider, LLMRequest, LLMResponse, ProviderStatus
from promptwizard.llm.http import get_json, post_json

__all__ = ["GeminiProvider"]

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"
API_VERSION = "v1beta"


class GeminiProvider(LLMProvider):
    """Chat with a Gemini model through ``models/{id}:generateContent``."""

    name = "gemini"
    kind = "gemini"
    requires_key = True
    api_key_env = "GEMINI_API_KEY"

    @property
    def base_url(self) -> str:
        return (self.settings.base_url or DEFAULT_BASE_URL).rstrip("/")

    @property
    def model_id(self) -> str:
        """Model id without any ``models/`` prefix, which the REST path adds."""
        return self.model.split("/")[-1]

    def _require_ready(self) -> None:
        if not self.api_key:
            raise MissingCredentials(
                "gemini: no API key found",
                hint_key="error.provider.missing_key",
                hint_kwargs={"provider": self.name, "env_var": self.api_key_env},
            )
        if not self.model:
            raise MissingCredentials(
                "gemini: no model configured",
                hint_key="error.provider.no_model",
                hint_kwargs={"provider": self.name},
            )

    def complete(self, request: LLMRequest) -> LLMResponse:
        self._require_ready()
        prepared = self.prepare(request)
        generation_config: dict[str, Any] = {
            "temperature": prepared.temperature,
            "maxOutputTokens": prepared.max_tokens,
        }
        if prepared.json_mode:
            generation_config["responseMimeType"] = "application/json"
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prepared.prompt}]}],
            "generationConfig": generation_config,
        }
        if prepared.system:
            payload["systemInstruction"] = {"parts": [{"text": prepared.system}]}
        data = post_json(
            f"{self.base_url}/{API_VERSION}/models/{self.model_id}:generateContent",
            payload,
            headers={"x-goog-api-key": self.api_key or ""},
            timeout=self.timeout,
            provider=self.name,
        )
        return LLMResponse(
            text=self._extract_text(data),
            provider=self.name,
            model=self.model_id,
            raw=data,
        )

    def list_models(self) -> tuple[str, ...]:
        """Return the model ids the key can use."""
        data = get_json(
            f"{self.base_url}/{API_VERSION}/models",
            headers={"x-goog-api-key": self.api_key or ""},
            timeout=min(self.timeout, 15.0),
            provider=self.name,
        )
        entries = data.get("models") or []
        names: list[str] = []
        for entry in entries:
            if isinstance(entry, Mapping):
                value = entry.get("name")
                if value:
                    names.append(str(value).split("/")[-1])
        return tuple(sorted(names))

    def status(self) -> ProviderStatus:
        if not self.api_key:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail="no API key found",
                requires_key=True,
                key_present=False,
            )
        try:
            models = self.list_models()
        except Exception as exc:  # noqa: BLE001 - a probe must degrade, never raise
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=str(getattr(exc, "message", exc)),
                requires_key=True,
                key_present=True,
            )
        return ProviderStatus(
            name=self.name,
            available=True,
            detail=f"reachable, {len(models)} model(s) listed",
            models=models,
            requires_key=True,
            key_present=True,
        )

    @staticmethod
    def _extract_text(data: Mapping[str, Any]) -> str:
        candidates = data.get("candidates") or []
        if candidates:
            first = candidates[0]
            if isinstance(first, Mapping):
                content = first.get("content")
                if isinstance(content, Mapping):
                    parts = content.get("parts") or []
                    chunks = [
                        str(part.get("text", ""))
                        for part in parts
                        if isinstance(part, Mapping) and part.get("text")
                    ]
                    text = "".join(chunks)
                    if text.strip():
                        return text
                if first.get("finishReason") and not text_from_parts(first):
                    raise LLMResponseError(
                        f"gemini: the answer was blocked ({first.get('finishReason')})",
                        hint_key="error.provider.bad_response",
                        hint_kwargs={"provider": "gemini"},
                    )
        feedback = data.get("promptFeedback")
        if isinstance(feedback, Mapping) and feedback.get("blockReason"):
            raise LLMResponseError(
                f"gemini: the prompt was blocked ({feedback.get('blockReason')})",
                hint_key="error.provider.bad_response",
                hint_kwargs={"provider": "gemini"},
            )
        raise LLMResponseError(
            "gemini: response contained no text content",
            hint_key="error.provider.bad_response",
            hint_kwargs={"provider": "gemini"},
        )


def text_from_parts(candidate: Mapping[str, Any]) -> str:
    """Return the concatenated text of a candidate, or ``""``."""
    content = candidate.get("content")
    if not isinstance(content, Mapping):
        return ""
    parts = content.get("parts") or []
    return "".join(
        str(part.get("text", "")) for part in parts if isinstance(part, Mapping) and part.get("text")
    )
