"""The same assertions against every storage backend.

`core/repositories.py` declares fourteen ports, and until now exactly one thing
implemented them. A port with a single implementation is not a port -- it is an
interface nobody has tested the shape of, and the first second implementation
discovers which of its guarantees were incidental.

So these tests are parametrised over backends rather than written against one.
Every assertion here is a promise `core/workflow_service.py` already relies on:
list order, last-write-wins on facts, first-writer-wins on idempotency keys,
a spent ticket that cannot be spent twice. A Firestore adapter added later
passes this file or it is not finished.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

import pytest

from schemas.assets import AssetVersion, MaterialCard, UploadTicket
from schemas.common import AuditEntry, Fact, SourceRef, TimelineEvent
from schemas.enums import (
    Actor,
    AssetKind,
    FactStatus,
    MaterialStatus,
    ProjectState,
    SourceRefType,
    TaskStatus,
    TaskType,
)
from schemas.forms import FormDraft
from schemas.project import Project
from schemas.reviews import (
    ConfirmedReviewDetails,
    IntakeStatus,
    ReviewMode,
    ReviewSession,
    ReviewState,
)
from schemas.workflow import MockInstitution, Notification, WorkflowTask
from store.memory import InMemoryStores
from store.sqlite import SqliteStores

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(params=["memory", "sqlite"])
def stores(request, tmp_path):
    """One bundle per backend. SQLite gets a real file, not `:memory:`.

    A file is the point: `:memory:` would test the code and not the storage,
    and the durability tests below have to be able to reopen the database.
    """

    if request.param == "memory":
        return InMemoryStores()
    return SqliteStores.at(tmp_path / "conformance.db")


def _project(project_id: str = "proj_1") -> Project:
    return Project(
        project_id=project_id,
        owner_uid="u_demo",
        title_working="夏日便利店",
        state=ProjectState.DRAFT,
        created_at=NOW,
        updated_at=NOW,
    )


def _fact(key: str, value, fact_id: str) -> Fact:
    return Fact(
        fact_id=fact_id,
        key=key,
        value=value,
        source_ref=SourceRef(type=SourceRefType.USER_ANSWER, answer_id="ans"),
        status=FactStatus.CONFIRMED,
    )


def _review_session() -> ReviewSession:
    return ReviewSession(
        review_id="review_1",
        owner_uid="u_demo",
        mode=ReviewMode.SCRIPT,
        state=ReviewState.COMPLETE,
        project_id="proj_1",
        asset_version="asset_1",
        source_filename="script.md",
        source_sha256="a" * 64,
        normalized_text_uri="blob://proj_1/script-text",
        confirmed=ConfirmedReviewDetails(
            title="先挂电话",
            tags=["public security"],
            synopsis="A caller races to stop a public-safety emergency.",
            episode_count=10,
            episode_minutes=3,
            amount_bracket="at_or_above_upper",
        ),
        intake_status=IntakeStatus.COMPLETE,
        created_at=NOW,
        updated_at=NOW,
    )


# --------------------------------------------------------------- projects


def test_a_project_round_trips(stores) -> None:
    stores.projects.create(_project())
    loaded = stores.projects.get("proj_1")
    assert loaded is not None
    assert loaded.title_working == "夏日便利店"
    assert loaded.state is ProjectState.DRAFT


def test_creating_the_same_project_twice_is_refused(stores) -> None:
    stores.projects.create(_project())
    with pytest.raises(KeyError):
        stores.projects.create(_project())


def test_save_overwrites_without_duplicating(stores) -> None:
    stores.projects.create(_project())
    stores.projects.save(_project().model_copy(update={"title_working": "改名"}))
    assert len(stores.projects.list_all()) == 1
    assert stores.projects.get("proj_1").title_working == "改名"


def test_a_missing_project_is_none_not_an_error(stores) -> None:
    assert stores.projects.get("proj_nope") is None


# --------------------------------------------------------- review sessions


def test_a_review_session_round_trips(stores) -> None:
    session = _review_session()
    assert stores.review_sessions.put(session) == session
    assert stores.review_sessions.get(session.review_id) == session


def test_a_missing_review_session_is_none(stores) -> None:
    assert stores.review_sessions.get("review_nope") is None


def test_updating_a_review_session_replaces_the_document(stores) -> None:
    session = _review_session()
    stores.review_sessions.put(session)
    updated = session.model_copy(update={"intake_pending_flags": ["pending"]})
    stores.review_sessions.put(updated)
    assert stores.review_sessions.get(session.review_id) == updated


def test_review_session_state_claim_is_atomic(stores) -> None:
    session = _review_session().model_copy(
        update={"state": ReviewState.AWAITING_CONFIRMATION}
    )
    stores.review_sessions.put(session)
    claimed = session.model_copy(update={"state": ReviewState.ANALYZING})

    assert stores.review_sessions.compare_and_put(
        session.review_id, ReviewState.AWAITING_CONFIRMATION, claimed
    )
    assert not stores.review_sessions.compare_and_put(
        session.review_id, ReviewState.AWAITING_CONFIRMATION, claimed
    )


def test_sqlite_review_session_survives_adapter_reconstruction(tmp_path) -> None:
    path = tmp_path / "review-session.db"
    first = SqliteStores.at(path)
    first.review_sessions.put(_review_session())
    first.db.close()

    reopened = SqliteStores.at(path)
    try:
        assert reopened.review_sessions.get("review_1") == _review_session()
    finally:
        reopened.db.close()


def test_sqlite_state_claim_is_atomic_across_two_connections(tmp_path) -> None:
    path = tmp_path / "review-session-race.db"
    first = SqliteStores.at(path)
    second = SqliteStores.at(path)
    session = _review_session().model_copy(
        update={"state": ReviewState.AWAITING_CONFIRMATION}
    )
    first.review_sessions.put(session)
    analyzing = session.model_copy(update={"state": ReviewState.ANALYZING})
    extracting = session.model_copy(update={"state": ReviewState.EXTRACTING})
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda item: item[0].review_sessions.compare_and_put(
                        session.review_id,
                        ReviewState.AWAITING_CONFIRMATION,
                        item[1],
                    ),
                    [(first, analyzing), (second, extracting)],
                )
            )
        assert sorted(results) == [False, True]
    finally:
        first.db.close()
        second.db.close()


# ------------------------------------------------------------------ facts


def test_facts_come_back_in_the_order_they_were_added(stores) -> None:
    for index, key in enumerate(["title", "episode_count", "applicant_entity"]):
        stores.facts.add("proj_1", _fact(key, index, f"fact_{index}"))
    assert [fact.key for fact in stores.facts.list("proj_1")] == [
        "title",
        "episode_count",
        "applicant_entity",
    ]


def test_get_by_key_returns_the_last_write(stores) -> None:
    """`_upsert_fact` appends rather than replacing, so this is load-bearing."""

    stores.facts.add("proj_1", _fact("title", "第一版", "fact_a"))
    stores.facts.add("proj_1", _fact("title", "第二版", "fact_b"))
    assert stores.facts.get_by_key("proj_1", "title").value == "第二版"


def test_facts_do_not_leak_between_projects(stores) -> None:
    stores.facts.add("proj_1", _fact("title", "A", "fact_a"))
    stores.facts.add("proj_2", _fact("title", "B", "fact_b"))
    assert [f.value for f in stores.facts.list("proj_1")] == ["A"]
    assert stores.facts.get_by_key("proj_2", "title").value == "B"


def test_an_empty_project_has_no_facts(stores) -> None:
    assert stores.facts.list("proj_unknown") == []


# ------------------------------------------------------------------ tasks


def test_the_first_writer_of_an_idempotency_key_wins(stores) -> None:
    """A retry must return the original task, never make a second one."""

    first = WorkflowTask(
        task_id="task_1", project_id="proj_1", type=TaskType.REVIEW_FULL,
        idempotency_key="proj_1:review:v1",
    )
    second = WorkflowTask(
        task_id="task_2", project_id="proj_1", type=TaskType.REVIEW_FULL,
        idempotency_key="proj_1:review:v1",
    )
    stores.tasks.add(first)
    stores.tasks.add(second)
    assert stores.tasks.find_by_idempotency_key("proj_1:review:v1").task_id == "task_1"


def test_saving_a_task_does_not_create_a_second_one(stores) -> None:
    task = WorkflowTask(
        task_id="task_1", project_id="proj_1", type=TaskType.REVIEW_FULL,
        idempotency_key="k",
    )
    stores.tasks.add(task)
    stores.tasks.save(task.model_copy(update={"status": TaskStatus.SUCCEEDED}))
    assert len(stores.tasks.list("proj_1")) == 1
    assert stores.tasks.get("task_1").status is TaskStatus.SUCCEEDED


# ------------------------------------------------------- timeline and audit


def test_the_timeline_keeps_its_order(stores) -> None:
    for index in range(4):
        stores.timeline.add(
            "proj_1",
            TimelineEvent(
                event_id=f"evt_{index}", at=NOW + timedelta(minutes=index),
                actor=Actor.SYSTEM, event=f"step.{index}",
            ),
        )
    assert [e.event for e in stores.timeline.list("proj_1")] == [
        "step.0", "step.1", "step.2", "step.3",
    ]


def test_audit_entries_append_even_without_an_id(stores) -> None:
    """`AuditEntry` has no id field; two identical lines must both survive."""

    entry = AuditEntry(
        at=NOW, actor=Actor.CREATOR,
        from_state=ProjectState.DRAFT, to_state=ProjectState.CLASSIFIED,
        reason="classified",
    )
    stores.audit.add("proj_1", entry)
    stores.audit.add("proj_1", entry)
    assert len(stores.audit.list("proj_1")) == 2


# ------------------------------------------------------------------ forms


def test_the_latest_draft_is_the_last_one_added(stores) -> None:
    for index in range(3):
        stores.forms.put(
            "proj_1", FormDraft(draft_id=f"draft_{index}", snapshot_version="v2")
        )
    assert stores.forms.latest("proj_1").draft_id == "draft_2"


def test_updating_a_draft_does_not_make_it_the_latest(stores) -> None:
    """Freezing draft_0 after draft_1 exists must not reorder them."""

    stores.forms.put("proj_1", FormDraft(draft_id="draft_0", snapshot_version="v2"))
    stores.forms.put("proj_1", FormDraft(draft_id="draft_1", snapshot_version="v2"))
    stores.forms.put(
        "proj_1",
        FormDraft(draft_id="draft_0", snapshot_version="v2", frozen=True, hash="abc"),
    )
    assert stores.forms.latest("proj_1").draft_id == "draft_1"
    assert stores.forms.get("proj_1", "draft_0").frozen is True


# ---------------------------------------------------------------- tickets


def test_a_ticket_can_only_be_spent_once(stores) -> None:
    stores.upload_tickets.add(
        UploadTicket(
            ticket_id="tkt_1", project_id="proj_1", kind=AssetKind.SCRIPT,
            storage_uri="blob://x", issued_to="u_demo", created_at=NOW,
        )
    )
    assert stores.upload_tickets.consume("tkt_1") is not None
    assert stores.upload_tickets.consume("tkt_1") is None


def test_consuming_an_unknown_ticket_is_none(stores) -> None:
    assert stores.upload_tickets.consume("tkt_nope") is None


# ------------------------------------------------------------------ blobs


def test_blobs_round_trip_bytes_exactly(stores) -> None:
    payload = "第一场 便利店 夜 内\n".encode("utf-8") + bytes([0, 255, 128])
    stores.blobs.put("blob://proj_1/script", payload)
    assert stores.blobs.get("blob://proj_1/script") == payload


def test_a_missing_blob_is_none(stores) -> None:
    assert stores.blobs.get("blob://nope") is None


# ---------------------------------------------------------- notifications


def test_an_inbox_is_newest_first(stores) -> None:
    for index in range(3):
        stores.notifications.add(
            Notification(
                notification_id=f"ntf_{index}", user_id="u_demo", project_id="proj_1",
                kind="policy_stale", title_key="t", body_key="b",
                created_at=NOW + timedelta(hours=index),
            )
        )
    assert [n.notification_id for n in stores.notifications.list("u_demo")] == [
        "ntf_2", "ntf_1", "ntf_0",
    ]


def test_another_user_sees_an_empty_inbox(stores) -> None:
    stores.notifications.add(
        Notification(
            notification_id="ntf_1", user_id="u_demo", project_id="proj_1",
            kind="policy_stale", title_key="t", body_key="b", created_at=NOW,
        )
    )
    assert stores.notifications.list("u_other") == []


def test_marking_read_hides_it_from_unread_only(stores) -> None:
    stores.notifications.add(
        Notification(
            notification_id="ntf_1", user_id="u_demo", project_id="proj_1",
            kind="policy_stale", title_key="t", body_key="b", created_at=NOW,
        )
    )
    stores.notifications.mark_read("ntf_1")
    assert stores.notifications.list("u_demo", unread_only=True) == []
    assert len(stores.notifications.list("u_demo")) == 1


def test_marking_an_unknown_notification_read_is_none(stores) -> None:
    assert stores.notifications.mark_read("ntf_nope") is None


# ------------------------------------------------- materials and findings


def test_materials_are_keyed_not_appended(stores) -> None:
    card = MaterialCard(
        material_id="mat_script", name_key="material.script", asset_kind=AssetKind.SCRIPT
    )
    stores.materials.put("proj_1", card)
    stores.materials.put(
        "proj_1", card.model_copy(update={"status": MaterialStatus.VALID})
    )
    cards = stores.materials.list("proj_1")
    assert len(cards) == 1
    assert cards[0].status is MaterialStatus.VALID


def test_assets_round_trip(stores) -> None:
    stores.assets.add(
        "proj_1",
        AssetVersion(
            version_id="av_1", kind=AssetKind.SCRIPT,
            storage_uri="blob://x", sha256="d" * 64,
            uploaded_by="u_demo", created_at=NOW,
        ),
    )
    assert stores.assets.get("proj_1", "av_1").sha256 == "d" * 64
    assert len(stores.assets.list("proj_1")) == 1


# ------------------------------------------------------------ institutions


def test_loading_institutions_replaces_the_previous_set(stores) -> None:
    first = MockInstitution(
        institution_id="inst_1", name="甲影视", license_no="待补充",
        valid_until="2027-01-01", registered_capital_rmb=0,
    )
    second = MockInstitution(
        institution_id="inst_2", name="乙影视", license_no="待补充",
        valid_until="2027-01-01", registered_capital_rmb=0,
    )
    stores.institutions.load([first])
    stores.institutions.load([second])
    assert [i.institution_id for i in stores.institutions.list()] == ["inst_2"]


# -------------------------------------------------------------- durability


def test_sqlite_survives_a_restart(tmp_path) -> None:
    """The whole point. The memory backend cannot do this and is not asked to."""

    path = tmp_path / "durable.db"
    first = SqliteStores.at(path)
    first.projects.create(_project())
    first.facts.add("proj_1", _fact("title", "夏日便利店", "fact_1"))
    first.blobs.put("blob://proj_1/script", b"scene one")
    first.db.close()

    reopened = SqliteStores.at(path)
    assert reopened.projects.get("proj_1").title_working == "夏日便利店"
    assert reopened.facts.get_by_key("proj_1", "title").value == "夏日便利店"
    assert reopened.blobs.get("blob://proj_1/script") == b"scene one"


def test_ordering_survives_a_restart(tmp_path) -> None:
    """Order is the guarantee most likely to be an accident of storage."""

    path = tmp_path / "ordered.db"
    first = SqliteStores.at(path)
    for index in range(5):
        first.timeline.add(
            "proj_1",
            TimelineEvent(
                event_id=f"evt_{index}", at=NOW + timedelta(minutes=index),
                actor=Actor.SYSTEM, event=f"step.{index}",
            ),
        )
    first.db.close()

    reopened = SqliteStores.at(path)
    assert [e.event for e in reopened.timeline.list("proj_1")] == [
        "step.0", "step.1", "step.2", "step.3", "step.4",
    ]
