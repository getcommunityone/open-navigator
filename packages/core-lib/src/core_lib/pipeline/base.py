"""Abstract data-source pipeline. Subclass per data source."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import AsyncIterator, Generic, TypeVar

from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import async_session
from .metrics import PipelineRun
from .schemas import PipelineContext, RawRow

R = TypeVar("R", bound=RawRow)


class DataSourcePipeline(ABC, Generic[R]):
    """
    Standard ingestion pipeline contract.

    Subclasses implement extract / row_schema / load_batch.
    validate() is provided for free via the pydantic row schema.
    run() orchestrates extract → validate → load with batching, metrics, rollback.

    Conventions:
      - `source` matches the `raw_<source>` schema name
      - `extract()` yields raw dicts (not pydantic instances)
      - `load_batch()` writes pre-validated pydantic rows in chunks of `batch_size`
    """

    source: str
    batch_size: int = 1_000

    @property
    @abstractmethod
    def row_schema(self) -> type[R]: ...

    @abstractmethod
    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]: ...

    @abstractmethod
    async def load_batch(
        self, session: AsyncSession, rows: list[R], ctx: PipelineContext
    ) -> None: ...

    def validate(self, raw: dict) -> R | None:
        try:
            return self.row_schema.model_validate(raw)
        except ValidationError as e:
            logger.bind(source=self.source, errors=e.errors()).warning("row_rejected")
            return None

    async def run(self, **params) -> PipelineRun:
        ctx = PipelineContext(
            run_id=uuid.uuid4().hex,
            started_at=datetime.now(timezone.utc),
            params=params,
        )
        run = PipelineRun(run_id=ctx.run_id, source=self.source, started_at=ctx.started_at)
        bound = logger.bind(source=self.source, run_id=ctx.run_id)
        bound.info("pipeline_start")

        try:
            batch: list[R] = []
            async for raw in self.extract(ctx):
                run.extracted += 1
                row = self.validate(raw)
                if row is None:
                    run.rejected += 1
                    continue
                batch.append(row)
                run.validated += 1
                if len(batch) >= self.batch_size:
                    await self._flush(batch, ctx, run)
                    batch.clear()
            if batch:
                await self._flush(batch, ctx, run)
        except Exception as e:
            run.errors.append(repr(e))
            bound.exception("pipeline_failed")
            raise
        finally:
            run.finished_at = datetime.now(timezone.utc)
            bound.bind(
                extracted=run.extracted,
                validated=run.validated,
                rejected=run.rejected,
                loaded=run.loaded,
                duration_s=run.duration.total_seconds(),
            ).info("pipeline_complete")
        return run

    async def _flush(self, batch: list[R], ctx: PipelineContext, run: PipelineRun) -> None:
        async with async_session() as session:
            await self.load_batch(session, batch, ctx)
        run.loaded += len(batch)
