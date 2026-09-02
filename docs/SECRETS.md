# Security — Secret Management

This document defines how deRek AI OS handles API keys, credentials,
and other sensitive configuration.

## 1. Security Architecture

All API keys and private credentials remain **backend-side only**.

```
Frontend                    FastAPI Backend                 External Providers
  |                              |                               |
  |  User requests only          |  Private environment variables |
  |----------------------------->|                               |
  |                              |------------------------------>|
  |                              |    (API key stays server-side) |
  |<-----------------------------|                               |
  |  Responses only              |                               |
  |  (NO secrets returned)       |                               |
```

The FastAPI backend is the **trusted boundary**. All provider
communication flows through it. The frontend never contacts external
AI providers directly and never receives API keys.

## 2. Local Development Secrets

### `apps/api/.env` — NEVER COMMITTED

This file contains private credentials for local development only.

- **Purpose:** Local development secrets (API keys, URLs, tokens).
- **Committed to Git:** NO. This file is listed in `.gitignore` via
  `*.env`.
- **Who creates it:** Each developer copies `.env.example` to `.env`
  and fills in their own private values.

```bash
cd apps/api
cp .env.example .env
# Edit .env with your private credentials
```

### `apps/api/.env.example` — COMMITTED

This file documents which environment variables the backend expects.
It contains only empty values or safe public defaults.

- **Purpose:** Documentation of required environment variables.
- **Committed to Git:** YES. This file is tracked.
- **Contains secrets:** NO. Only variable names and safe defaults.

### `.gitignore` Protection

The root `.gitignore` contains:

```
*.env
!*.env.example
```

This ensures any file ending in `.env` is ignored, except files
explicitly named `.env.example`.

## 3. Environment Variables

### NVIDIA Provider (Sprint 4)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `NVIDIA_API_KEY` | Yes | — | NVIDIA API authentication key |
| `NVIDIA_BASE_URL` | No | `https://integrate.api.nvidia.com/v1` | NVIDIA API endpoint |
| `NVIDIA_TIMEOUT_SECONDS` | No | `60` | HTTP request timeout |
| `NVIDIA_MODEL_LIGHTNING` | No | — | Model ID for LIGHTNING profile |
| `NVIDIA_MODEL_SUPER` | No | — | Model ID for SUPER profile |
| `NVIDIA_MODEL_ULTRA` | No | — | Model ID for ULTRA profile |

### Future Providers (Placeholders)

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | OpenAI API key (future) |
| `ANTHROPIC_API_KEY` | Anthropic API key (future) |
| `GOOGLE_API_KEY` | Google API key (future) |

### Future Infrastructure

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Database connection string (future) |
| `REDIS_URL` | Redis connection string (future) |
| `JWT_SECRET` | JWT signing secret (future) |

## 4. Where to Paste Credentials

### NVIDIA_API_KEY

Paste your NVIDIA API key in:

```
apps/api/.env
```

On the line:

```
NVIDIA_API_KEY=your-key-here
```

**Do not paste the key into `.env.example` or any tracked file.**

### Model IDs

Paste NVIDIA model IDs in:

```
apps/api/.env
```

On the relevant lines:

```
NVIDIA_MODEL_LIGHTNING=nemotron-3.5-lightning
NVIDIA_MODEL_SUPER=nemotron-3-super
NVIDIA_MODEL_ULTRA=nemotron-3-ultra
```

Leave these empty until model IDs are confirmed.

## 5. What the Backend Must Never Do

The backend must never:

- Log API keys or tokens
- Return API keys in API responses
- Expose secrets through environment variables to the frontend
- Embed credentials in source code
- Commit `.env` files

## 6. Frontend Security

The dashboard (`apps/dashboard`) must never:

- Import or reference backend environment variables
- Contain provider API keys
- Contain secret tokens or credentials
- Call AI providers directly
- Receive secret configuration from the backend

If a frontend file ever contains `NVIDIA_API_KEY`, `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `DATABASE_URL`, or `JWT_SECRET`, this is a
security violation that must be reported and fixed immediately.

## 7. Production Secret Management

`apps/api/.env` is for **local development only**.

In production, secrets must be injected through:

- The deployment platform's secret manager (e.g., AWS Secrets Manager,
  GCP Secret Manager, Azure Key Vault)
- Environment variables set by the deployment pipeline
- A dedicated secrets management system

Never copy a local `.env` to a production environment.

## 8. Adding New Credentials

When a new provider or service is integrated:

1. Add the environment variable name to `apps/api/.env.example`
2. Add a placeholder entry in `apps/api/.env`
3. Load it through the provider's configuration class
4. Never hardcode the value
5. Never commit the real value
