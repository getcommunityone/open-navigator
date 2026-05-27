"""Per-run metrics object."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class PipelineRun:
    run_id: str
    source: str
    started_at: datetime
    finished_at: datetime | None = None
    extracted: int = 0
    validated: int = 0
    rejected: int = 0
    loaded: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def duration(self) -> timedelta:
        return (self.finished_at or datetime.utcnow()) - self.started_at
