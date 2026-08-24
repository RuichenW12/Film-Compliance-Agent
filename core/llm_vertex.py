"""Gemini on Vertex AI. Imported lazily so the package works without credentials."""

from __future__ import annotations

import json
from typing import Any

from .errors import UpstreamLLMError
from .llm import LLMRequest, SYSTEM_PREAMBLE


class VertexGeminiLLM:
    """Structured-output calls through google-genai with Vertex AI backend."""

    name = "vertex"

    def __init__(self, project: str, location: str, model: str) -> None:
        self._project = project
        self._location = location
        self._model = model
        self._client: Any | None = None

    def available(self) -> bool:
        return bool(self._project and self._model)

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from google import genai
            except ImportError as exc:  # pragma: no cover - depends on optional extra
                raise UpstreamLLMError(
                    "google-genai is not installed; install the 'vertex' extra"
                ) from exc
            self._client = genai.Client(
                vertexai=True, project=self._project, location=self._location
            )
        return self._client

    def structured(self, request: LLMRequest) -> dict[str, Any]:
        client = self._ensure_client()
        try:
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise UpstreamLLMError("google-genai is not installed") from exc

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PREAMBLE,
            temperature=request.temperature,
            response_mime_type="application/json",
            response_schema=request.response_schema,
        )
        try:
            response = client.models.generate_content(
                model=self._model, contents=request.render(), config=config
            )
        except Exception as exc:  # pragma: no cover - network failure path
            raise UpstreamLLMError(
                f"vertex call failed: {exc}", {"prompt_id": request.prompt_id}
            ) from exc

        text = getattr(response, "text", None)
        if not text:
            raise UpstreamLLMError(
                "empty response from Vertex", {"prompt_id": request.prompt_id}
            )
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise UpstreamLLMError(
                "Vertex returned non-JSON output", {"prompt_id": request.prompt_id}
            ) from exc
