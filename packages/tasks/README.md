# packages/tasks

The Task Engine — implemented in Sprint 2. Framework-agnostic (no
FastAPI dependency); exposed over HTTP by `apps/api/routers/tasks.py`.

## What this package is

Every unit of work in deRek AI OS is a `Task` that moves through the
exact seven-state lifecycle defined in `docs/PROJECT_BIBLE.md` (Task
Lifecycle): `Queued`, `Planning`, `Running`, `Waiting`, `Completed`,
`Failed`, `Cancelled`. This package implements that lifecycle plus the
in-memory storage, queuing, and processing needed to create and run a
task end to end.

- **`models.py`** — `Task`, `TaskTransition`, `TaskState`, and
  `ExecutionMode` (Interactive, Background, Scheduled, Event Driven,
  Autonomous — per Execution Modes in the Bible). Pure Pydantic v2
  data models; no I/O.
- **`state_machine.py`** — the authoritative transition graph
  (`ALLOWED_TRANSITIONS`) and `apply_transition()`, which validates a
  transition and appends it to the task's history rather than
  overwriting prior state.
- **`queue.py`** — `TaskQueue`, a thin `asyncio.Queue` wrapper holding
  task IDs awaiting processing.
- **`manager.py`** — `TaskManager`, the in-memory store and the single
  point through which tasks are created, looked up, listed,
  transitioned, completed, failed, and deleted.
- **`worker.py`** — `TaskWorker`, which drives a task through
  `Queued -> Planning -> Running -> Completed`/`Failed` via a pluggable
  `TaskExecutor`. `default_executor` performs no real work — see
  "What this package is not" below.
- **`exceptions.py`** — `TaskError`, `TaskNotFoundError`,
  `InvalidStateTransitionError`. Framework-agnostic; the API layer
  translates these into `HTTPException`.

## What this package is not

Per Sprint 2's explicit scope, this package does **not** implement:

- AI providers or capability routing — a task declares a `capability`
  (a lowercase snake_case string, per Naming Conventions) but nothing
  resolves that capability to a provider yet. That is the Capability
  Router and Provider Layer's job (see `docs/PROJECT_BIBLE.md`,
  sections 6–7), out of scope here.
- Memory, plugins, agents, a database, or authentication.
- A continuous background worker loop — `TaskWorker.run()` exists and
  is fully implemented for when that's in scope (Event Bus & Workers,
  per the Long-Term Roadmap), but Sprint 2 processes each task
  synchronously and inline via `TaskWorker.process_one()`, called once
  from `POST /api/v1/tasks`.

`worker.default_executor` is the Task Engine's own honest default: it
performs no external work and says so in the result it returns. It
exists so a task's full lifecycle is genuinely exercisable end to end
without a real capability behind it yet, and is expected to be
replaced by capability-based routing once the Provider Layer lands.

## Storage

In-memory only (`TaskManager._tasks`, a plain `dict`). State does not
survive a process restart. No database is used in this sprint.
