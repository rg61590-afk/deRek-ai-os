# packages/providers

Provider foundation for deRek AI OS — implemented in Sprint 3.

## What this package provides

- **`base.py`** — The abstract `AIProvider` interface with `generate()`,
  `stream()`, `health_check()`, and supporting models
  (`ProviderRequest`, `ProviderResponse`, `ProviderMessage`,
  `ProviderUsage`, `ProviderCapability`).
- **`exceptions.py`** — Canonical provider exception hierarchy:
  `ProviderError` (base), `ProviderUnavailableError`,
  `ProviderNotFoundError`, `InvalidModelProfileError`. This is the
  single authoritative hierarchy for all provider-domain errors.
- **`models.py`** — `ModelProfile` (StrEnum: AUTO, LIGHTNING, SUPER,
  ULTRA) and `ModelMetadata` (Pydantic model with `profile`,
  `description`, and `recommended_for` keyword tags).
- **`selector.py`** — `ModelSelector`: resolves a user message and
  optional preferred profile into a concrete `ModelProfile`.
  - **Explicit selection**: passing a specific profile bypasses AUTO.
  - **AUTO selection**: deterministic keyword scoring. Each profile's
    `recommended_for` tags are matched case-insensitively against the
    user message. Profiles with zero matches are ignored.
    - No profile scores above zero: returns the configured default
      profile (SUPER by default).
    - Exactly one profile has the highest score: that profile wins.
    - Multiple profiles tie for the highest score: SUPER wins.
    Tie-breaking is explicit and does not depend on dictionary order.
- **`registry.py`** — `ProviderRegistry`: registers providers by name,
  looks them up, returns sorted names, and runs `health_check_all()`
  with graceful exception handling.
- **`nvidia/provider.py`** — `NvidiaProvider` stub. `generate()` and `stream()` raise `NotImplementedError`; `health_check()` returns `False`. No real API calls, no API keys, no hardcoded model IDs. This is a placeholder for Sprint 4 integration.

## What this package is not

This package does **not** make real AI API calls. The NVIDIA provider
is a stub: `generate()` and `stream()` raise `NotImplementedError`;
`health_check()` returns `False`. No API keys are used, no model IDs
are hardcoded, and no network calls are made. Real NVIDIA API
integration is planned for Sprint 4.
