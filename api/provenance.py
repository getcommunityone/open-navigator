"""The "how this summary was made" facts for a decision (#798).

Only facts the analysis run recorded are returned; a missing fact is None and the page leaves it out.
Nothing here guesses a tier, prompt or source.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from pydantic import BaseModel


class Provenance(BaseModel):
    model: Optional[str] = None
    generated_at: Optional[str] = None  # ISO timestamp
    tier: Optional[str] = None  # "light" | "full"
    prompt_name: Optional[str] = None
    prompt_version: Optional[str] = None  # first 12 hex of the prompt's SHA-256
    transcript_source: Optional[str] = None
    video_url: Optional[str] = None
    # How many analyses existed for the meeting; more than 1 means the preferred one was chosen.
    analyses_for_meeting: Optional[int] = None


def _text(v: Any) -> Optional[str]:
    s = str(v).strip() if v is not None else ""
    return s or None


def _iso(v: Any) -> Optional[str]:
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else _text(v)


def build_provenance(
    prov_row: Optional[Mapping[str, Any]],
    *,
    source_ai_model: Any = None,
    extracted_at: Any = None,
    video_id: Any = None,
) -> Optional[Provenance]:
    """Merge the provenance mart row with the decision's own recorded model and time.

    Returns None when there is nothing recorded at all (so the page renders no footer)."""
    row = prov_row or {}
    tier = _text(row.get("analysis_tier"))
    vid = _text(video_id) or _text(row.get("video_id"))
    p = Provenance(
        model=_text(row.get("ai_model")) or _text(source_ai_model),
        generated_at=_iso(row.get("generated_at")) or _iso(extracted_at),
        tier=tier.lower() if tier and tier.lower() in ("light", "full") else None,
        prompt_name=_text(row.get("prompt_name")),
        prompt_version=_text(row.get("prompt_sha")),
        transcript_source=_text(row.get("transcript_source")),
        video_url=f"https://www.youtube.com/watch?v={vid}" if vid else None,
        analyses_for_meeting=(
            int(row["analyses_for_meeting"]) if row.get("analyses_for_meeting") is not None else None
        ),
    )
    return p if any(v is not None for v in p.model_dump().values()) else None
