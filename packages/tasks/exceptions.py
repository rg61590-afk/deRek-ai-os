"""
Task Engine exceptions for deRek AI OS.

Domain-level errors raised by `packages.tasks`. The API layer
(`apps/api/routers/tasks.py`) catches these and translates them into
`fastapi.HTTPException`, so they flow through the existing global
exception handling and `StandardResponse` envelope rather than needing
handlers of their own.
"""


class TaskError(Exception):
    """Base exception for all Task Engine errors."""


class TaskNotFoundError(TaskError):
    """Raised when a task ID does not exist in the manager's store."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task '{task_id}' was not found")


class InvalidStateTransitionError(TaskError):
    """Raised when a transition is attempted that the state machine
    does not allow from the task's current state.
    """

    def __init__(self, task_id: str, from_state: str, to_state: str) -> None:
        self.task_id = task_id
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Task '{task_id}' cannot transition from '{from_state}' to '{to_state}'"
        )
