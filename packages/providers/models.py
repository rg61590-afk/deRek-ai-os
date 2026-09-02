"""
Model domain for deRek AI OS.

Defines the logical model profiles (AUTO, LIGHTNING, SUPER, ULTRA) that
users select from, plus metadata describing each profile's intended use.
These are deRek-internal profiles — the mapping to actual provider model
identifiers is the selector/registry's responsibility and is resolved at
runtime, not hardcoded here.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ModelProfile(str, Enum):
    """Logical model profiles available to deRek AI OS users.

    These are deRek-internal abstractions. The mapping from each profile
    to an actual provider model identifier is handled by the
    `ModelSelector` and `ProviderRegistry`, and is configurable rather
    than baked into this enum.
    """

    AUTO = "auto"
    LIGHTNING = "lightning"
    SUPER = "super"
    ULTRA = "ultra"


class ModelMetadata(BaseModel):
    """Static metadata describing a logical model profile.

    Filled in once at startup (or by tests) and consumed by the
    `ModelSelector` to inform AUTO routing decisions. These descriptions
    are intentionally abstract — no benchmark numbers or vendor-specific
    capabilities are declared here.
    """

    profile: ModelProfile = Field(..., description="Which profile this metadata describes")
    description: str = Field(
        ...,
        description="One-line summary of the profile's intended use.",
    )
    recommended_for: list[str] = Field(
        default_factory=list,
        description="Keyword tags the selector can match against when routing AUTO requests.",
    )