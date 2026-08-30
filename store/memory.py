"""In-memory store. Same ports as the Firestore adapter, no emulator required."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from dataclasses import dataclass, field
from functools import wraps
import threading
from typing import Protocol

from core.repositories import (
    ReviewAnalysisBaseline,
    ReviewAnalysisPublication,
    ReviewAnalysisStage,
    validate_review_analysis_publication,
)

from schemas.assets import AssetVersion, MaterialCard, UploadTicket
from schemas.common import AuditEntry, Fact, TimelineEvent
from schemas.enums import TaskStatus
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


class InMemoryReviewSessionStore:
    def __init__(self) -> None:
        self._items: dict[str, ReviewSession] = {}
        self._lock = threading.Lock()

    def put(self, session: ReviewSession) -> ReviewSession:
        self._items[session.review_id] = session
        return session

    def get(self, review_id: str) -> ReviewSession | None:
        return self._items.get(review_id)

    def compare_and_put(
        self,
        review_id: str,
        expected_state: ReviewState,
        session: ReviewSession,
        *,
        expected_generation: int | None = None,
    ) -> bool:
        with self._lock:
            current = self._items.get(review_id)
            if current is None or current.state is not expected_state:
                return False
            if (
                expected_generation is not None
                and current.generation != expected_generation
            ):
                return False
            self._items[review_id] = session
            return True


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

    def get_or_create_by_idempotency_key(
        self, task: WorkflowTask
    ) -> tuple[WorkflowTask, bool]:
        existing = self.find_by_idempotency_key(task.idempotency_key)
        if existing is not None:
            return existing, False
        self.add(task)
        return task, True

    def claim_queued_task(
        self, task_id: str, updated_at: datetime
    ) -> WorkflowTask | None:
        task = self._items.get(task_id)
        if task is None or task.status is not TaskStatus.QUEUED:
            return None
        running = task.model_copy(
            update={"status": TaskStatus.RUNNING, "updated_at": updated_at}
        )
        self._items[task_id] = running
        return running


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

    def list(self, project_id: str) -> list[FormDraft]:
        return list(self._items[project_id])


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
    review_sessions: object
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

    def publish_review_analysis(
        self, publication: ReviewAnalysisPublication
    ) -> bool: ...

    def stage_review_analysis(
        self, review_id: str, project_id: str
    ) -> ReviewAnalysisStage: ...

    def prepare_review_analysis_publication(
        self, stage: ReviewAnalysisStage, session: ReviewSession
    ) -> ReviewAnalysisPublication: ...


class _SynchronizedStore:
    """Serialize every ordinary memory-store operation with bundle publication."""

    def __init__(self, target, lock: threading.RLock) -> None:
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_lock", lock)

    def __getattr__(self, name):
        value = getattr(self._target, name)
        if not callable(value):
            return value

        @wraps(value)
        def synchronized(*args, **kwargs):
            with self._lock:
                return value(*args, **kwargs)

        return synchronized

    def __setattr__(self, name, value) -> None:
        if name in {"_target", "_lock"}:
            object.__setattr__(self, name, value)
            return
        setattr(self._target, name, value)


@dataclass
class InMemoryStores:
    projects: InMemoryProjectStore = field(default_factory=InMemoryProjectStore)
    review_sessions: InMemoryReviewSessionStore = field(
        default_factory=InMemoryReviewSessionStore
    )
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
    _transaction_lock: threading.RLock = field(
        default_factory=threading.RLock,
        repr=False,
    )

    def __post_init__(self) -> None:
        for name in (
            "projects",
            "review_sessions",
            "facts",
            "findings",
            "materials",
            "assets",
            "blobs",
            "upload_tickets",
            "tasks",
            "timeline",
            "audit",
            "forms",
            "institution_reviews",
            "notifications",
            "institutions",
        ):
            setattr(
                self,
                name,
                _SynchronizedStore(getattr(self, name), self._transaction_lock),
            )

    def stage_review_analysis(
        self, review_id: str, project_id: str
    ) -> ReviewAnalysisStage:
        with self._transaction_lock:
            session = self.review_sessions._items.get(review_id)
            project = self.projects._items.get(project_id)
            if session is None or project is None:
                raise KeyError(f"review aggregate not found: {review_id}/{project_id}")
            baseline = ReviewAnalysisBaseline(
                session=deepcopy(session),
                project=deepcopy(project),
                facts=tuple(deepcopy(self.facts._items[project_id])),
                findings=tuple(
                    deepcopy(list(self.findings._items[project_id].values()))
                ),
                forms=tuple(deepcopy(self.forms._items[project_id])),
                tasks=tuple(
                    deepcopy(
                        [
                            task
                            for task in self.tasks._items.values()
                            if task.project_id == project_id
                        ]
                    )
                ),
                timeline=tuple(deepcopy(self.timeline._items[project_id])),
                audit=tuple(deepcopy(self.audit._items[project_id])),
            )
            assets = deepcopy(list(self.assets._items[project_id].values()))
            blobs: dict[str, bytes] = {}
            for asset in assets:
                for uri in (asset.storage_uri, asset.text_storage_uri):
                    if uri and uri in self.blobs._blobs:
                        blobs[uri] = self.blobs._blobs[uri]

        staged = InMemoryStores()
        staged.projects.create(deepcopy(baseline.project))
        for fact in baseline.facts:
            staged.facts.add(project_id, deepcopy(fact))
        for finding in baseline.findings:
            staged.findings.add(project_id, deepcopy(finding))
        for form in baseline.forms:
            staged.forms.put(project_id, deepcopy(form))
        for task in baseline.tasks:
            staged.tasks.add(deepcopy(task))
        for event in baseline.timeline:
            staged.timeline.add(project_id, deepcopy(event))
        for entry in baseline.audit:
            staged.audit.add(project_id, deepcopy(entry))
        for asset in assets:
            staged.assets.add(project_id, asset)
        for uri, content in blobs.items():
            staged.blobs.put(uri, content)
        return ReviewAnalysisStage(baseline=baseline, stores=staged)

    def prepare_review_analysis_publication(
        self, stage: ReviewAnalysisStage, session: ReviewSession
    ) -> ReviewAnalysisPublication:
        staged = stage.stores
        project = staged.projects.get(session.project_id)
        if project is None:
            raise KeyError(f"project not found: {session.project_id}")
        return ReviewAnalysisPublication(
            baseline=stage.baseline,
            session=session,
            project=project,
            facts=tuple(staged.facts.list(session.project_id)),
            findings=tuple(staged.findings.list(session.project_id)),
            forms=tuple(staged.forms.list(session.project_id)),
            tasks=tuple(staged.tasks.list(session.project_id)),
            timeline=tuple(staged.timeline.list(session.project_id)),
            audit=tuple(staged.audit.list(session.project_id)),
        )

    def publish_review_analysis(
        self, publication: ReviewAnalysisPublication
    ) -> bool:
        project_id = validate_review_analysis_publication(publication)
        baseline = publication.baseline
        with self._transaction_lock, self.review_sessions._lock:
            current = self.review_sessions._items.get(publication.session.review_id)
            live_project = self.projects._items.get(project_id)
            live_facts = tuple(self.facts._items[project_id])
            live_findings = tuple(self.findings._items[project_id].values())
            live_forms = tuple(self.forms._items[project_id])
            live_tasks = tuple(
                task
                for task in self.tasks._items.values()
                if task.project_id == project_id
            )
            live_timeline = tuple(self.timeline._items[project_id])
            live_audit = tuple(self.audit._items[project_id])
            if (
                current is None
                or current.state is not ReviewState.ANALYZING
                or current.generation != publication.session.generation
                or live_project != baseline.project
                or live_facts != baseline.facts
                or live_findings != baseline.findings
                or live_forms != baseline.forms
                or live_tasks != baseline.tasks
                or live_timeline != baseline.timeline
                or live_audit != baseline.audit
            ):
                return False

            facts = list(publication.facts)
            findings = {
                finding.finding_id: finding for finding in publication.findings
            }
            forms = list(publication.forms)
            tasks = {task.task_id: task for task in publication.tasks}
            timeline = list(publication.timeline)
            audit = list(publication.audit)

            self.projects._items[project_id] = publication.project
            self.facts._items[project_id] = facts
            self.findings._items[project_id] = findings
            self.forms._items[project_id] = forms
            old_task_ids = {
                task_id
                for task_id, task in self.tasks._items.items()
                if task.project_id == project_id
            }
            for task_id in old_task_ids:
                self.tasks._items.pop(task_id, None)
            for key, task_id in list(self.tasks._by_key.items()):
                if task_id in old_task_ids:
                    self.tasks._by_key.pop(key, None)
            self.tasks._items.update(tasks)
            for task in tasks.values():
                self.tasks._by_key.setdefault(task.idempotency_key, task.task_id)
            self.timeline._items[project_id] = timeline
            self.audit._items[project_id] = audit
            self.review_sessions._items[publication.session.review_id] = (
                publication.session
            )
            return True
