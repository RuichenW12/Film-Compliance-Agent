"""In-memory store. Same ports as the Firestore adapter, no emulator required."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Protocol

from schemas.assets import AssetVersion, MaterialCard, UploadTicket
from schemas.common import AuditEntry, Fact, TimelineEvent
from schemas.findings import Finding
from schemas.forms import FormDraft
from schemas.project import Project
from schemas.workflow import (
    InstitutionReview,
    MockInstitution,
    Notification,
    WorkflowTask,
)


class InMemoryProjectStore:
    def __init__(self) -> None:
        self._items: dict[str, Project] = {}

    def create(self, project: Project) -> Project:
        if project.project_id in self._items:
            raise KeyError(f"project already exists: {project.project_id}")
        self._items[project.project_id] = project
        return project

    def get(self, project_id: str) -> Project | None:
        return self._items.get(project_id)

    def save(self, project: Project) -> Project:
        self._items[project.project_id] = project
        return project

    def list_all(self) -> list[Project]:
        return list(self._items.values())


class InMemoryFactStore:
    def __init__(self) -> None:
        self._items: dict[str, list[Fact]] = defaultdict(list)

    def add(self, project_id: str, fact: Fact) -> Fact:
        self._items[project_id].append(fact)
        return fact

    def list(self, project_id: str) -> list[Fact]:
        return list(self._items[project_id])

    def get_by_key(self, project_id: str, key: str) -> Fact | None:
        for fact in reversed(self._items[project_id]):
            if fact.key == key:
                return fact
        return None


class InMemoryFindingStore:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Finding]] = defaultdict(dict)

    def add(self, project_id: str, finding: Finding) -> Finding:
        self._items[project_id][finding.finding_id] = finding
        return finding

    def save(self, project_id: str, finding: Finding) -> Finding:
        self._items[project_id][finding.finding_id] = finding
        return finding

    def get(self, project_id: str, finding_id: str) -> Finding | None:
        return self._items[project_id].get(finding_id)

    def list(self, project_id: str) -> list[Finding]:
        return list(self._items[project_id].values())


class InMemoryMaterialStore:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, MaterialCard]] = defaultdict(dict)

    def put(self, project_id: str, material: MaterialCard) -> MaterialCard:
        self._items[project_id][material.material_id] = material
        return material

    def get(self, project_id: str, material_id: str) -> MaterialCard | None:
        return self._items[project_id].get(material_id)

    def list(self, project_id: str) -> list[MaterialCard]:
        return list(self._items[project_id].values())


class InMemoryAssetStore:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, AssetVersion]] = defaultdict(dict)

    def add(self, project_id: str, asset: AssetVersion) -> AssetVersion:
        self._items[project_id][asset.version_id] = asset
        return asset

    def get(self, project_id: str, version_id: str) -> AssetVersion | None:
        return self._items[project_id].get(version_id)

    def list(self, project_id: str) -> list[AssetVersion]:
        return list(self._items[project_id].values())


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._items: dict[str, WorkflowTask] = {}
        self._by_key: dict[str, str] = {}

    def add(self, task: WorkflowTask) -> WorkflowTask:
        self._items[task.task_id] = task
        self._by_key.setdefault(task.idempotency_key, task.task_id)
        return task

    def save(self, task: WorkflowTask) -> WorkflowTask:
        self._items[task.task_id] = task
        return task

    def get(self, task_id: str) -> WorkflowTask | None:
        return self._items.get(task_id)

    def list(self, project_id: str) -> list[WorkflowTask]:
        return [task for task in self._items.values() if task.project_id == project_id]

    def find_by_idempotency_key(self, key: str) -> WorkflowTask | None:
        task_id = self._by_key.get(key)
        return self._items.get(task_id) if task_id else None


class InMemoryTimelineStore:
    def __init__(self) -> None:
        self._items: dict[str, list[TimelineEvent]] = defaultdict(list)

    def add(self, project_id: str, event: TimelineEvent) -> TimelineEvent:
        self._items[project_id].append(event)
        return event

    def list(self, project_id: str) -> list[TimelineEvent]:
        return list(self._items[project_id])


class InMemoryAuditStore:
    def __init__(self) -> None:
        self._items: dict[str, list[AuditEntry]] = defaultdict(list)

    def add(self, project_id: str, entry: AuditEntry) -> AuditEntry:
        self._items[project_id].append(entry)
        return entry

    def list(self, project_id: str) -> list[AuditEntry]:
        return list(self._items[project_id])


class InMemoryFormStore:
    def __init__(self) -> None:
        self._items: dict[str, list[FormDraft]] = defaultdict(list)

    def put(self, project_id: str, draft: FormDraft) -> FormDraft:
        drafts = self._items[project_id]
        for index, existing in enumerate(drafts):
            if existing.draft_id == draft.draft_id:
                drafts[index] = draft
                return draft
        drafts.append(draft)
        return draft

    def get(self, project_id: str, draft_id: str) -> FormDraft | None:
        for draft in self._items[project_id]:
            if draft.draft_id == draft_id:
                return draft
        return None

    def latest(self, project_id: str) -> FormDraft | None:
        drafts = self._items[project_id]
        return drafts[-1] if drafts else None


class InMemoryInstitutionReviewStore:
    def __init__(self) -> None:
        self._items: dict[str, list[InstitutionReview]] = defaultdict(list)

    def put(self, project_id: str, review: InstitutionReview) -> InstitutionReview:
        reviews = self._items[project_id]
        for index, existing in enumerate(reviews):
            if existing.review_id == review.review_id:
                reviews[index] = review
                return review
        reviews.append(review)
        return review

    def latest(self, project_id: str) -> InstitutionReview | None:
        reviews = self._items[project_id]
        return reviews[-1] if reviews else None


EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _created_at(notification: Notification) -> datetime:
    return notification.created_at or EPOCH


class InMemoryNotificationStore:
    def __init__(self) -> None:
        self._items: dict[str, Notification] = {}

    def add(self, notification: Notification) -> Notification:
        self._items[notification.notification_id] = notification
        return notification

    def get(self, notification_id: str) -> Notification | None:
        return self._items.get(notification_id)

    def list(self, user_id: str, unread_only: bool = False) -> list[Notification]:
        """Newest first: an inbox is read from the top."""

        matching = [
            item
            for item in self._items.values()
            if item.user_id == user_id and (not unread_only or not item.read)
        ]
        return sorted(matching, key=_created_at, reverse=True)

    def mark_read(self, notification_id: str) -> Notification | None:
        item = self._items.get(notification_id)
        if item is None:
            return None
        updated = item.model_copy(update={"read": True})
        self._items[notification_id] = updated
        return updated


class InMemoryInstitutionRegistry:
    def __init__(self, institutions: list[MockInstitution] | None = None) -> None:
        self._items = {item.institution_id: item for item in (institutions or [])}

    def load(self, institutions: list[MockInstitution]) -> None:
        self._items = {item.institution_id: item for item in institutions}

    def get(self, institution_id: str) -> MockInstitution | None:
        return self._items.get(institution_id)

    def list(self) -> list[MockInstitution]:
        return list(self._items.values())


class InMemoryBlobStore:
    """Raw bytes, keyed by storage uri. A GCS adapter slots in behind this."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    def put(self, uri: str, data: bytes) -> str:
        self._blobs[uri] = data
        return uri

    def get(self, uri: str) -> bytes | None:
        return self._blobs.get(uri)


class InMemoryUploadTicketStore:
    def __init__(self) -> None:
        self._items: dict[str, UploadTicket] = {}

    def add(self, ticket: UploadTicket) -> UploadTicket:
        self._items[ticket.ticket_id] = ticket
        return ticket

    def get(self, ticket_id: str) -> UploadTicket | None:
        return self._items.get(ticket_id)

    def consume(self, ticket_id: str) -> UploadTicket | None:
        """Mark spent and return it, or None if it was already spent."""

        ticket = self._items.get(ticket_id)
        if ticket is None or ticket.consumed:
            return None
        spent = ticket.model_copy(update={"consumed": True})
        self._items[ticket_id] = spent
        return spent


class Stores(Protocol):
    """The bundle the API and workers receive by dependency injection."""

    projects: object
    facts: object
    findings: object
    materials: object
    assets: object
    blobs: object
    upload_tickets: object
    tasks: object
    timeline: object
    audit: object
    forms: object
    institution_reviews: object
    notifications: object
    institutions: object


@dataclass
class InMemoryStores:
    projects: InMemoryProjectStore = field(default_factory=InMemoryProjectStore)
    facts: InMemoryFactStore = field(default_factory=InMemoryFactStore)
    findings: InMemoryFindingStore = field(default_factory=InMemoryFindingStore)
    materials: InMemoryMaterialStore = field(default_factory=InMemoryMaterialStore)
    assets: InMemoryAssetStore = field(default_factory=InMemoryAssetStore)
    blobs: InMemoryBlobStore = field(default_factory=InMemoryBlobStore)
    upload_tickets: InMemoryUploadTicketStore = field(
        default_factory=InMemoryUploadTicketStore
    )
    tasks: InMemoryTaskStore = field(default_factory=InMemoryTaskStore)
    timeline: InMemoryTimelineStore = field(default_factory=InMemoryTimelineStore)
    audit: InMemoryAuditStore = field(default_factory=InMemoryAuditStore)
    forms: InMemoryFormStore = field(default_factory=InMemoryFormStore)
    institution_reviews: InMemoryInstitutionReviewStore = field(
        default_factory=InMemoryInstitutionReviewStore
    )
    notifications: InMemoryNotificationStore = field(
        default_factory=InMemoryNotificationStore
    )
    institutions: InMemoryInstitutionRegistry = field(
        default_factory=InMemoryInstitutionRegistry
    )
