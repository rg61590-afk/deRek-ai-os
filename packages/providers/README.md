# packages/providers

Provider foundation for deRek AI OS — implemented in Sprint 3 and Sprint 4.

## Overview

The `packages/providers` package provides the AI Provider Layer. It defines
the abstract interface all AI providers implement, the logical model profiles
users select from, the deterministic model selector for AUTO mode, the provider
registry, and concrete provider implementations.

## Architecture

```
User Request
    ↓
ModelSelector (resolves AUTO → concrete profile)
    ↓
ProviderRegistry (lookup by name)
    ↓
AIProvider.generate() (concrete provider)
    ↓
ProviderResponse
```

## IMPLEMENTED

- **Abstract provider interface** (`base.py`) — `AIProvider` ABC with
  `generate()`, `stream()`, and `health_check()`.
- **Provider-agnostic types** — `ProviderRequest`, `ProviderResponse`,
  `ProviderMessage`, `ProviderUsage`, `ProviderCapability`.
- **Exception hierarchy** (`exceptions.py`) — `ProviderError` (base),
  `ProviderUnavailableError`, `ProviderNotFoundError`, `InvalidModelProfileError`.
- **Logical model profiles** (`models.py`) — `ModelProfile` (AUTO, LIGHTNING,
  SUPER, ULTRA) and `ModelMetadata` (description + keyword tags).
- **ModelSelector** (`selector.py`) — deterministic keyword-scoring AUTO
  selection with SUPER tie-breaking. Explicit profiles bypass AUTO.
- **ProviderRegistry** (`registry.py`) — registers providers by name, lookup,
  `health_check_all()` with graceful error handling.
- **NVIDIA provider** (`nvidia/provider.py`) — real non-streaming text
  generation via `NvidiaHttpClient`. Maps logical profiles to configured
  NVIDIA model IDs. `stream()` raises `NotImplementedError`.
- **NVIDIA HTTP client** (`nvidia/client.py`) — async HTTP client wrapping
  `httpx.AsyncClient` with NVIDIA authentication, timeout, and error
  translation.
- **NVIDIA configuration** (`nvidia/config.py`) — `NvidiaSettings` reads
  `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_TIMEOUT_SECONDS`, and
  model ID mappings from environment variables.

## Application-Layer Integration (Sprint 4)

The `apps/api` package provides:

- **`services/ai.py`** — Application service layer that wires ModelSelector,
  ProviderRegistry, and NvidiaProvider together. Resolves AUTO, builds
  ProviderRequest, invokes the provider, returns the response.
- **`routers/chat.py`** — `POST /api/v1/chat` endpoint. Accepts a
  provider-agnostic chat request, dispatches to the AI service layer,
  and returns the response in the standard `StandardResponse` envelope.

## Contract

Every provider implementation must:

1. Subclass `AIProvider`.
2. Set `name` (e.g. `"nvidia"`).
3. Declare `capabilities` as a `frozenset[ProviderCapability]`.
4. Implement `generate(request: ProviderRequest) -> ProviderResponse`.
5. Implement `stream(request: ProviderRequest) -> AsyncIterator[str]`.
6. Implement `health_check() -> bool`.
7. Raise `ProviderError` (or a subclass) on failure — never leak
   provider-specific exceptions.

## NOT IMPLEMENTED

- NVIDIA streaming
- deRek Mind / agent orchestration
- Memory + RAG
- Embeddings
- Autonomous workflows
- Additional providers (Anthropic, OpenAI, etc.)
