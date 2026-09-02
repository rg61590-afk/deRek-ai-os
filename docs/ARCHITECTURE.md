# Architecture — v0.1.0 (Sprint 1 + Sprint 2 + Sprint 2.1 + Sprint 3)

## Scope

This release includes the **project foundation** (Sprint 1), the
**Sprint 2 Task Engine**, the **Sprint 2.1 Runtime Modernization**, and the
**Sprint 3 Provider Foundation and Model Selection** implementation.
It intentionally excludes:

- Real NVIDIA API integration (Sprint 4)
- Authentication / authorization
- Database connectivity
- deRek Mind / agent orchestration
- Memory + RAG (Sprint 5+)
- Plugin Layer (Sprint 5+)
- Email sending
- Browser automation

## CURRENT IMPLEMENTATION

### Task Engine (`packages/tasks`)

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
  `TaskExecutor`. `default_executor` performs no real work.
- **`exceptions.py`** — `TaskError`, `TaskNotFoundError`,
  `InvalidStateTransitionError`. Framework-agnostic; the API layer
  translates these into `HTTPException`.

The Task Engine does **not** implement AI providers or capability
routing — a task declares a `capability` (a lowercase snake_case
string) but nothing resolves that capability to a provider yet.

### Provider Foundation (`packages/providers`)

Sprint 3 implements the provider abstraction, model profiles, model
selection, and a provider registry. No real AI API calls are made.

- **`base.py`** — `AIProvider` abstract base class with `generate()`,
  `stream()`, and `health_check()`. Also defines `ProviderCapability`,
  `ProviderRequest`, `ProviderResponse`, `ProviderMessage`, and
  `ProviderUsage`.
- **`exceptions.py`** — The canonical provider exception hierarchy:
  `ProviderError` (base), `ProviderUnavailableError`,
  `ProviderNotFoundError`, `InvalidModelProfileError`. This is the
  single, authoritative hierarchy for all provider-domain errors.
- **`models.py`** — `ModelProfile` (StrEnum: AUTO, LIGHTNING, SUPER,
  ULTRA) and `ModelMetadata` (Pydantic model with `profile`,
  `description`, and `recommended_for` keyword tags).
- **`selector.py`** — `ModelSelector`: resolves a user message and
  optional preferred profile into a concrete `ModelProfile`.
  - **Explicit selection**: passing a specific profile bypasses AUTO.
  - **AUTO selection**: deterministic keyword scoring. Each profile's
    `recommended_for` tags are matched against the user message
    (case-insensitive). Profiles with zero matches are ignored.
    - If no profile scores above zero: returns the configured default
      profile (SUPER by default).
    - If exactly one profile has the highest score: that profile wins.
    - If multiple profiles tie for the highest score: SUPER wins.
    Tie-breaking is explicit and does not depend on dictionary order.
- **`registry.py`** — `ProviderRegistry`: registers providers by name,
  looks them up, reports sorted names, and runs `health_check_all()`
  with graceful exception handling.
- **`nvidia/`** — Placeholder package. `NvidiaProvider` is a stub where `generate()` and `stream()` raise `NotImplementedError`; `health_check()` returns `False`. No API calls, no API keys, no hardcoded model IDs.

### Backend (`apps/api`)

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
- **`routers/tasks.py`** — Task Engine HTTP interface (CRUD, state
  transitions).
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

### Frontend (`apps/dashboard`)

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

### Configuration

Both apps are configured exclusively through environment variables,
each with a checked-in `.env.example` documenting every variable. No
`.env` file is committed to version control.

### Deployment

Deployment is configured per host. The repository currently ships
without a host-specific deployment configuration; the backend runs
locally via `uvicorn` and the dashboard is a standard Vite app that
can be served as a static build.

---

## PLANNED ARCHITECTURE

The following components and flows are planned but **not yet implemented**.

### NVIDIA Provider Integration (Sprint 4)

```
User Request
    ↓
ModelSelector
    ↓
ProviderRegistry
    ↓
NVIDIA Provider
    ↓
NVIDIA API
    ↓
Real Nemotron Model
```

The `NvidiaProvider` stub in `packages/providers/nvidia/provider.py` will
be replaced with a real implementation that:

- Accepts configuration via environment variables (e.g. `NVIDIA_API_KEY`)
- Maps deRek model profiles to NVIDIA model identifiers
- Makes requests to the NVIDIA NIM or NVIDIA AI Foundation API
- Implements `generate`, `stream`, and `health_check`

No real API calls, API keys, or model IDs exist in the current codebase.

### deRek Mind / Agent Architecture (Planned)

```
User
 ↓
Task Engine
 ↓
deRek Mind
 ↓
Planner → Tool Executor → Observation → Evaluation → Retry → Verification
 ↓
Completion
```

### Memory + RAG (Planned)

```
Memory Layer
  ↓
Hybrid Retrieval (semantic, keyword, structured)
  ↓
Reranking
  ↓
Context Builder
  ↓
deRek Mind
```

`Nemotron Embed` is the planned retrieval/embedding model for this layer.
No memory, retrieval, or RAG implementation exists in the current codebase.

### Event Bus and Workers (Planned)

Background and asynchronous execution processes separate from the
request/response cycle, with publish/subscribe communication between
subsystems.

### Plugin Layer (Planned)

Third-party integrations (GitHub, Slack, Discord, Notion, Gmail,
Outlook, Google Drive, Google Calendar, Docker, AWS, Local Files,
Browser Automation) registered against defined extension points.
