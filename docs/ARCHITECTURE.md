# Architecture — v0.1.0 (Foundation + Sprint 2)

## Scope

This release includes the **project foundation** (v0.0.1) and the
**Sprint 2 Task Engine** implementation. It intentionally excludes:

- AI provider integration (NVIDIA Nemotron models — Sprint 3)
- Authentication / authorization
- Database connectivity
- deRek Mind / agent orchestration
- Memory + RAG (Sprint 4)
- Plugin Layer (Sprint 5+)
- Email sending
- Browser automation

Those capabilities have reserved locations in the repository
(`packages/agents`, `packages/providers`, `packages/memory`, etc.) but
contain no concrete implementation yet. `packages/providers` holds an
abstract `AIProvider` interface only; the NVIDIA Nemotron model
integrations are the target for Sprint 3.

## Repository layout

```
apps/
  api/          FastAPI backend (health, version, Task Engine)
  dashboard/    React + TypeScript + Vite + Tailwind frontend
  mobile/       Reserved, not implemented
packages/
  kernel/       Reserved: the deRek Kernel — shared core every capability plugs into
  providers/    AI/model provider integrations — abstract AIProvider interface only (base.py)
  tasks/        Reserved: task execution/orchestration layer
  events/       Reserved: event bus (pub/sub)
  plugins/      Reserved: plugin system
  agents/       Reserved: agent orchestration
  memory/       Reserved: persistence/memory layer
  shared/       Reserved: cross-app shared types/utilities
docs/           Documentation
tests/          Cross-app/integration tests
tools/          Developer tooling and scripts
infrastructure/ Deployment/infra-as-code assets
```

## Task Engine (`packages/tasks`)

Sprint 2 implements the Task Engine, which is framework-agnostic (no
FastAPI dependency) and exposed over HTTP by `apps/api/routers/tasks.py`.

Every unit of work in deRek AI OS is a `Task` that moves through the
seven-state lifecycle defined in `docs/PROJECT_BIBLE.md` (Task
Lifecycle): `Queued`, `Planning`, `Running`, `Waiting`, `Completed`,
`Failed`, `Cancelled`. The package implements this lifecycle plus the
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
  `TaskExecutor`. `default_executor` performs no real work — it is the
  Task Engine's honest default, expected to be replaced by
  capability-based routing once the NVIDIA Provider lands in Sprint 3.
- **`exceptions.py`** — `TaskError`, `TaskNotFoundError`,
  `InvalidStateTransitionError`. Framework-agnostic; the API layer
  translates these into `HTTPException`.

The Task Engine does **not** implement AI providers or capability
routing — a task declares a `capability` (a lowercase snake_case
string) but nothing resolves that capability to a provider yet. That
is the Capability Router and Provider Layer's job, out of scope here.

## Backend (`apps/api`)

- **`main.py`** — Application factory. Builds the `FastAPI` instance,
  registers CORS middleware and `RequestIDMiddleware`, mounts the
  versioned API router under `API_PREFIX` (`/api/v1`), registers the
  global exception handlers, and defines startup/shutdown behavior via
  an async `lifespan` context manager.
- **`config.py`** — `pydantic-settings`-based `Settings` model. Reads
  from environment variables and an optional local `.env` file. No
  secrets are hardcoded anywhere in source.
- **`logger.py`** — Structured logging. Emits single-line JSON log
  records (toggle with `LOG_JSON`) so output is ready for any log
  aggregator without custom parsing.
- **`schemas.py`** — `StandardResponse[T]`, the API-wide response
  envelope (`success`, `message`, `data`, `request_id`, `timestamp`).
  Every endpoint — success or error — returns this shape.
- **`middleware.py`** — `RequestIDMiddleware`. Assigns/propagates a
  correlation ID (`X-Request-ID` header, honored if the caller sends
  one) via `request.state.request_id`, and logs every incoming request
  and completed response with method, path, status, and duration.
- **`exceptions.py`** — `register_exception_handlers()`. Global
  handlers for unhandled exceptions, `HTTPException`, and request
  validation errors — all logged and all returned as a
  `StandardResponse` error envelope with the correct status code.
- **`routers/health.py`** — `GET /api/v1/health` liveness endpoint.
- **`routers/version.py`** — `GET /api/v1/version` build/version info.
- **`routers/api.py`** — Aggregates the above into one router mounted
  in `main.py` under the `/api/v1` prefix.

Swagger UI is available at `/docs`, ReDoc at `/redoc`, and the raw
OpenAPI schema at `/openapi.json`.

### Response envelope

Every `/api/v1/*` response — success or error — has this shape:

```json
{
  "success": true,
  "message": "Service is healthy",
  "data": { "status": "ok" },
  "request_id": "3fae7e2b-...-...",
  "timestamp": "2026-08-07T10:00:00+00:00"
}
```

`request_id` always matches the `X-Request-ID` response header, and
echoes back a caller-supplied `X-Request-ID` request header when one
is sent.

## Frontend (`apps/dashboard`)

A single-page dashboard that displays exactly three things, per the
v0.0.1 spec:

1. Application name ("deRek AI OS")
2. Version
3. Live server status (polls `/health` and `/version`)

`src/lib/api.ts` is a minimal, dependency-free `fetch` wrapper around
the two backend endpoints; it unwraps the backend's `StandardResponse`
envelope and returns just the `data` payload to callers.
`src/components/ServerStatus.tsx` renders the card and polls the API
every 15 seconds to keep the status badge current.

## Configuration

Both apps are configured exclusively through environment variables,
each with a checked-in `.env.example` documenting every variable. No
`.env` file is committed to version control.

## Deployment

Deployment is configured per host. The repository currently ships
without a host-specific deployment configuration; the backend runs
locally via `uvicorn` and the dashboard is a standard Vite app that
can be served as a static build.
