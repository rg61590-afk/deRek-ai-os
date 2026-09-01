"""
Task Worker for deRek AI OS.

Drives a task through its lifecycle: `Queued -> Planning -> Running ->
Completed`/`Failed`. Execution itself is delegated to a pluggable
`TaskExecutor` callable so the Worker's own logic (state transitions,
error handling, logging) stays independent of *what* actually performs
the work — the Capability Router and concrete AI providers are not
implemented in this sprint, so `default_executor` below performs no
real work; it exists so a task's full lifecycle is genuinely
exercisable end to end.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from .manager import TaskManager
from .models import Task, TaskState
from .queue import TaskQueue

logger = logging.getLogger(__name__)

#: A callable that performs the actual work for a task and returns a
#: JSON-serializable result. Swappable — a future Capability Router /
#: Provider Layer implementation plugs in here without requiring any
#: change to `TaskWorker` itself.
TaskExecutor = Callable[[Task], Awaitable[dict[str, Any]]]


async def default_executor(task: Task) -> dict[str, Any]:
    """The Task Engine's default executor.

    Performs no external work — no AI provider, plugin, or agent is
    implemented in this sprint (Sprint 2 scope: Task Engine only). It
    exists so tasks can be driven through their full lifecycle for
    testing, the dashboard, and API demonstration purposes, and is
    expected to be replaced by capability-based routing once the
    Provider Layer is implemented (docs/PROJECT_BIBLE.md, Long-Term
    Roadmap, Provider Implementations phase).
    """
    return {
        "message": f"Task '{task.name}' completed by the default in-process executor.",
        "capability": task.capability,
        "note": "No capability-specific provider is implemented yet.",
    }


class TaskWorker:
    """Processes tasks from a `TaskQueue`, driving each through the
    state machine via `TaskManager`.
    """

    def __init__(
        self,
        manager: TaskManager,
        queue: TaskQueue,
        executor: TaskExecutor = default_executor,
    ) -> None:
        self._manager = manager
        self._queue = queue
        self._executor = executor

    async def process_one(self) -> Optional[Task]:
        """Process exactly one task from the queue, if one is
        immediately available, and return it once it reaches a
        terminal state. Returns `None` if the queue is currently empty.

        Non-blocking by design: this is the entry point called
        synchronously from `POST /api/v1/tasks` in this sprint, and
        must never wait indefinitely for work that may never arrive.
        """
        task_id = self._queue.dequeue_nowait()
        if task_id is None:
            return None
        return await self._process_task_id(task_id)

    async def run(self) -> None:
        """Continuously process tasks as they arrive, blocking between
        items when the queue is empty.

        Not started automatically in this sprint. Continuous
        background execution, decoupled from the request/response
        cycle, is Event Bus & Workers scope (see
        docs/PROJECT_BIBLE.md, Long-Term Roadmap) — this method is
        implemented now so that phase can start it without changes
        here, but Sprint 2 drives tasks via `process_one()` instead.
        """
        while True:
            task_id = await self._queue.dequeue()
            await self._process_task_id(task_id)

    async def _process_task_id(self, task_id: str) -> Task:
        task = await self._manager.transition_task(
            task_id, TaskState.PLANNING, reason="worker picked up task"
        )
        task = await self._manager.transition_task(
            task.id, TaskState.RUNNING, reason="execution started"
        )

        try:
            result = await self._executor(task)
        except Exception as exc:  # noqa: BLE001 - executor failures must never propagate
            logger.error(
                "task.execution_failed",
                extra={"task_id": task.id, "capability": task.capability},
                exc_info=exc,
            )
            return await self._manager.fail_task(task.id, error=str(exc))

        completed = await self._manager.complete_task(task.id, result=result)
        logger.info(
            "task.execution_succeeded",
            extra={"task_id": completed.id, "capability": completed.capability},
        )
        return completed
