# deRek AI OS

Version **0.0.1** — project foundation.

This release contains the production-ready **skeleton** only:
a FastAPI backend and a React/TypeScript/Vite dashboard. It
intentionally does **not** include AI integration, authentication,
database connectivity, agents, email, or browser automation — those
are reserved for later releases (see `docs/architecture.md`).

---

## Repository structure

```
apps/
  api/          FastAPI backend
  dashboard/    React + TypeScript + Vite + Tailwind frontend
  mobile/       Reserved, not implemented in v0.0.1
packages/
  kernel/ providers/ tasks/ events/ plugins/ agents/ memory/ shared/   Reserved
docs/           Documentation
tests/          Cross-app/integration tests
tools/          Developer tooling and scripts
infrastructure/ Deployment/infra-as-code assets
```

---

## Prerequisites

- Python 3.11
- Node.js 20+ and npm
- (Optional) Replit, for hosted deployment

---

## 1. Backend setup (`apps/api`)

```bash
cd apps/api

# Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# edit .env if you need non-default values — never commit this file
```

### Run the API

```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Or simply:

```bash
python main.py
```

Once running:

| Endpoint | URL |
|---|---|
| Root | http://localhost:8000/ |
| Health | http://localhost:8000/api/v1/health |
| Version | http://localhost:8000/api/v1/version |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| OpenAPI schema | http://localhost:8000/openapi.json |

### Run backend tests

```bash
cd apps/api
pytest
```

This runs the suite in `apps/api/tests/`, covering the health
endpoint, version endpoint, root endpoint, Swagger/OpenAPI
availability, the request-ID/response-envelope contract, and the
global exception handler.

---

## 2. Frontend setup (`apps/dashboard`)

```bash
cd apps/dashboard

# Install dependencies
npm install

# Configure environment variables
cp .env.example .env
# edit .env if your API runs somewhere other than localhost:8000
```

### Run the dashboard

```bash
npm run dev
```

The dashboard will be available at http://localhost:5173 and will
display the application name, version, and live server status by
polling the backend's `/health` and `/version` endpoints. Make sure
the API (step 1) is running first, or the status badge will show
**Offline**.

### Build for production

```bash
npm run build
npm run preview
```

---

## 3. Running both together (local development)

Open two terminals:

```bash
# Terminal 1
cd apps/api && source .venv/bin/activate && python main.py

# Terminal 2
cd apps/dashboard && npm run dev
```

---

## 4. Deployment (Replit)

The repository root includes `.replit`, `replit.nix`, and
`tools_run_api.sh`. On Replit, clicking **Run** will:

1. Install backend dependencies from `apps/api/requirements.txt`
2. Copy `.env.example` to `.env` if no `.env` exists yet
3. Start the API with `uvicorn` on the port Replit assigns

Deploy the dashboard separately as a static site (`npm run build`
produces `apps/dashboard/dist/`), pointing `VITE_API_BASE_URL` at your
deployed API's `/api/v1` prefix.

---

## Configuration reference

All configuration is via environment variables — nothing is
hardcoded. See:

- `apps/api/.env.example` for backend variables (app name/version,
  host/port, API prefix, CORS origins, log level/format).
- `apps/dashboard/.env.example` for frontend variables (API base URL,
  dev server port).

Never commit a real `.env` file — both are already excluded via
`.gitignore`.

---

## Logging

The backend emits structured JSON logs by default (`LOG_JSON=true`),
one JSON object per line, suitable for any log aggregator. Set
`LOG_JSON=false` for human-readable console output during local
development.

---

## Further reading

See `docs/architecture.md` for a deeper description of what each file
does and why the reserved `packages/*` directories are empty in this
release.
