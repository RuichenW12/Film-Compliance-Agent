"""Job records, the two runners, and the worker that finishes queued work.

The claim under test is that where a job runs is a deployment decision and not a
product one: the same task is written either way, and the creator's view of
their project does not change.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
import threading

import pytest
from fastapi.testclient import TestClient

from api.deps.services import AppContext
from api.main import create_app
from api.settings import Settings
from core.jobs import InlineRunner, QueuedRunner, RecordingPublisher, idempotency_key
from core.llm import UnavailableLLM
from core.workflow_service import WorkflowService
from schemas.enums import TaskType
from store.memory import InMemoryStores
from store.sqlite import SqliteStores
from workers.jobs import JobWorker

OWNER = {"X-Mock-Role": "creator", "X-User-Id": "u_owner"}
SCRIPT = (
    "第一集 场景一：码头。卧底警察与线人接头。\n"
    "第一集 场景二：派出所。民警连夜审讯嫌疑人。\n"
)
REVISED = "第一集 场景一：码头。两个老友深夜叙旧。\n"


def make_client(stores, snapshots, clock, runner, llm=None) -> TestClient:
    context = AppContext(
        settings=Settings(),
        stores=stores,
        snapshots=snapshots,
        clock=clock,
        llm=llm or UnavailableLLM(),
        jobs=runner,
    )
    return TestClient(create_app(context=context))


@pytest.fixture
def inline_client(stores, snapshots, clock) -> TestClient:
    return make_client(stores, snapshots, clock, InlineRunner())


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
def queued_client(stores, snapshots, clock, publisher) -> TestClient:
    return make_client(stores, snapshots, clock, QueuedRunner(publisher))


def project_with_script(client: TestClient, script: str = SCRIPT) -> tuple[str, str]:
    created = client.post(
        "/v1/projects", json={"title_working": "Operation Fog"}, headers=OWNER
    )
    project_id = created.json()["project_id"]
    ticket = client.post(
        f"/v1/projects/{project_id}/assets/upload-url",
        json={"kind": "script"},
        headers=OWNER,
    ).json()
    version = client.put(
        ticket["upload_url"], content=script.encode("utf-8"), headers=OWNER
    ).json()
    return project_id, version["version_id"]


def tasks_of(client: TestClient, project_id: str) -> list[dict]:
    return client.get(f"/v1/projects/{project_id}/tasks", headers=OWNER).json()


# ------------------------------------------------------------- the key itself


def test_the_key_names_the_project_the_job_and_the_version():
    key = idempotency_key("proj_1", TaskType.REVIEW_FULL, "av_9")
    assert key == "proj_1:review_full:av_9"


# --------------------------------------------------------------- inline runs


def test_running_inline_still_answers_in_the_response(inline_client):
    project_id, _ = project_with_script(inline_client)
    body = inline_client.post(f"/v1/projects/{project_id}/review", headers=OWNER).json()

    assert len(body["findings"]) == 2
    assert body["pending_flags"] == ["script_semantic_check_pending"]


def test_an_inline_job_is_still_recorded_as_a_task(inline_client):
    """The record is the contract, whatever ran it."""

    project_id, version_id = project_with_script(inline_client)
    inline_client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    tasks = tasks_of(inline_client, project_id)
    review = [task for task in tasks if task["type"] == "review_full"][0]
    assert review["idempotency_key"] == f"{project_id}:review_full:{version_id}"
    assert review["status"] == "needs_human"
    assert review["error"] == "script_semantic_check_pending"


def test_a_first_review_is_full_and_a_second_version_is_incremental(inline_client):
    project_id, _ = project_with_script(inline_client)
    inline_client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    ticket = inline_client.post(
        f"/v1/projects/{project_id}/assets/upload-url",
        json={"kind": "script"},
        headers=OWNER,
    ).json()
    inline_client.put(
        ticket["upload_url"], content=REVISED.encode("utf-8"), headers=OWNER
    )
    inline_client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    types = [task["type"] for task in tasks_of(inline_client, project_id)]
    assert "review_full" in types
    assert "review_incremental" in types


def test_extraction_is_recorded_against_its_asset_version(inline_client):
    project_id, version_id = project_with_script(inline_client)
    inline_client.post(
        f"/v1/projects/{project_id}/assets/{version_id}/extract-facts", headers=OWNER
    )

    extract = [
        task for task in tasks_of(inline_client, project_id)
        if task["type"] == "fact_extract"
    ][0]
    assert extract["payload"]["asset_version"] == version_id
    assert extract["error"] == "fact_extraction_pending"


def test_replaying_a_job_does_not_run_it_twice(inline_client):
    """Two reviews of the same version are one task and one set of findings."""

    project_id, _ = project_with_script(inline_client)
    inline_client.post(f"/v1/projects/{project_id}/review", headers=OWNER)
    inline_client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    reviews = [
        task for task in tasks_of(inline_client, project_id)
        if task["type"].startswith("review")
    ]
    assert len(reviews) == 1

    findings = inline_client.get(
        f"/v1/projects/{project_id}/findings", headers=OWNER
    ).json()
    assert len(findings) == 2


# --------------------------------------------------------------- queued runs


def test_queueing_publishes_and_leaves_the_task_queued(queued_client, publisher):
    project_id, _ = project_with_script(queued_client)
    queued_client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    assert len(publisher.published) == 1
    task = tasks_of(queued_client, project_id)[0]
    assert task["status"] == "queued"


def test_a_queued_review_has_not_written_findings_yet(queued_client):
    """The API answered; the work has not happened. That must be visible."""

    project_id, _ = project_with_script(queued_client)
    response = queued_client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    assert response.status_code == 200
    assert response.json()["backend"] == "queued"
    assert response.json()["pending_flags"] == ["script_semantic_check_pending"]
    assert response.json()["findings"] == []
    assert (
        queued_client.get(f"/v1/projects/{project_id}/findings", headers=OWNER).json()
        == []
    )


def test_the_worker_finishes_what_was_queued(queued_client, publisher, stores):
    project_id, _ = project_with_script(queued_client)
    queued_client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    worker = JobWorker(queued_client.app.state.context.workflow, stores)
    handled = worker.handle(publisher.published[0])

    assert handled.ran is True
    assert handled.task.status.value == "needs_human"
    assert handled.task.result["finding_count"] == 2

    findings = queued_client.get(
        f"/v1/projects/{project_id}/findings", headers=OWNER
    ).json()
    assert len(findings) == 2


def test_the_worker_ignores_a_redelivered_finished_task(queued_client, publisher, stores):
    """Pub/Sub delivers at least once. Twice must not double the findings."""

    project_id, _ = project_with_script(queued_client)
    queued_client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    worker = JobWorker(queued_client.app.state.context.workflow, stores)
    worker.handle(publisher.published[0])
    again = worker.handle(publisher.published[0])

    assert again.ran is False
    assert again.reason == "already_finished"

    findings = queued_client.get(
        f"/v1/projects/{project_id}/findings", headers=OWNER
    ).json()
    assert len(findings) == 2


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_concurrent_worker_redelivery_claims_and_executes_once(
    tmp_path, snapshots, clock, backend
) -> None:
    primary = (
        InMemoryStores()
        if backend == "memory"
        else SqliteStores.at(tmp_path / "worker-claim.sqlite3")
    )
    concurrent = (
        primary
        if backend == "memory"
        else SqliteStores.at(tmp_path / "worker-claim.sqlite3")
    )
    entered = threading.Event()
    release = threading.Event()

    class BlockingLLM:
        name = "blocking"

        def __init__(self) -> None:
            self.calls = 0
            self._lock = threading.Lock()

        def available(self) -> bool:
            return True

        def structured(self, _request):
            with self._lock:
                self.calls += 1
            entered.set()
            assert release.wait(timeout=5)
            return {"hits": []}

    llm = BlockingLLM()
    publisher = RecordingPublisher()
    client = make_client(
        primary, snapshots, clock, QueuedRunner(publisher), llm=llm
    )
    project_id, _ = project_with_script(client)
    response = client.post(f"/v1/projects/{project_id}/review", headers=OWNER)
    assert response.status_code == 200
    task = publisher.published[0]
    first_worker = JobWorker(client.app.state.context.workflow, primary)
    second_workflow = WorkflowService(concurrent, snapshots, clock, llm)
    second_worker = JobWorker(second_workflow, concurrent)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_worker.handle, task)
        assert entered.wait(timeout=5)
        running_replay = client.post(
            f"/v1/projects/{project_id}/review", headers=OWNER
        )
        second = pool.submit(second_worker.handle, task)
        completed, _ = wait([second], timeout=0.5)
        release.set()
        first_result = first.result(timeout=5)
        second_result = second.result(timeout=5)

    assert running_replay.status_code == 200
    assert running_replay.json()["backend"] == "queued"
    assert running_replay.json()["pending_flags"] == [
        "script_semantic_check_pending"
    ]
    assert len(primary.tasks.list(project_id)) == 1
    assert len(publisher.published) == 1
    assert second in completed
    assert first_result.ran is True
    assert second_result.ran is False
    assert second_result.reason == "already_claimed"
    assert llm.calls == 1
    stored = primary.tasks.get(task.task_id)
    assert stored.status.value == "succeeded"
    assert stored.result["finding_count"] == 2
    assert len(primary.findings.list(project_id)) == 2
    assert len(
        [event for event in primary.timeline.list(project_id) if event.event == "job.completed"]
    ) == 1
    terminal_replay = client.post(
        f"/v1/projects/{project_id}/review", headers=OWNER
    )
    assert terminal_replay.status_code == 200
    assert terminal_replay.json()["pending_flags"] == []
    assert len(primary.tasks.list(project_id)) == 1
    assert len(publisher.published) == 1
    assert llm.calls == 1
    if backend == "sqlite":
        concurrent.db.close()
        primary.db.close()


def test_the_worker_finishes_a_queued_extraction(queued_client, publisher, stores):
    project_id, version_id = project_with_script(queued_client)
    queued_client.post(
        f"/v1/projects/{project_id}/assets/{version_id}/extract-facts", headers=OWNER
    )

    worker = JobWorker(queued_client.app.state.context.workflow, stores)
    handled = worker.handle(publisher.published[0])

    assert handled.ran is True
    assert handled.task.error == "fact_extraction_pending"


def test_a_job_type_the_worker_does_not_know_is_reported(queued_client, publisher, stores):
    """Drift between the queue and the worker must be visible, not silent."""

    project_id, _ = project_with_script(queued_client)
    queued_client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    stray = publisher.published[0].model_copy(update={"type": TaskType.US_RESEARCH})
    stores.tasks.save(stray)

    handled = JobWorker(queued_client.app.state.context.workflow, stores).handle(stray)
    assert handled.ran is False
    assert handled.reason == "no_handler"
    assert handled.task.status.value == "failed"
    assert "us_research" in handled.task.error


def test_a_worker_failure_is_recorded_on_the_task(queued_client, publisher, stores):
    project_id, _ = project_with_script(queued_client)
    queued_client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    class Exploding:
        def execute_task(self, task):
            raise RuntimeError("vertex quota exhausted")

    handled = JobWorker(Exploding(), stores).handle(publisher.published[0])

    assert handled.ran is True
    assert handled.task.status.value == "failed"
    assert "quota exhausted" in handled.task.error


def test_the_timeline_shows_the_job_either_way(inline_client, queued_client, publisher, stores):
    """A creator sees the same events whether or not a worker was involved."""

    inline_project, _ = project_with_script(inline_client)
    inline_client.post(f"/v1/projects/{inline_project}/review", headers=OWNER)
    inline_events = [
        event["event"]
        for event in inline_client.get(
            f"/v1/projects/{inline_project}/timeline", headers=OWNER
        ).json()
    ]
    assert "job.recorded" in inline_events

    queued_project, _ = project_with_script(queued_client)
    queued_client.post(f"/v1/projects/{queued_project}/review", headers=OWNER)
    JobWorker(queued_client.app.state.context.workflow, stores).handle(
        publisher.published[0]
    )
    queued_events = [
        event["event"]
        for event in queued_client.get(
            f"/v1/projects/{queued_project}/timeline", headers=OWNER
        ).json()
    ]
    assert "job.recorded" in queued_events
    assert "job.completed" in queued_events
