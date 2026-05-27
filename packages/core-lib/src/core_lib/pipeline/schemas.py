"""Pydantic envelopes for pipeline rows and per-run context."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RawRow(BaseModel):
    """Base for every raw row written to raw_<source> schemas."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    source_version: str
    ingested_at: datetime = Field(default_factory=_utcnow)
    natural_key: str


class PipelineContext(BaseModel):
    """Per-run context, threaded through every stage."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    started_at: datetime
    params: dict[str, Any] = Field(default_factory=dict)
