"""Task Engine endpoints.

Exposes the Task Engine (`packages.tasks`) over the API: creating,
listing, retrieving, and deleting tasks. No AI provider, plugin, or
agent is wired in — task execution uses the Task Engine's default
in-process executor (see `packages.tasks.worker.default_executor`).
"""

from functools import lru_cache
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator

from schemas import StandardResponse
from packages.tasks import (
    ExecutionMode,
    Task,
    TaskManager,
    TaskNotFoundError,
    TaskQueue,
    TaskState,
    TaskWorker,
    validate_capability,
    validate_task_name,
)

router = APIRouter(tags=["tasks"])


# --- Shared Task Engine singletons -------------------------------------------
#
# One TaskQueue/TaskManager/TaskWorker per process, matching the
# `get_settings()` cached-singleton pattern already used in config.py.
# In-memory only, per this sprint's scope — state does not survive a
# process restart.

@lru_cache
def get_task_queue() -> TaskQueue:
    return TaskQueue()


@lru_cache
def get_task_manager() -> TaskManager:
    return TaskManager(queue=get_task_queue())


@lru_cache
def get_task_worker() -> TaskWorker:
    return TaskWorker(manager=get_task_manager(), queue=get_task_queue())


# --- Request/response models --------------------------------------------------

class TaskCreateRequest(BaseModel):
    """Request body for `POST /api/v1/tasks`."""

    name: str = Field(..., description="Human-readable task name")
    capability: str = Field(
        ...,
        description=(
            "The capability this task requests (lowercase snake_case, "
            "for example 'coding' or 'research'). Not yet routed to a "
            "provider — see docs/PROJECT_BIBLE.md, Capability Router."
        ),
    )
    execution_mode: Optional[ExecutionMode] = Field(
        default=None, description="Defaults to 'Interactive' if omitted."
    )
    input: Optional[dict[str, Any]] = Field(
        default=None, description="Task parameters/payload. Defaults to an empty object."
    )

    # Validated here too (not just on the domain `Task` model) so
    # invalid input is rejected at the API boundary with a standard
    # 422 response, before it ever reaches `TaskManager`.
    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        return validate_task_name(value)

    @field_validator("capability")
    @classmethod
    def _capability_is_snake_case(cls, value: str) -> str:
        return validate_capability(value)


# --- Routes --------------------------------------------------------------------

@router.post(
    "/tasks",
    response_model=StandardResponse[Task],
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
    description=(
        "Creates a task and processes it synchronously via the Task Engine's "
        "default executor. No AI provider is implemented yet, so `result` "
        "reflects the default in-process executor, not real capability output."
    ),
)
async def create_task(payload: TaskCreateRequest, request: Request) -> StandardResponse[Task]:
    manager = get_task_manager()
    worker = get_task_worker()

    task = await manager.create_task(
        name=payload.name,
        capability=payload.capability,
        execution_mode=payload.execution_mode or ExecutionMode.INTERACTIVE,
        input=payload.input,
    )

    # Sprint 2 has no continuous background worker loop (that is Event Bus &
    # Workers scope — see docs/PROJECT_BIBLE.md, Long-Term Roadmap), so the
    # task just enqueued is processed inline here. `process_one()` dequeues
    # whatever is next in the queue, which — since nothing else in this
    # sprint consumes it — is this task under normal, sequential use.
    processed = await worker.process_one()

    return StandardResponse.ok(
        data=processed or task,
        message="Task created",
        request_id=request.state.request_id,
    )


@router.get(
    "/tasks",
    response_model=StandardResponse[list[Task]],
    summary="List tasks",
    description="Returns all tasks, most recently created first, optionally filtered by state.",
)
async def list_tasks(
    request: Request,
    state: Optional[TaskState] = Query(
        default=None, description="Filter by exact state, e.g. 'Completed'."
    ),
) -> StandardResponse[list[Task]]:
    manager = get_task_manager()
    tasks = await manager.list_tasks(state=state)
    return StandardResponse.ok(
        data=tasks,
        message=f"{len(tasks)} task(s) retrieved",
        request_id=request.state.request_id,
    )


@router.get(
    "/tasks/{task_id}",
    response_model=StandardResponse[Task],
    summary="Retrieve a task",
    description="Returns a single task by ID.",
)
async def get_task(task_id: str, request: Request) -> StandardResponse[Task]:
    manager = get_task_manager()
    try:
        task = await manager.get_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return StandardResponse.ok(
        data=task,
        message="Task retrieved",
        request_id=request.state.request_id,
    )


@router.delete(
    "/tasks/{task_id}",
    response_model=StandardResponse[Task],
    summary="Delete a task",
    description=(
        "Removes a task. If it has not yet reached a terminal state, it is "
        "transitioned to 'Cancelled' first so the cancellation is recorded "
        "in its history before it is removed."
    ),
)
async def delete_task(task_id: str, request: Request) -> StandardResponse[Task]:
    manager = get_task_manager()
    try:
        task = await manager.delete_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return StandardResponse.ok(
        data=task,
        message="Task deleted",
        request_id=request.state.request_id,
    )
