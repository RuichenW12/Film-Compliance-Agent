"""Policy administration HTTP models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict

from schemas.policy_snapshot import (
    ImpactNode,
    PackName,
    ProposalStatus,
    VerificationStatus,
    Version,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CrawlRequest(ApiModel):
    source_id: str


class CrawlResponse(ApiModel):
    run_id: str


class PolicyRunResponse(ApiModel):
    run_id: str
    source_id: str
    status: Literal["running", "no_change", "proposal_created", "failed"]
    started_at: AwareDatetime
    finished_at: AwareDatetime | None
    previous_sha256: str | None
    current_sha256: str | None
    proposal_id: str | None
    error: str | None


class ProposalSummary(ApiModel):
    proposal_id: str
    summary: str
    impact: list[ImpactNode]
    effective_from: AwareDatetime
    status: ProposalStatus


class ProposalDetail(ProposalSummary):
    source_diff_uri: str
    source_diff_text: str
    draft_pack_updates: dict[PackName, dict[str, Any]]
    published_version: Version | None


class PublishResponse(ApiModel):
    snapshot_version: Version


class SnapshotSummary(ApiModel):
    version: Version
    published_at: AwareDatetime
    effective_from: AwareDatetime
    published_by: str
    thresholds_published: bool
    verification_status: VerificationStatus
