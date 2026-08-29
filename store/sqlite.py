"""A durable store behind the same ports as `store.memory`.

Everything vanished on restart, which made the product impossible to show
twice: a demo had to be built live each time, and an e2e run against a
long-lived server told a different story from one against a fresh process.

This is SQLite rather than Firestore deliberately. Firestore is the production
target named in `CLAUDE.md`, but it is not enabled on the project and Docker is
not installed, so a Firestore adapter could be written here and never once run
-- and an unrunnable adapter is not a verified one. SQLite needs nothing
installed, so this is testable today, and it sits behind the identical ports so
Firestore remains a drop-in later. It also does something one implementation
never can: proves the ports are real ports. `tests/test_store_conformance.py`
runs the same assertions against both backends.

Shape: one `documents` table holding JSON, keyed by `(collection, doc_key)`,
with a `parent` column for the project a document belongs to and a monotonic
`ordinal` for insertion order. Every `list()` in the memory store returns
insertion order -- dicts and lists preserve it for free -- so the ordinal is
what keeps that promise here rather than an accident of storage.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, TypeVar

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

M = TypeVar("M", bound=BaseModel)

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    collection TEXT NOT NULL,
    doc_key    TEXT NOT NULL,
    parent     TEXT NOT NULL DEFAULT '',
    ordinal    INTEGER NOT NULL,
    payload    TEXT NOT NULL,
    PRIMARY KEY (collection, doc_key)
);
CREATE INDEX IF NOT EXISTS documents_by_parent
    ON documents (collection, parent, ordinal);

CREATE TABLE IF NOT EXISTS blobs (
    uri  TEXT PRIMARY KEY,
    data BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS counters (
    name  TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
"""


class Database:
    """One connection, guarded by a lock.

    FastAPI serves requests from a thread pool, so `check_same_thread` has to
    be off and writes have to be serialised. A single connection with a lock is
    the honest choice at this scale: it cannot interleave a read and a write
    halfway through, and it keeps the file consistent without a pool to reason
    about.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.path, check_same_thread=False, isolation_level=None
        )
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.executescript(SCHEMA)

    def execute(self, sql: str, params: Iterable = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._connection.execute(sql, tuple(params))

    def query(self, sql: str, params: Iterable = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._connection.execute(sql, tuple(params)).fetchall())

    def next_ordinal(self) -> int:
        """A single sequence across every collection.

        Per-collection sequences would be enough for ordering within a list,
        but one sequence also makes the write order across collections
        recoverable, which is worth more than the contention it costs here.
        """

        with self._lock:
            self._connection.execute(
                "INSERT INTO counters (name, value) VALUES ('ordinal', 0) "
                "ON CONFLICT(name) DO UPDATE SET value = value + 1"
            )
            row = self._connection.execute(
                "SELECT value FROM counters WHERE name = 'ordinal'"
            ).fetchone()
            return int(row["value"])

    def close(self) -> None:
        with self._lock:
            self._connection.close()


@dataclass
class Collection:
    """Typed read and write over one logical collection."""

    db: Database
    name: str
    model: type[BaseModel]

    def _key(self, parent: str, doc_id: str) -> str:
        return f"{parent}/{doc_id}" if parent else doc_id

    def put(self, parent: str, doc_id: str, document: BaseModel) -> None:
        """Insert, or update in place keeping the original ordinal.

        Keeping the ordinal matters: `FormStore.put` replaces a draft by id and
        the memory store leaves it where it was in the list, so `latest()` does
        not silently reorder when an existing draft is saved again.
        """

        key = self._key(parent, doc_id)
        existing = self.db.query(
            "SELECT ordinal FROM documents WHERE collection = ? AND doc_key = ?",
            (self.name, key),
        )
        ordinal = existing[0]["ordinal"] if existing else self.db.next_ordinal()
        self.db.execute(
            "INSERT INTO documents (collection, doc_key, parent, ordinal, payload) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(collection, doc_key) DO UPDATE SET payload = excluded.payload",
            (self.name, key, parent, ordinal, document.model_dump_json()),
        )

    def append(self, parent: str, doc_id: str | None, document: BaseModel) -> None:
        """Always a new ordinal. For collections that are logs, not maps.

        `doc_id` may be None for a record with no identity of its own --
        `AuditEntry` has no id field, because an audit line is only ever
        appended and read back in order. The ordinal then serves as the key,
        which is unique by construction.
        """

        ordinal = self.db.next_ordinal()
        key = self._key(parent, doc_id if doc_id is not None else f"#{ordinal}")
        self.db.execute(
            "INSERT INTO documents (collection, doc_key, parent, ordinal, payload) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(collection, doc_key) DO UPDATE SET payload = excluded.payload",
            (self.name, key, parent, ordinal, document.model_dump_json()),
        )

    def get(self, parent: str, doc_id: str):
        rows = self.db.query(
            "SELECT payload FROM documents WHERE collection = ? AND doc_key = ?",
            (self.name, self._key(parent, doc_id)),
        )
        return self.model.model_validate_json(rows[0]["payload"]) if rows else None

    def list(self, parent: str) -> list:
        rows = self.db.query(
            "SELECT payload FROM documents WHERE collection = ? AND parent = ? "
            "ORDER BY ordinal",
            (self.name, parent),
        )
        return [self.model.model_validate_json(row["payload"]) for row in rows]

    def list_all(self) -> list:
        rows = self.db.query(
            "SELECT payload FROM documents WHERE collection = ? ORDER BY ordinal",
            (self.name,),
        )
        return [self.model.model_validate_json(row["payload"]) for row in rows]

    def exists(self, parent: str, doc_id: str) -> bool:
        return bool(
            self.db.query(
                "SELECT 1 FROM documents WHERE collection = ? AND doc_key = ?",
                (self.name, self._key(parent, doc_id)),
            )
        )


class SqliteProjectStore:
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


class SqliteFactStore:
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


class SqliteFindingStore:
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


class SqliteMaterialStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "materials", MaterialCard)

    def put(self, project_id: str, material: MaterialCard) -> MaterialCard:
        self._c.put(project_id, material.material_id, material)
        return material

    def get(self, project_id: str, material_id: str) -> MaterialCard | None:
        return self._c.get(project_id, material_id)

    def list(self, project_id: str) -> list[MaterialCard]:
        return self._c.list(project_id)


class SqliteAssetStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "assets", AssetVersion)

    def add(self, project_id: str, asset: AssetVersion) -> AssetVersion:
        self._c.put(project_id, asset.version_id, asset)
        return asset

    def get(self, project_id: str, version_id: str) -> AssetVersion | None:
        return self._c.get(project_id, version_id)

    def list(self, project_id: str) -> list[AssetVersion]:
        return self._c.list(project_id)


class SqliteTaskStore:
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


class SqliteTimelineStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "timeline", TimelineEvent)

    def add(self, project_id: str, event: TimelineEvent) -> TimelineEvent:
        self._c.append(project_id, event.event_id, event)
        return event

    def list(self, project_id: str) -> list[TimelineEvent]:
        return self._c.list(project_id)


class SqliteAuditStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "audit", AuditEntry)

    def add(self, project_id: str, entry: AuditEntry) -> AuditEntry:
        self._c.append(project_id, None, entry)
        return entry

    def list(self, project_id: str) -> list[AuditEntry]:
        return self._c.list(project_id)


class SqliteFormStore:
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


class SqliteInstitutionReviewStore:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "institution_reviews", InstitutionReview)

    def put(self, project_id: str, review: InstitutionReview) -> InstitutionReview:
        self._c.put(project_id, review.review_id, review)
        return review

    def latest(self, project_id: str) -> InstitutionReview | None:
        reviews = self._c.list(project_id)
        return reviews[-1] if reviews else None


EPOCH = datetime.min.replace(tzinfo=timezone.utc)


class SqliteNotificationStore:
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


class SqliteInstitutionRegistry:
    def __init__(self, db: Database) -> None:
        self._c = Collection(db, "institutions", MockInstitution)

    def load(self, institutions: list[MockInstitution]) -> None:
        self._c.db.execute("DELETE FROM documents WHERE collection = ?", ("institutions",))
        for item in institutions:
            self._c.put("", item.institution_id, item)

    def get(self, institution_id: str) -> MockInstitution | None:
        return self._c.get("", institution_id)

    def list(self) -> list[MockInstitution]:
        return self._c.list_all()


class SqliteBlobStore:
    """Raw bytes on disk. A GCS adapter slots in behind the same two methods."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def put(self, uri: str, data: bytes) -> str:
        self._db.execute(
            "INSERT INTO blobs (uri, data) VALUES (?, ?) "
            "ON CONFLICT(uri) DO UPDATE SET data = excluded.data",
            (uri, sqlite3.Binary(data)),
        )
        return uri

    def get(self, uri: str) -> bytes | None:
        rows = self._db.query("SELECT data FROM blobs WHERE uri = ?", (uri,))
        return bytes(rows[0]["data"]) if rows else None


class SqliteUploadTicketStore:
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
class SqliteStores:
    """The same bundle as `InMemoryStores`, sharing one database."""

    db: Database

    def __post_init__(self) -> None:
        self.projects = SqliteProjectStore(self.db)
        self.facts = SqliteFactStore(self.db)
        self.findings = SqliteFindingStore(self.db)
        self.materials = SqliteMaterialStore(self.db)
        self.assets = SqliteAssetStore(self.db)
        self.blobs = SqliteBlobStore(self.db)
        self.upload_tickets = SqliteUploadTicketStore(self.db)
        self.tasks = SqliteTaskStore(self.db)
        self.timeline = SqliteTimelineStore(self.db)
        self.audit = SqliteAuditStore(self.db)
        self.forms = SqliteFormStore(self.db)
        self.institution_reviews = SqliteInstitutionReviewStore(self.db)
        self.notifications = SqliteNotificationStore(self.db)
        self.institutions = SqliteInstitutionRegistry(self.db)

    @classmethod
    def at(cls, path: str | Path) -> "SqliteStores":
        return cls(Database(path))
