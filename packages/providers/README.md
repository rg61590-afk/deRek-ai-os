# packages/providers

Abstract AI provider interface — `base.py` defines the `AIProvider`
contract (request/response models, capability flags, error types) that
every concrete provider integration must implement.

No concrete provider is implemented in the current release. NVIDIA
Nemotron models (Lightning, Super, Ultra, Embed) are the planned
integrations for future sprints, targeting the abstract interface
defined here. Additional providers may be added later using the same
interface.
