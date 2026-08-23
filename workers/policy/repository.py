"""Local policy state used by the deterministic Gate 2 loop."""

from __future__ import annotations

from datetime import datetime

from schemas.policy_snapshot import PolicyProposal

from .models import PolicyRun, SourceState


class InMemoryPolicyRepository:
    def __init__(self) -> None:
        self._runs: dict[str, PolicyRun] = {}
        self._source_states: dict[str, SourceState] = {}
        self._proposals: dict[str, PolicyProposal] = {}
        self._proposal_counter = 0

    def create_run(self, run_id: str, source_id: str, started_at: datetime) -> None:
        if run_id in self._runs:
            raise ValueError(f"run already exists: {run_id}")
        self._runs[run_id] = PolicyRun(
            run_id=run_id,
            source_id=source_id,
            status="running",
            started_at=started_at,
        )

    def get_run(self, run_id: str) -> PolicyRun:
        return self._runs[run_id].model_copy(deep=True)

    def complete_run(
        self,
        run_id: str,
        *,
        status: str,
        finished_at: datetime,
        previous_sha256: str | None,
        current_sha256: str,
        proposal_id: str | None,
    ) -> None:
        run = self._runs[run_id]
        self._runs[run_id] = run.model_copy(
            update={
                "status": status,
                "finished_at": finished_at,
                "previous_sha256": previous_sha256,
                "current_sha256": current_sha256,
                "proposal_id": proposal_id,
                "error": None,
            }
        )

    def fail_run(self, run_id: str, error: str, finished_at: datetime) -> None:
        run = self._runs[run_id]
        self._runs[run_id] = run.model_copy(
            update={"status": "failed", "finished_at": finished_at, "error": error}
        )

    def get_source_state(self, source_id: str) -> SourceState | None:
        state = self._source_states.get(source_id)
        return state.model_copy(deep=True) if state is not None else None

    def put_source_state(self, source_id: str, state: SourceState) -> None:
        self._source_states[source_id] = state.model_copy(deep=True)

    def create_proposal(self, proposal: PolicyProposal) -> str:
        self._proposal_counter += 1
        proposal_id = f"proposal_{self._proposal_counter:03d}"
        self._proposals[proposal_id] = proposal.model_copy(deep=True)
        return proposal_id

    def get_proposal(self, proposal_id: str | None) -> PolicyProposal:
        if proposal_id is None:
            raise KeyError("proposal id is required")
        return self._proposals[proposal_id].model_copy(deep=True)

    def list_proposals(self) -> dict[str, PolicyProposal]:
        return {
            proposal_id: proposal.model_copy(deep=True)
            for proposal_id, proposal in self._proposals.items()
        }
