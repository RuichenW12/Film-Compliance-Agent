"""Storage ports.

`api/` and `workers/` depend on these protocols only, so the in-memory store
used by tests and the Firestore store used on Cloud Run stay interchangeable.
"""

from __future__ import annotations

from typing import Protocol

from schemas.assets import AssetVersion, MaterialCard, UploadTicket
from schemas.common import AuditEntry, Fact, TimelineEvent
from schemas.findings import Finding
from schemas.forms import FormDraft
from schemas.project import Project
from schemas.reviews import ReviewSession, ReviewState
from schemas.workflow import (
    InstitutionReview,
    MockInstitution,
    Notification,
    WorkflowTask,
)


class ProjectStore(Protocol):
    def create(self, project: Project) -> Project: ...

    def get(self, project_id: str) -> Project | None: ...

    def save(self, project: Project) -> Project: ...

    def list_all(self) -> list[Project]: ...


class ReviewSessionStore(Protocol):
    def put(self, session: ReviewSession) -> ReviewSession: ...

    def get(self, review_id: str) -> ReviewSession | None: ...

    def compare_and_put(
        self,
        review_id: str,
        expected_state: ReviewState,
        session: ReviewSession,
        *,
        expected_generation: int | None = None,
    ) -> bool: ...


class FactStore(Protocol):
    def add(self, project_id: str, fact: Fact) -> Fact: ...

    def list(self, project_id: str) -> list[Fact]: ...

    def get_by_key(self, project_id: str, key: str) -> Fact | None: ...


class FindingStore(Protocol):
    def add(self, project_id: str, finding: Finding) -> Finding: ...

    def save(self, project_id: str, finding: Finding) -> Finding: ...

    def get(self, project_id: str, finding_id: str) -> Finding | None: ...

    def list(self, project_id: str) -> list[Finding]: ...


class MaterialStore(Protocol):
    def put(self, project_id: str, material: MaterialCard) -> MaterialCard: ...

    def get(self, project_id: str, material_id: str) -> MaterialCard | None: ...

    def list(self, project_id: str) -> list[MaterialCard]: ...


class AssetStore(Protocol):
    def add(self, project_id: str, asset: AssetVersion) -> AssetVersion: ...

    def get(self, project_id: str, version_id: str) -> AssetVersion | None: ...

    def list(self, project_id: str) -> list[AssetVersion]: ...


class BlobStore(Protocol):
    """Raw uploaded bytes. Local in development, object storage in the cloud."""

    def put(self, uri: str, data: bytes) -> str: ...

    def get(self, uri: str) -> bytes | None: ...


class UploadTicketStore(Protocol):
    """One-shot permits. A ticket names what may be written, exactly once."""

    def add(self, ticket: UploadTicket) -> UploadTicket: ...

    def get(self, ticket_id: str) -> UploadTicket | None: ...

    def consume(self, ticket_id: str) -> UploadTicket | None: ...


class TaskStore(Protocol):
    def add(self, task: WorkflowTask) -> WorkflowTask: ...

    def list(self, project_id: str) -> list[WorkflowTask]: ...

    def save(self, task: WorkflowTask) -> WorkflowTask: ...

    def get(self, task_id: str) -> WorkflowTask | None: ...

    def find_by_idempotency_key(self, key: str) -> WorkflowTask | None: ...


class TimelineStore(Protocol):
    def add(self, project_id: str, event: TimelineEvent) -> TimelineEvent: ...

    def list(self, project_id: str) -> list[TimelineEvent]: ...


class AuditStore(Protocol):
    def add(self, project_id: str, entry: AuditEntry) -> AuditEntry: ...

    def list(self, project_id: str) -> list[AuditEntry]: ...


class FormStore(Protocol):
    def put(self, project_id: str, draft: FormDraft) -> FormDraft: ...

    def get(self, project_id: str, draft_id: str) -> FormDraft | None: ...

    def latest(self, project_id: str) -> FormDraft | None: ...


class InstitutionReviewStore(Protocol):
    def put(self, project_id: str, review: InstitutionReview) -> InstitutionReview: ...

    def latest(self, project_id: str) -> InstitutionReview | None: ...


class NotificationStore(Protocol):
    def add(self, notification: Notification) -> Notification: ...

    def get(self, notification_id: str) -> Notification | None: ...

    def list(self, user_id: str, unread_only: bool = False) -> list[Notification]: ...

    def mark_read(self, notification_id: str) -> Notification | None: ...


class InstitutionRegistry(Protocol):
    def get(self, institution_id: str) -> MockInstitution | None: ...

    def list(self) -> list[MockInstitution]: ...
