"""The product job worker: runs what `QueuedRunner` queued.

With `InlineRunner` the API does the work itself and this module is unused. With
`QueuedRunner` the API records a `queued` task, publishes it, and answers
immediately; this worker picks the task up and finishes it.

The creator's view does not change between the two. The task is written the same
way either way, which is what makes where it runs a deployment decision rather
than a product one.

Two rules the handler exists to keep:

1. **Redelivery is normal.** Pub/Sub delivers at least once, so a task already
   in a terminal state is acknowledged and dropped rather than run again. A
   redelivered review must not write a second set of findings.
2. **A job that fails says why.** The task records the reason and stays visible
   in the project's task list; it is never quietly retried into silence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.workflow_service import WorkflowService
from schemas.enums import TaskStatus, TaskType
from schemas.workflow import WorkflowTask

logger = logging.getLogger(__name__)

TERMINAL = frozenset(
    {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.NEEDS_HUMAN}
)

# Job types this worker knows how to finish. A task of any other type is
# reported rather than dropped: the queue and the worker have drifted apart.
HANDLED = frozenset(
    {TaskType.FACT_EXTRACT, TaskType.REVIEW_FULL, TaskType.REVIEW_INCREMENTAL}
)


@dataclass
class HandledJob:
    task: WorkflowTask
    ran: bool
    reason: str | None = None


class JobWorker:
    """Executes one queued task. Safe to call twice with the same task."""

    def __init__(self, workflow: WorkflowService, stores) -> None:
        self._workflow = workflow
        self._stores = stores

    def handle(self, task: WorkflowTask) -> HandledJob:
        current = self._stores.tasks.get(task.task_id) or task

        if current.status in TERMINAL:
            # Already finished. Acknowledge the redelivery and do nothing.
            return HandledJob(current, ran=False, reason="already_finished")

        if current.type not in HANDLED:
            # An unknown job type is reported, not silently dropped: the queue
            # and this worker have drifted apart and someone needs to know.
            failed = current.model_copy(
                update={
                    "status": TaskStatus.FAILED,
                    "error": f"no handler for {current.type.value}",
                }
            )
            self._stores.tasks.save(failed)
            return HandledJob(failed, ran=False, reason="no_handler")

        try:
            self._workflow.execute_task(current)
        except Exception as failure:
            logger.exception("job %s failed", current.task_id)
            failed = current.model_copy(
                update={"status": TaskStatus.FAILED, "error": str(failure)}
            )
            self._stores.tasks.save(failed)
            return HandledJob(failed, ran=True, reason="failed")

        return HandledJob(
            self._stores.tasks.get(current.task_id) or current, ran=True
        )
