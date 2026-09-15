"""
NVIDIA provider integration for deRek AI OS.

This package provides the NVIDIA provider implementation for the deRek
AI OS provider layer. NVIDIA NIM API integration is implemented
(Sprint 4):

- configuration via environment variables (e.g. ``NVIDIA_API_KEY``)
- non-streaming text generation via ``NvidiaProvider.generate()``
- model profile mapping via ``NvidiaSettings``
- async HTTP communication via ``NvidiaHttpClient``

``stream()`` remains unimplemented (planned for a future sprint).
"""