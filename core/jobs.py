"""Job records and how they get run (TDD section 4, async work).

Every long-running piece of work — fact extraction, script review, teaser
generation — is a `WorkflowTask` before it is a result. That is true whether the
work runs inside the request or on a worker, which is the point: the record is
the contract, and where it executes is a deployment decision.

Two runners implement that decision:

- `InlineRunner` executes immediately. Local development and the whole test
  suite use it, so a demo needs no queue, and the caller still gets its answer
  in the response.
- `QueuedRunner` hands the job to a publisher and leaves the task `queued`. The
  API answers immediately and a worker finishes the job later.

Both write the same task, so the creator's view of "what is happening to my
project" does not change with the deployment.

**Idempotency is enforced here, once, for every job type.** The key is
`{project_id}:{task_type}:{asset_version}` — ground rule 6. Pub/Sub redelivers,
and a redelivered review must not write a second set of findings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from schemas.enums import TaskStatus, TaskType
from schemas.workflow import WorkflowTask


def idempotency_key(project_id: str, task_type: TaskType, asset_version: str) -> str:
    """Ground rule 6: one key per project, job type, and version of the input."""

    return f"{project_id}:{task_type.value}:{asset_version}"


@dataclass
class JobOutcome:
    """What a job produced, in a shape a task can record."""

    result: dict[str, Any] | None = None
    error: str | None = None
    status: TaskStatus = TaskStatus.SUCCEEDED


class JobPublisher(Protocol):
    """Hands a queued task to whatever will run it."""

    def publish(self, task: WorkflowTask) -> None: ...


class JobRunner(Protocol):
    def run(
        self, task: WorkflowTask, work: Callable[[], JobOutcome]
    ) -> tuple[WorkflowTask, JobOutcome | None]: ...


class InlineRunner:
    """Run the work now. The task is still recorded, exactly as if queued."""

    name = "inline"

    def run(
        self, task: WorkflowTask, work: Callable[[], JobOutcome]
    ) -> tuple[WorkflowTask, JobOutcome | None]:
        running = task.model_copy(update={"status": TaskStatus.RUNNING})
        try:
            outcome = work()
        except Exception as failure:
            # A job that raised did not produce a result. Recording it as failed
            # with the reason beats a success with nothing behind it.
            return (
                running.model_copy(
                    update={"status": TaskStatus.FAILED, "error": str(failure)}
                ),
                None,
            )
        return (
            running.model_copy(
                update={"status": outcome.status, "result": outcome.result, "error": outcome.error}
            ),
            outcome,
        )


class QueuedRunner:
    """Publish and return. A worker runs the job and updates the task."""

    name = "queued"

    def __init__(self, publisher: JobPublisher) -> None:
        self._publisher = publisher

    def run(
        self, task: WorkflowTask, work: Callable[[], JobOutcome]
    ) -> tuple[WorkflowTask, JobOutcome | None]:
        self._publisher.publish(task)
        return task.model_copy(update={"status": TaskStatus.QUEUED}), None


class RecordingPublisher:
    """Test double: keeps what was published instead of sending it anywhere."""

    def __init__(self) -> None:
        self.published: list[WorkflowTask] = []

    def publish(self, task: WorkflowTask) -> None:
        self.published.append(task)
