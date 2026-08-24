"""Worker-internal policy records that are not shared A/B contracts."""

from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from schemas.policy_snapshot import ImpactNode, PackName


class InternalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PolicyDiff(InternalModel):
    source_id: str
    previous_sha256: str
    current_sha256: str
    unified_diff: str


class PolicySource(InternalModel):
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    url: str = Field(pattern=r"^https://")
    content_selector: str = Field(min_length=1)
    enabled: bool


class FetchedSource(InternalModel):
    content: bytes
    source_url: str


class BlobRef(InternalModel):
    uri: str
    sha256: str


class SourceState(InternalModel):
    last_success_at: AwareDatetime
    raw_uri: str
    normalized_uri: str
    normalized_sha256: str


class PolicyRun(InternalModel):
    run_id: str
    source_id: str
    status: Literal["running", "no_change", "proposal_created", "failed"]
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    previous_sha256: str | None = None
    current_sha256: str | None = None
    proposal_id: str | None = None
    error: str | None = None


class ProposalDraft(InternalModel):
    summary: str = Field(min_length=1, max_length=1000)
    impact: list[ImpactNode] = Field(min_length=1)
    effective_from: AwareDatetime
    draft_pack_updates: dict[PackName, dict[str, Any]] = Field(min_length=1)


class ProposalRequest(InternalModel):
    source_url: str
    previous_sha256: str
    current_sha256: str
    unified_diff: str


class RefreshResult(InternalModel):
    run_id: str
    status: Literal["no_change", "proposal_created"]
    proposal_id: str | None
    previous_sha256: str | None
    current_sha256: str
