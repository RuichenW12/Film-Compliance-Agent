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
    text_storage_uri: str | None = None
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_version: str | None = None
    diff_summary: str | None = None
    uploaded_by: str
    created_at: AwareDatetime


class MaterialCard(DomainModel):
    """One S5 collection card: what, why, template, common rejects."""

    material_id: str
    name_key: str
    asset_kind: AssetKind
    required: bool = True
    why_clause: EvidenceRef | None = None
    template_uri: str | None = None
    common_rejects_key: str | None = None
    status: MaterialStatus = MaterialStatus.PENDING
    asset_version: str | None = None
    invalid_reasons: list[str] = Field(default_factory=list)
    waive_reason: str | None = None


class UploadTicket(DomainModel):
    """A one-shot permit to write one asset version.

    The product issues a ticket instead of a bare route so the same flow works
    for a local upload and for a signed object-storage URL later: only
    `upload_url` and `backend` differ.
    """

    ticket_id: str
    project_id: str
    kind: AssetKind
    storage_uri: str
    issued_to: str
    filename: str | None = None
    consumed: bool = False
    created_at: AwareDatetime
