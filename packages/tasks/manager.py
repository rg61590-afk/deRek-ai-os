"""
Task Manager for deRek AI OS.

Owns the in-memory store of tasks and is the single point through
which tasks are created, looked up, listed, transitioned, and removed.
No database is used in this sprint — the store does not survive a
process restart.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from . import state_machine
from .exceptions import TaskNotFoundError
from .models import ExecutionMode, Task, TaskState, TaskTransition
from .queue import TaskQueue

logger = logging.getLogger(__name__)


class TaskManager:
    """In-memory task store and lifecycle coordinator.

    Thread-unsafe by design (a single `asyncio.Lock` serializes access
    instead) since this process has exactly one event loop and no
    multi-process worker pool in this sprint.
    """

    def __init__(self, queue: TaskQueue) -> None:
        self._queue = queue
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()

    async def create_task(
        self,
        *,
        name: str,
        capability: str,
        execution_mode: ExecutionMode = ExecutionMode.INTERACTIVE,
        input: Optional[dict[str, Any]] = None,
    ) -> Task:
        """Create a new task in the `Queued` state and enqueue it for
        processing.
        """
        task = Task(
            name=name,
            capability=capability,
            execution_mode=execution_mode,
            input=input or {},
        )
        # The initial Queued state is recorded as a transition too, so
        # a task's full history — including its creation — is visible
        # by inspecting `history` alone.
        task.history.append(
            TaskTransition(from_state=None, to_state=TaskState.QUEUED, reason="created")
        )

        async with self._lock:
            self._tasks[task.id] = task

        await self._queue.enqueue(task.id)
        logger.info(
            "task.created",
            extra={"task_id": task.id, "capability": task.capability, "state": task.state.value},
        )
        return task

    async def get_task(self, task_id: str) -> Task:
        """Return the task with `task_id`, or raise `TaskNotFoundError`."""
        async with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    async def list_tasks(self, *, state: Optional[TaskState] = None) -> list[Task]:
        """Return all tasks, optionally filtered by state, most
        recently created first.
        """
        async with self._lock:
            tasks = list(self._tasks.values())
        if state is not None:
            tasks = [t for t in tasks if t.state == state]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    async def transition_task(
        self, task_id: str, to_state: TaskState, *, reason: Optional[str] = None
    ) -> Task:
        """Move a task to `to_state` via the state machine, validating
        the transition and appending to its history.
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise TaskNotFoundError(task_id)
            state_machine.apply_transition(task, to_state, reason=reason)

        logger.info(
            "task.transitioned",
            extra={"task_id": task.id, "state": task.state.value, "reason": reason},
        )
        return task

    async def complete_task(self, task_id: str, *, result: dict[str, Any]) -> Task:
        """Record a successful result and transition the task to
        `Completed`, atomically with respect to other manager
        operations.
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise TaskNotFoundError(task_id)
            task.result = result
            state_machine.apply_transition(task, TaskState.COMPLETED, reason="execution succeeded")

        logger.info("task.completed", extra={"task_id": task.id})
        return task

    async def fail_task(self, task_id: str, *, error: str) -> Task:
        """Record a failure reason and transition the task to
        `Failed`, atomically with respect to other manager operations.
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise TaskNotFoundError(task_id)
            task.error = error
            state_machine.apply_transition(task, TaskState.FAILED, reason=error)

        logger.info("task.failed", extra={"task_id": task.id, "error": error})
        return task

    async def delete_task(self, task_id: str) -> Task:
        """Remove a task from the store.

        If the task has not yet reached a terminal state, it is
        transitioned to `Cancelled` first (a valid transition from
        every non-terminal state — see `state_machine`), so its
        history reflects that it was stopped rather than simply
        vanishing. A task already in a terminal state is removed as-is.
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise TaskNotFoundError(task_id)
            if not task.is_terminal:
                state_machine.apply_transition(
                    task, TaskState.CANCELLED, reason="deleted before completion"
                )
            del self._tasks[task_id]

        logger.info("task.deleted", extra={"task_id": task.id, "final_state": task.state.value})
        return task
