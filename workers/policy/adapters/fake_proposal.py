"""Deterministic proposal adapter for Gate 2."""

from ..models import ProposalDraft, ProposalRequest


class FakeProposalModel:
    def __init__(self, draft: ProposalDraft) -> None:
        self._draft = draft.model_copy(deep=True)
        self.call_count = 0
        self.requests: list[ProposalRequest] = []

    async def draft(self, request: ProposalRequest) -> ProposalDraft:
        self.call_count += 1
        self.requests.append(request.model_copy(deep=True))
        return self._draft.model_copy(deep=True)
