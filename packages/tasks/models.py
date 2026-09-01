"""
Task Engine domain models for deRek AI OS.

Defines the `Task` entity, its lifecycle states, its execution modes,
and its transition history record — matching the Task Lifecycle and
Execution Modes sections of `docs/PROJECT_BIBLE.md` exactly. This
module has no dependency on the API layer or on any AI provider,
plugin, or agent; it is the Task Engine's own domain layer.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

# Capabilities are declared by the task, not resolved to a provider here —
# resolving a capability to a provider is the Capability Router's job
# (docs/PROJECT_BIBLE.md #7), which is not implemented in this sprint.
_CAPABILITY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_capability(value: str) -> str:
    """Validate that `value` is a lowercase snake_case capability
    identifier, per Naming Conventions in `docs/PROJECT_BIBLE.md`.

    Shared between the domain `Task` model and the API's
    `TaskCreateRequest` (`apps/api/routers/tasks.py`), so an invalid
    capability is rejected at the API boundary with a standard 422
    response rather than surfacing as an unhandled error once it
    reaches `TaskManager`.
    """
    if not _CAPABILITY_PATTERN.match(value):
        raise ValueError(
            "capability must be a lowercase snake_case identifier "
            "(for example, 'coding', 'image_generation')"
        )
    return value


def validate_task_name(value: str) -> str:
    """Validate that `value` is not blank or whitespace-only.

    Shared between the domain `Task` model and the API's
    `TaskCreateRequest` for the same reason as `validate_capability`.
    """
    if not value.strip():
        raise ValueError("name must not be blank")
    return value


class TaskState(str, Enum):
    """The seven lifecycle states a task moves through.

    Values match `docs/PROJECT_BIBLE.md` (Task Lifecycle) exactly,
    including PascalCase, per the project's Naming Conventions.
    """

    QUEUED = "Queued"
    PLANNING = "Planning"
    RUNNING = "Running"
    WAITING = "Waiting"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


#: States with no valid outgoing transition — a task in one of these
#: states has finished its lifecycle (see docs/PROJECT_BIBLE.md #12).
TERMINAL_STATES: frozenset[TaskState] = frozenset(
    {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}
)


class ExecutionMode(str, Enum):
    """What caused a task to be created and how closely a human is
    involved while it runs. Independent of `TaskState` — see
    docs/PROJECT_BIBLE.md (Execution Modes).

    Only `INTERACTIVE` reflects real behavior in this sprint (every
    task is created by a direct API request and processed inline).
    The other modes are recorded as declared intent for forward
    compatibility with the Event Bus, Scheduler, and deRek Mind
    phases, which are not implemented yet.
    """

    INTERACTIVE = "Interactive"
    BACKGROUND = "Background"
    SCHEDULED = "Scheduled"
    EVENT_DRIVEN = "Event Driven"
    AUTONOMOUS = "Autonomous"


class TaskTransition(BaseModel):
    """One entry in a task's transition history.

    History is append-only — `docs/PROJECT_BIBLE.md` is explicit that
    "the system does not overwrite prior state, it appends to it."
    """

    from_state: Optional[TaskState] = None
    to_state: TaskState
    reason: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Task(BaseModel):
    """A single unit of work executed by the Task Engine.

    `capability` declares *what* needs to happen (see Capability
    Router, docs/PROJECT_BIBLE.md #7) — it is recorded here but not
    resolved to a provider in this sprint, since the Capability
    Router and Provider implementations are out of scope for Sprint 2.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    capability: str
    execution_mode: ExecutionMode = ExecutionMode.INTERACTIVE
    input: dict[str, Any] = Field(default_factory=dict)
    state: TaskState = TaskState.QUEUED
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    history: list[TaskTransition] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        return validate_task_name(value)

    @field_validator("capability")
    @classmethod
    def _capability_is_snake_case(cls, value: str) -> str:
        return validate_capability(value)

    @property
    def is_terminal(self) -> bool:
        """Whether this task has finished its lifecycle (no valid
        outgoing transition remains).
        """
        return self.state in TERMINAL_STATES
