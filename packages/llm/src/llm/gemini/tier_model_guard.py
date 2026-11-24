"""Light and full analysis never run on the same model (#796).

Light and full analyses of one meeting land in the same tables, keyed by meeting and model name.
Two runs on one model would overwrite each other's rows, silently losing the light analysis.
The owner's rule is that the two tiers never share a model; this makes it fail loudly instead of
relying on everyone remembering it.

The light tier's model is ``LIGHT_MODEL`` (default ``deepseek-flash``); an empty ``LIGHT_MODEL``
means the Gemini default. A light run is also checked against ``FULL_MODEL`` when that is set.
"""

from __future__ import annotations

import os
from typing import Mapping, Optional

DEFAULT_LIGHT_MODEL = "deepseek-flash"


def light_model(env: Mapping[str, str], gemini_default: str) -> str:
    """The model the light tier is configured to use."""
    if "LIGHT_MODEL" not in env:
        return DEFAULT_LIGHT_MODEL
    return (env.get("LIGHT_MODEL") or "").strip() or gemini_default


def tier_model_conflict(
    *,
    tier: str,
    model: str,
    part_2_model: str = "",
    gemini_default: str,
    env: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """An error message when this run would share a model with the other tier, else ``None``."""
    e = os.environ if env is None else env
    used = {(model or "").strip() or gemini_default, (part_2_model or "").strip() or (model or "").strip() or gemini_default}
    if tier == "full":
        other = light_model(e, gemini_default)
        clash = sorted(m for m in used if m == other)
        if clash:
            return (
                f"A full analysis would run on {clash[0]!r}, the model the light tier uses "
                f"(LIGHT_MODEL). Light and full must never share a model: their rows would "
                f"overwrite each other. Pick a different --model for full, or change LIGHT_MODEL."
            )
    elif tier == "light":
        other = (e.get("FULL_MODEL") or "").strip()
        if other and other in used:
            return (
                f"A light analysis would run on {other!r}, the model the full tier uses "
                f"(FULL_MODEL). Light and full must never share a model: their rows would "
                f"overwrite each other. Pick a different --model for light."
            )
    return None
