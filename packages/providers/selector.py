"""
Model selector for deRek AI OS.

Resolves a user's requested model preference into a concrete
`ModelProfile`. When the user requests AUTO, the selector applies
deterministic, keyword-based heuristics to choose LIGHTNING, SUPER,
or ULTRA. No external API calls or LLM reasoning is involved.
"""

from __future__ import annotations

from typing import Optional

from packages.providers.exceptions import InvalidModelProfileError
from packages.providers.models import ModelMetadata, ModelProfile


class ModelSelector:
    """Deterministic, rule-based model selector.

    Parameters
    ----------
    profiles : dict[ModelProfile, ModelMetadata]
        Metadata for each supported profile. Used for AUTO routing.
    default_profile : ModelProfile
        Fallback profile when AUTO rules cannot determine a match and
        no explicit profile was given.
    """

    def __init__(
        self,
        profiles: dict[ModelProfile, ModelMetadata],
        default_profile: ModelProfile = ModelProfile.SUPER,
    ) -> None:
        self._profiles = dict(profiles)
        self._default = default_profile

    def select(
        self,
        message: str,
        preferred: str | ModelProfile = ModelProfile.AUTO,
    ) -> ModelProfile:
        """Resolve the user's preferred model to a `ModelProfile`.

        Parameters
        ----------
        message:
            The user's input text. Used only when *preferred* is AUTO.
        preferred:
            A `ModelProfile` member or its string value. If the string
            is unrecognised, `InvalidModelProfileError` is raised.

        Returns
        -------
        ModelProfile
            The resolved profile. When *preferred* is AUTO, a profile
            is chosen based on keyword matching against each profile's
            `recommended_for` tags.
        """
        if not isinstance(preferred, ModelProfile):
            try:
                preferred = ModelProfile(preferred)
            except ValueError:
                raise InvalidModelProfileError(preferred)

        if preferred is not ModelProfile.AUTO:
            return preferred

        return self._auto_select(message)

    def _auto_select(self, message: str) -> ModelProfile:
        """Choose a profile for an AUTO request using keyword heuristics.

        Scoring rules
        -------------
        - Each `ModelProfile` (except AUTO) contributes a score equal to
          the number of its `recommended_for` tags that appear
          case-insensitively in *message*.
        - Profiles with a score of 0 are skipped.
        - If no profile scores at all, the selector falls back to
          `self._default`.
        - If exactly one profile has the highest score, that profile wins.
        - If multiple profiles tie for the highest score, SUPER wins.
        """
        lowered = message.lower()
        scores: dict[ModelProfile, int] = {}

        for profile, metadata in self._profiles.items():
            if profile is ModelProfile.AUTO:
                continue
            score = sum(1 for tag in metadata.recommended_for if tag in lowered)
            if score > 0:
                scores[profile] = score

        if not scores:
            return self._default

        max_score = max(scores.values())
        winners = [p for p, s in scores.items() if s == max_score]

        if len(winners) == 1:
            return winners[0]

        return ModelProfile.SUPER