"""Evidence-bounded structured policy proposal generation."""

from __future__ import annotations

from typing import Any

from ..models import ProposalDraft, ProposalRequest


class PolicyProposalModelError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class GeminiProposalModel:
    def __init__(self, client: Any, model: str, prompt_text: str) -> None:
        self._client = client
        self._model = model
        self._prompt_text = prompt_text.strip()

    @classmethod
    def from_vertex_ai(
        cls,
        project: str,
        location: str,
        model: str,
        prompt_text: str,
    ) -> "GeminiProposalModel":
        from google import genai

        client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )
        return cls(client, model, prompt_text)

    async def draft(self, request: ProposalRequest) -> ProposalDraft:
        base_contents = self._build_contents(request)
        last_error: Exception | None = None
        for attempt in range(3):
            contents = base_contents
            if attempt:
                contents += (
                    "\n\nRepair note: the previous response did not match the "
                    "configured response schema. Return only a conforming response."
                )
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": ProposalDraft,
                    },
                )
                return ProposalDraft.model_validate(
                    getattr(response, "parsed", None)
                )
            except Exception as exc:
                last_error = exc

        raise PolicyProposalModelError(
            "POLICY_PROPOSAL_MODEL_FAILED",
            "proposal model did not return a valid structured draft",
        ) from last_error

    def _build_contents(self, request: ProposalRequest) -> str:
        return (
            f"{self._prompt_text}\n\n"
            f"Source URL: {request.source_url}\n"
            f"Previous SHA-256: {request.previous_sha256}\n"
            f"Current SHA-256: {request.current_sha256}\n"
            "BEGIN_UNTRUSTED_POLICY_DIFF\n"
            f"{request.unified_diff}\n"
            "END_UNTRUSTED_POLICY_DIFF"
        )
