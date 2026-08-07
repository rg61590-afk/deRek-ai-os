# Architecture — v0.0.1 (Foundation)

## Scope

This release is the project **foundation only**. It intentionally
excludes:

- AI provider integration
- Authentication / authorization
- Database connectivity
- Agents / agent orchestration
- Email sending
- Browser automation

Those capabilities have reserved locations in the repository
(`packages/agents`, `packages/providers`, `packages/memory`, etc.) but
contain no implementation yet. As of Sprint 001, `packages/providers`
holds an abstract `AIProvider` interface only — still no concrete
Claude/Gemini/etc. integration.

## Repository layout

```
apps/
  api/          FastAPI backend (this release: skeleton + health/version)
  dashboard/    React + TypeScript + Vite + Tailwind frontend
  mobile/       Reserved, not implemented in v0.0.1
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

The repository root includes a `.replit` file and `replit.nix` for
running the API on Replit. The dashboard is a standard Vite app and
can be deployed to any static host or run alongside the API.
