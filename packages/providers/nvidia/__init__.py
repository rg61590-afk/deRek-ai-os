"""
NVIDIA provider integration for deRek AI OS.

This package is a placeholder. NVIDIA API integration is planned but
**not implemented** in Sprint 3 — no network calls are made, no API
key is required, and no actual model identifiers are hardcoded here.

Future implementation will:
- accept configuration via environment variables (e.g. NVIDIA_API_KEY)
- map deRek model profiles to NVIDIA model identifiers
- make requests to the NVIDIA NIM or NVIDIA AI Foundation API
- implement `generate`, `stream`, and `health_check` on `NvidiaProvider`
"""