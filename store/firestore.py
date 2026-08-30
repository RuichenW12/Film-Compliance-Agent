"""The same ports again, on Firestore.

Why a third backend rather than deploying the SQLite one: Cloud Run replaces
containers freely and runs several at once. A SQLite file lives on a container
filesystem, so a project created on one instance is invisible to the next and
gone at the next revision. `store.sqlite` says as much in its own docstring --
it exists because Firestore was not reachable at the time, and it names this
file as the drop-in that would follow.

The shape is deliberately the same as `store.sqlite`: one logical collection per
kind of document, a `parent` naming the project it belongs to, and a monotonic
`ordinal` fixing insertion order. `store.memory` returns insertion order for
free because dicts preserve it; both durable backends have to work for that
promise, and `tests/test_store_conformance.py` runs the same assertions against
all three.

Two decisions worth knowing before changing anything here:

**Ordering is done in Python, not by Firestore.** Every `list()` fetches by an
equality filter on `parent` and sorts locally. Ordering in the query instead
would need a composite index (`parent ASC, ordinal ASC`) per collection, which
means index definitions that must be deployed before the code that needs them,
and a confusing runtime failure when they are missing. At this volume -- a
project has tens of documents, not thousands -- sorting locally costs nothing
and removes a whole class of deployment mistake. Revisit if any collection
starts holding thousands of documents for one parent.

**The ordinal comes from a transactional counter.** One document,
`_counters/ordinal`, incremented in a transaction per write. That serialises
writes, which is the price of preserving exact insertion order across
instances. A timestamp would avoid the round trip but two writes in the same
millisecond would tie, and the conformance suite asserts order.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore
from pydantic import BaseModel

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

# A Firestore document is capped at roughly 1 MiB including field names and
# overhead, and base64 inflates bytes by a third. Refusing early with a
# readable message beats a client-library error from three frames down. The
# real answer for anything this size is Cloud Storage; scripts and synopses --
# the only things uploaded today -- are kilobytes.
MAX_BLOB_BYTES = 700_000

COUNTERS = "_counters"
ORDINAL = "ordinal"


class Database:
    """A Firestore client plus the ordinal sequence.

    Mirrors `store.sqlite.Database` so the store classes below read the same
    way as their SQLite counterparts.
    """

    def __init__(
        self,
        project: str | None = None,
        database: str | None = None,
        client: firestore.Client | None = None,
        namespace: str = "",
    ) -> None:
        # `namespace` prefixes every collection. Tests use it to isolate runs
        # inside one emulator; production leaves it empty.
        self._namespace = namespace
        if client is not None:
            self.client = client
        elif database:
            self.client = firestore.Client(project=project, database=database)
        else:
            self.client = firestore.Client(project=project)

    def collection(self, name: str):
        return self.client.collection(f"{self._namespace}{name}")

    def next_ordinal(self) -> int:
        """One sequence across every collection, as in the SQLite store.

        Per-collection sequences would order each list correctly, but a single
        sequence also keeps the write order across collections recoverable.
        """

        ref = self.collection(COUNTERS).document(ORDINAL)

        @firestore.transactional
        def _bump(transaction) -> int:
            snapshot = ref.get(transaction=transaction)
            current = snapshot.get("value") if snapshot.exists else 0
            nxt = int(current or 0) + 1
            transaction.set(ref, {"value": nxt})
            return nxt

        return _bump(self.client.transaction())

    def close(self) -> None:
        self.client.close()


@dataclass
class Collection:
    """Typed read and write over one logical collection.

    Same surface as `store.sqlite.Collection`, so the store classes below are
    the SQLite ones with the backend swapped.
    """

    db: Database
    name: str
    model: type[BaseModel]

    def _key(self, parent: str, doc_id: str) -> str:
        # Firestore forbids "/" in a document id, so the SQLite key format
        # cannot be reused verbatim. "__" is safe: every id in this system is
        # a prefixed ULID or a snake_case constant, and none contains it.
        return f"{parent}__{doc_id}" if parent else doc_id

    def _ref(self, parent: str, doc_id: str):
        return self.db.collection(self.name).document(self._key(parent, doc_id))

    def _load(self, data: dict[str, Any]):
        return self.model.model_validate_json(data["payload"])

    def put(self, parent: str, doc_id: str, document: BaseModel) -> None:
        """Insert, or update in place keeping the original ordinal.

        Keeping the ordinal matters: `FormStore.put` replaces a draft by id and
        the memory store leaves it where it was, so `latest()` must not
        silently reorder when an existing draft is saved again.
        """

        ref = self._ref(parent, doc_id)
        snapshot = ref.get()
        ordinal = (
            snapshot.get("ordinal")
            if snapshot.exists
            else self.db.next_ordinal()
        )
        ref.set(
            {
                "parent": parent,
                "ordinal": ordinal,
                "payload": document.model_dump_json(),
            }
        )

    def append(self, parent: str, doc_id: str | None, document: BaseModel) -> None:
        """Always a new ordinal. For collections that are logs, not maps.

        `doc_id` may be None for a record with no identity of its own --
        `AuditEntry` has no id field, because an audit line is only appended
        and read back in order. The ordinal then serves as the key.
        """

        ordinal = self.db.next_ordinal()
        key = doc_id if doc_id is not None else f"#{ordinal}"
        self._ref(parent, key).set(
            {
                "parent": parent,
                "ordinal": ordinal,
                "payload": document.model_dump_json(),
            }
        )

    def get(self, parent: str, doc_id: str):
        snapshot = self._ref(parent, doc_id).get()
        return self._load(snapshot.to_dict()) if snapshot.exists else None

    def list(self, parent: str) -> list:
        # Equality filter only; ordering happens below. See the module
        # docstring on why this does not order in the query.
        docs = [
            doc.to_dict()
            for doc in self.db.collection(self.name).where(
                filter=firestore.FieldFilter("parent", "==", parent)
            ).stream()
        ]
        return [self._load(d) for d in sorted(docs, key=lambda d: d["ordinal"])]

    def list_all(self) -> list:
        docs = [doc.to_dict() for doc in self.db.collection(self.name).stream()]
        return [self._load(d) for d in sorted(docs, key=lambda d: d["ordinal"])]

    def exists(self, parent: str, doc_id: str) -> bool:
        return self._ref(parent, doc_id).get().exists

    def clear(self) -> None:
        for doc in self.db.collection(self.name).stream():
            doc.reference.delete()


class FirestoreProjectStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "projects", Project)

    def create(self, project: Project) -> Project:
        if self._c.exists("", project.project_id):
            raise KeyError(f"project already exists: {project.project_id}")
        self._c.put("", project.project_id, project)
        return project

    def get(self, project_id: str) -> Project | None:
        return self._c.get("", project_id)

    def save(self, project: Project) -> Project:
        self._c.put("", project.project_id, project)
        return project

    def list_all(self) -> list[Project]:
        return self._c.list_all()


class FirestoreFactStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "facts", Fact)

    def add(self, project_id: str, fact: Fact) -> Fact:
        self._c.append(project_id, fact.fact_id, fact)
        return fact

    def list(self, project_id: str) -> list[Fact]:
        return self._c.list(project_id)

    def get_by_key(self, project_id: str, key: str) -> Fact | None:
        # Last write wins, matching the memory store's reversed() scan.
        for fact in reversed(self._c.list(project_id)):
            if fact.key == key:
                return fact
        return None


class FirestoreFindingStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "findings", Finding)

    def add(self, project_id: str, finding: Finding) -> Finding:
        self._c.put(project_id, finding.finding_id, finding)
        return finding

    def save(self, project_id: str, finding: Finding) -> Finding:
        self._c.put(project_id, finding.finding_id, finding)
        return finding

    def get(self, project_id: str, finding_id: str) -> Finding | None:
        return self._c.get(project_id, finding_id)

    def list(self, project_id: str) -> list[Finding]:
        return self._c.list(project_id)


class FirestoreMaterialStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "materials", MaterialCard)

    def put(self, project_id: str, material: MaterialCard) -> MaterialCard:
        self._c.put(project_id, material.material_id, material)
        return material

    def get(self, project_id: str, material_id: str) -> MaterialCard | None:
        return self._c.get(project_id, material_id)

    def list(self, project_id: str) -> list[MaterialCard]:
        return self._c.list(project_id)


class FirestoreAssetStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "assets", AssetVersion)

    def add(self, project_id: str, asset: AssetVersion) -> AssetVersion:
        self._c.put(project_id, asset.version_id, asset)
        return asset

    def get(self, project_id: str, version_id: str) -> AssetVersion | None:
        return self._c.get(project_id, version_id)

    def list(self, project_id: str) -> list[AssetVersion]:
        return self._c.list(project_id)


class FirestoreTaskStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "tasks", WorkflowTask)

    def add(self, task: WorkflowTask) -> WorkflowTask:
        self._c.put("", task.task_id, task)
        return task

    def save(self, task: WorkflowTask) -> WorkflowTask:
        self._c.put("", task.task_id, task)
        return task

    def get(self, task_id: str) -> WorkflowTask | None:
        return self._c.get("", task_id)

    def list(self, project_id: str) -> list[WorkflowTask]:
        return [task for task in self._c.list_all() if task.project_id == project_id]

    def find_by_idempotency_key(self, key: str) -> WorkflowTask | None:
        # First writer wins, matching the memory store's setdefault. A retry
        # must return the original task, never a second one.
        for task in self._c.list_all():
            if task.idempotency_key == key:
                return task
        return None


class FirestoreTimelineStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "timeline", TimelineEvent)

    def add(self, project_id: str, event: TimelineEvent) -> TimelineEvent:
        self._c.append(project_id, event.event_id, event)
        return event

    def list(self, project_id: str) -> list[TimelineEvent]:
        return self._c.list(project_id)


class FirestoreAuditStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "audit", AuditEntry)

    def add(self, project_id: str, entry: AuditEntry) -> AuditEntry:
        self._c.append(project_id, None, entry)
        return entry

    def list(self, project_id: str) -> list[AuditEntry]:
        return self._c.list(project_id)


class FirestoreFormStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "forms", FormDraft)

    def put(self, project_id: str, draft: FormDraft) -> FormDraft:
        self._c.put(project_id, draft.draft_id, draft)
        return draft

    def get(self, project_id: str, draft_id: str) -> FormDraft | None:
        return self._c.get(project_id, draft_id)

    def latest(self, project_id: str) -> FormDraft | None:
        drafts = self._c.list(project_id)
        return drafts[-1] if drafts else None


class FirestoreInstitutionReviewStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "institution_reviews", InstitutionReview)

    def put(self, project_id: str, review: InstitutionReview) -> InstitutionReview:
        self._c.put(project_id, review.review_id, review)
        return review

    def latest(self, project_id: str) -> InstitutionReview | None:
        reviews = self._c.list(project_id)
        return reviews[-1] if reviews else None


EPOCH = datetime.min.replace(tzinfo=timezone.utc)


class FirestoreNotificationStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "notifications", Notification)

    def add(self, notification: Notification) -> Notification:
        self._c.put("", notification.notification_id, notification)
        return notification

    def get(self, notification_id: str) -> Notification | None:
        return self._c.get("", notification_id)

    def list(self, user_id: str, unread_only: bool = False) -> list[Notification]:
        matching = [
            item
            for item in self._c.list_all()
            if item.user_id == user_id and (not unread_only or not item.read)
        ]
        # Newest first: an inbox is read from the top.
        return sorted(matching, key=lambda item: item.created_at or EPOCH, reverse=True)

    def mark_read(self, notification_id: str) -> Notification | None:
        item = self._c.get("", notification_id)
        if item is None:
            return None
        updated = item.model_copy(update={"read": True})
        self._c.put("", notification_id, updated)
        return updated


class FirestoreInstitutionRegistry:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "institutions", MockInstitution)

    def load(self, institutions: list[MockInstitution]) -> None:
        self._c.clear()
        for item in institutions:
            self._c.put("", item.institution_id, item)

    def get(self, institution_id: str) -> MockInstitution | None:
        return self._c.get("", institution_id)

    def list(self) -> list[MockInstitution]:
        return self._c.list_all()


class FirestoreBlobStore:
    """Uploaded bytes, base64 in a document.

    This is the one store here that is a stopgap rather than the destination.
    Cloud Storage is where uploads belong -- see the GCS adapter in phase 5b --
    and until it lands, a document keeps the backend complete and the ports
    honest. `MAX_BLOB_BYTES` refuses anything that would not fit, with a
    message naming the real limit, rather than letting the client library fail
    obscurely on a document that is too large.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def put(self, uri: str, data: bytes) -> str:
        if len(data) > MAX_BLOB_BYTES:
            raise ValueError(
                f"{len(data)} bytes exceeds the {MAX_BLOB_BYTES} this backend "
                "can hold; uploads this size need the Cloud Storage blob store"
            )
        # A URI contains slashes; a document id may not.
        key = base64.urlsafe_b64encode(uri.encode()).decode().rstrip("=")
        self._db.collection("blobs").document(key).set(
            {"uri": uri, "data": base64.b64encode(data).decode()}
        )
        return uri

    def get(self, uri: str) -> bytes | None:
        key = base64.urlsafe_b64encode(uri.encode()).decode().rstrip("=")
        snapshot = self._db.collection("blobs").document(key).get()
        if not snapshot.exists:
            return None
        return base64.b64decode(snapshot.to_dict()["data"])


class FirestoreUploadTicketStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "upload_tickets", UploadTicket)

    def add(self, ticket: UploadTicket) -> UploadTicket:
        self._c.put("", ticket.ticket_id, ticket)
        return ticket

    def get(self, ticket_id: str) -> UploadTicket | None:
        return self._c.get("", ticket_id)

    def consume(self, ticket_id: str) -> UploadTicket | None:
        """Mark spent and return it, or None if missing or already spent."""

        ticket = self._c.get("", ticket_id)
        if ticket is None or ticket.consumed:
            return None
        spent = ticket.model_copy(update={"consumed": True})
        self._c.put("", ticket_id, spent)
        return spent


@dataclass
class FirestoreStores:
    """The same bundle as `InMemoryStores`, sharing one Firestore database."""

    db: Database

    def __post_init__(self) -> None:
        self.projects = FirestoreProjectStore(self.db)
        self.facts = FirestoreFactStore(self.db)
        self.findings = FirestoreFindingStore(self.db)
        self.materials = FirestoreMaterialStore(self.db)
        self.assets = FirestoreAssetStore(self.db)
        self.blobs = FirestoreBlobStore(self.db)
        self.upload_tickets = FirestoreUploadTicketStore(self.db)
        self.tasks = FirestoreTaskStore(self.db)
        self.timeline = FirestoreTimelineStore(self.db)
        self.audit = FirestoreAuditStore(self.db)
        self.forms = FirestoreFormStore(self.db)
        self.institution_reviews = FirestoreInstitutionReviewStore(self.db)
        self.notifications = FirestoreNotificationStore(self.db)
        self.institutions = FirestoreInstitutionRegistry(self.db)

    @classmethod
    def for_project(
        cls,
        project: str | None = None,
        database: str | None = None,
        namespace: str = "",
    ) -> "FirestoreStores":
        return cls(Database(project=project, database=database, namespace=namespace))
