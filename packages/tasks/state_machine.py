"""
Task state machine for deRek AI OS.

Encodes the exact transition graph from the Task Lifecycle section of
`docs/PROJECT_BIBLE.md` (and its Mermaid `stateDiagram-v2`) as data,
and applies transitions to a `Task`, appending to its history rather
than overwriting prior state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .exceptions import InvalidStateTransitionError
from .models import Task, TaskState, TaskTransition

#: The complete, authoritative transition graph. Mirrors
#: docs/PROJECT_BIBLE.md #12 (Task Lifecycle) exactly:
#:
#:   Queued    -> Planning, Cancelled
#:   Planning  -> Running, Failed, Cancelled
#:   Running   -> Waiting, Completed, Failed, Cancelled
#:   Waiting   -> Running, Cancelled
#:   Completed -> (terminal)
#:   Failed    -> (terminal)
#:   Cancelled -> (terminal)
ALLOWED_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.QUEUED: frozenset({TaskState.PLANNING, TaskState.CANCELLED}),
    TaskState.PLANNING: frozenset(
        {TaskState.RUNNING, TaskState.FAILED, TaskState.CANCELLED}
    ),
    TaskState.RUNNING: frozenset(
        {TaskState.WAITING, TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}
    ),
    TaskState.WAITING: frozenset({TaskState.RUNNING, TaskState.CANCELLED}),
    TaskState.COMPLETED: frozenset(),
    TaskState.FAILED: frozenset(),
    TaskState.CANCELLED: frozenset(),
}


def can_transition(from_state: TaskState, to_state: TaskState) -> bool:
    """Return whether `from_state -> to_state` is a legal transition."""
    return to_state in ALLOWED_TRANSITIONS[from_state]


def apply_transition(
    task: Task, to_state: TaskState, *, reason: Optional[str] = None
) -> Task:
    """Move `task` to `to_state`, validating the transition and
    appending a `TaskTransition` record to its history.

    Mutates and returns the same `Task` instance so callers holding a
    reference (for example, `TaskManager`'s in-memory store) see the
    update immediately.
    """
    from_state = task.state

    if not can_transition(from_state, to_state):
        raise InvalidStateTransitionError(
            task_id=task.id, from_state=from_state.value, to_state=to_state.value
        )

    now = datetime.now(timezone.utc)
    task.history.append(
        TaskTransition(from_state=from_state, to_state=to_state, reason=reason, timestamp=now)
    )
    task.state = to_state
    task.updated_at = now
    return task
