"""Immutable uploaded assets and material collection cards."""

from __future__ import annotations

from pydantic import AwareDatetime, Field

from .common import DomainModel, EvidenceRef
from .enums import AssetKind, MaterialStatus


class AssetVersion(DomainModel):
    """projects/{pid}/asset_versions/{vid} - immutable once written."""

    version_id: str
    kind: AssetKind
    storage_uri: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_version: str | None = None
    diff_summary: str | None = None
    uploaded_by: str
    created_at: AwareDatetime


class MaterialCard(DomainModel):
    """One S5 collection card: what, why, template, common rejects."""

    material_id: str
    name_key: str
    required: bool = True
    why_clause: EvidenceRef | None = None
    template_uri: str | None = None
    common_rejects_key: str | None = None
    status: MaterialStatus = MaterialStatus.PENDING
    asset_version: str | None = None
    invalid_reasons: list[str] = Field(default_factory=list)
    waive_reason: str | None = None
