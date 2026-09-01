"""Task Engine for deRek AI OS.

Implements task creation, the state machine defined in
docs/PROJECT_BIBLE.md (Task Lifecycle), and in-process execution via a
pluggable executor. No AI provider, plugin, agent, memory, or database
is implemented here — see `worker.default_executor` and this
package's README for exactly what is and is not implemented.
"""

from .exceptions import InvalidStateTransitionError, TaskError, TaskNotFoundError
from .manager import TaskManager
from .models import (
    ExecutionMode,
    Task,
    TaskState,
    TaskTransition,
    TERMINAL_STATES,
    validate_capability,
    validate_task_name,
)
from .queue import TaskQueue
from .state_machine import ALLOWED_TRANSITIONS, apply_transition, can_transition
from .worker import TaskExecutor, TaskWorker, default_executor

__all__ = [
    "ALLOWED_TRANSITIONS",
    "ExecutionMode",
    "InvalidStateTransitionError",
    "Task",
    "TaskError",
    "TaskExecutor",
    "TaskManager",
    "TaskNotFoundError",
    "TaskQueue",
    "TaskState",
    "TaskTransition",
    "TaskWorker",
    "TERMINAL_STATES",
    "apply_transition",
    "can_transition",
    "default_executor",
    "validate_capability",
    "validate_task_name",
]
