"""Tests for the Task Engine.

Covers two layers, per Testing Standards in docs/PROJECT_BIBLE.md
("tests are written against public interfaces and observable
behavior"):

- API-level tests against `/api/v1/tasks`, using the same
  `TestClient` pattern as the rest of `apps/api/tests/`.
- Task Engine unit tests against `packages.tasks` directly, to verify
  the state machine's transition graph precisely — the architectural
  core of Sprint 2.

Importing `main` first (before any `packages.tasks` import) ensures
`main.py`'s repository-root `sys.path` bootstrap has already run,
regardless of test collection order.
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from packages.tasks import (
    InvalidStateTransitionError,
    TaskManager,
    TaskQueue,
    TaskState,
)

client = TestClient(app)


def _create_task(name: str, capability: str = "research", **extra):
    payload = {"name": name, "capability": capability, **extra}
    return client.post("/api/v1/tasks", json=payload)


# --- API: task creation -------------------------------------------------------


def test_create_task_returns_201_and_standard_envelope():
    response = _create_task("create-task-basic")
    assert response.status_code == 201

    body = response.json()
    assert body["success"] is True
    assert "request_id" in body and body["request_id"]
    assert response.headers["X-Request-ID"] == body["request_id"]

    data = body["data"]
    assert data["id"]
    assert data["name"] == "create-task-basic"
    assert data["capability"] == "research"


def test_create_task_defaults_execution_mode_to_interactive():
    data = _create_task("default-execution-mode").json()["data"]
    assert data["execution_mode"] == "Interactive"


def test_create_task_runs_synchronously_to_a_terminal_state():
    # Sprint 2 has no background worker loop: the task enqueued by this
    # request is processed inline before the response is returned.
    data = _create_task("runs-to-completion").json()["data"]

    assert data["state"] == "Completed"
    assert data["result"] is not None
    assert data["error"] is None

    history_states = [entry["to_state"] for entry in data["history"]]
    assert history_states == ["Queued", "Planning", "Running", "Completed"]
    assert data["history"][0]["from_state"] is None


def test_create_task_rejects_invalid_capability():
    response = _create_task("bad-capability", capability="Not Snake Case!")
    assert response.status_code == 422

    # response.json() itself proves the body is valid, parseable JSON —
    # this is what fails if a raw (non-JSON-safe) exception object ever
    # leaks into the response content again.
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Request validation failed"
    assert body["data"] is not None
    assert "request_id" in body and body["request_id"]
    assert "timestamp" in body
    assert response.headers["X-Request-ID"] == body["request_id"]

    errors = body["data"]["errors"]
    assert len(errors) >= 1
    error = next(e for e in errors if e["loc"][-1] == "capability")
    # The validator's message is preserved as plain text, not lost
    # during sanitization, and any embedded context is JSON-safe
    # (a raw exception instance would fail response.json() above
    # before this assertion is even reached).
    assert "snake_case" in error["msg"]
    if "ctx" in error:
        assert isinstance(error["ctx"], dict)
        for value in error["ctx"].values():
            assert isinstance(value, (str, int, float, bool, type(None), list, dict))


def test_create_task_rejects_blank_name():
    response = _create_task("   ")
    assert response.status_code == 422

    body = response.json()
    assert body["success"] is False
    assert "request_id" in body and body["request_id"]

    errors = body["data"]["errors"]
    error = next(e for e in errors if e["loc"][-1] == "name")
    assert "blank" in error["msg"]
    if "ctx" in error:
        assert isinstance(error["ctx"], dict)
        for value in error["ctx"].values():
            assert isinstance(value, (str, int, float, bool, type(None), list, dict))


# --- API: task retrieval -------------------------------------------------------


def test_get_task_returns_the_created_task():
    created = _create_task("get-task-target").json()["data"]

    response = client.get(f"/api/v1/tasks/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["id"] == created["id"]
    assert body["data"]["name"] == "get-task-target"


def test_list_tasks_includes_created_task():
    created = _create_task("list-task-target").json()["data"]

    response = client.get("/api/v1/tasks")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert created["id"] in [task["id"] for task in body["data"]]


def test_list_tasks_filters_by_state():
    created = _create_task("filter-by-state").json()["data"]

    completed = client.get("/api/v1/tasks", params={"state": "Completed"}).json()["data"]
    assert created["id"] in [task["id"] for task in completed]

    running = client.get("/api/v1/tasks", params={"state": "Running"}).json()["data"]
    assert created["id"] not in [task["id"] for task in running]


# --- API: invalid task lookup -------------------------------------------------


def test_get_task_invalid_id_returns_404_standard_envelope():
    response = client.get("/api/v1/tasks/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert "request_id" in body and body["request_id"]


def test_delete_task_invalid_id_returns_404():
    response = client.delete("/api/v1/tasks/does-not-exist")

    assert response.status_code == 404
    assert response.json()["success"] is False


# --- API: delete ----------------------------------------------------------------


def test_delete_task_removes_it():
    created = _create_task("delete-me").json()["data"]

    response = client.delete(f"/api/v1/tasks/{created['id']}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == created["id"]

    follow_up = client.get(f"/api/v1/tasks/{created['id']}")
    assert follow_up.status_code == 404


# --- Task Engine unit tests: state transitions --------------------------------


async def test_valid_transition_is_recorded_in_history():
    manager = TaskManager(queue=TaskQueue())
    task = await manager.create_task(name="unit-valid-transition", capability="research")
    assert task.state == TaskState.QUEUED

    task = await manager.transition_task(task.id, TaskState.PLANNING, reason="unit test")

    assert task.state == TaskState.PLANNING
    assert task.history[-1].from_state == TaskState.QUEUED
    assert task.history[-1].to_state == TaskState.PLANNING
    assert task.history[-1].reason == "unit test"


async def test_invalid_transition_is_rejected():
    manager = TaskManager(queue=TaskQueue())
    task = await manager.create_task(name="unit-invalid-transition", capability="research")

    # Queued -> Completed skips Planning and Running and is not a
    # legal transition in the state machine.
    with pytest.raises(InvalidStateTransitionError):
        await manager.transition_task(task.id, TaskState.COMPLETED)


async def test_terminal_state_permits_no_further_transitions():
    manager = TaskManager(queue=TaskQueue())
    task = await manager.create_task(name="unit-terminal-state", capability="research")
    task = await manager.transition_task(task.id, TaskState.PLANNING)
    task = await manager.transition_task(task.id, TaskState.RUNNING)
    task = await manager.complete_task(task.id, result={"ok": True})
    assert task.state == TaskState.COMPLETED

    with pytest.raises(InvalidStateTransitionError):
        await manager.transition_task(task.id, TaskState.RUNNING)


async def test_waiting_state_can_resume_to_running():
    manager = TaskManager(queue=TaskQueue())
    task = await manager.create_task(name="unit-waiting-resume", capability="research")
    task = await manager.transition_task(task.id, TaskState.PLANNING)
    task = await manager.transition_task(task.id, TaskState.RUNNING)

    task = await manager.transition_task(task.id, TaskState.WAITING, reason="paused")
    assert task.state == TaskState.WAITING

    task = await manager.transition_task(task.id, TaskState.RUNNING, reason="resumed")
    assert task.state == TaskState.RUNNING
