#!/usr/bin/env python3
"""EveryOrg causes pipeline: land curated cause taxonomy into bronze.bronze_everyorg_causes.

Every.org does not expose a public "list all causes" endpoint, so the canonical
upstream source is the parquet we maintain on HuggingFace:
``CommunityOne/reference-causes-everyorg-causes``. On a fresh checkout this
file is downloaded into ``data/cache/everyorg/`` on first run.

Source-of-truth resolution order:
    1. Explicit ``--file`` argument.
    2. ``data/cache/everyorg/causes.{csv,parquet}`` (operator-managed).
    3. Auto-downloaded HuggingFace parquet (default; disable with --no-download).
    4. Vendored seed YAML — small representative subset, sufficient for smoke
       tests but not the full ~39-cause production taxonomy.

Schema mirrors the columns the legacy parquet carried (cause_id, cause_name,
description, icon, category, parent_id, popularity_rank).

Usage:
    python -m ingestion.everyorg.causes                 # fetch + load
    python -m ingestion.everyorg.causes --truncate
    python -m ingestion.everyorg.causes --no-download   # use cache or vendored
    python -m ingestion.everyorg.causes --file data/cache/everyorg/causes.csv

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
from typing import Any, AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/everyorg")
VENDORED_YAML = Path(__file__).parent / "causes.yaml"

# HuggingFace dataset that mirrors the legacy data/gold/causes_everyorg_causes.parquet.
HF_REPO_ID = "CommunityOne/reference-causes-everyorg-causes"
HF_FILENAME = "causes_everyorg_causes.parquet"


def download_from_hf(cache_dir: Path = CACHE_DIR) -> Path | None:
    """Download the EveryOrg causes parquet from HuggingFace into the cache.

    Returns the local path on success, ``None`` if the download fails (no
    network, missing huggingface_hub, dataset not published, etc.). Failures
    are logged at warning level — the pipeline falls back to the vendored YAML.
    """
    try:
        from huggingface_hub import hf_hub_download  # lazy: optional dep
    except ImportError:
        logger.warning(
            "huggingface_hub not installed; skipping HF download. "
            "Install with `pip install huggingface_hub` or use --no-download."
        )
        return None

    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        downloaded = hf_hub_download(
            repo_id=HF_REPO_ID,
            filename=HF_FILENAME,
            repo_type="dataset",
            local_dir=str(cache_dir),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"HuggingFace download failed ({HF_REPO_ID}): {exc}")
        return None

    # Normalize to the path the resolver looks for.
    target = cache_dir / "causes.parquet"
    src = Path(downloaded)
    if src != target:
        src.replace(target)
    logger.success(f"Downloaded EveryOrg causes → {target}")
    return target


def resolve_source_path(
    explicit: Path | None = None,
    *,
    allow_download: bool = True,
) -> Path:
    """Pick the source file in explicit → cache → HF → vendored YAML order.

    Operators can drop a CSV or parquet at data/cache/everyorg/causes.{csv,parquet}
    to override the upstream. When neither override nor cache is present, the
    canonical HuggingFace parquet is fetched (unless ``allow_download=False``).
    Falls back to the vendored YAML only when everything else fails.
    """
    if explicit is not None:
        return explicit
    for candidate in (CACHE_DIR / "causes.parquet", CACHE_DIR / "causes.csv"):
        if candidate.exists():
            return candidate
    if allow_download:
        downloaded = download_from_hf()
        if downloaded is not None:
            return downloaded
    return VENDORED_YAML


def _safe_str(val: Any, maxlen: int | None = None) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def _safe_int(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _read_rows(path: Path) -> list[dict]:
    """Read raw rows from yaml/csv/parquet at ``path``."""
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        import yaml  # lazy: only needed for vendored taxonomy path

        with path.open("r", encoding="utf-8") as handle:
            doc = yaml.safe_load(handle) or {}
        return list(doc.get("causes", []))
    if suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".parquet":
        # Lazy import: pandas is only needed for the parquet bootstrap path.
        import pandas as pd

        return pd.read_parquet(path).to_dict(orient="records")
    raise ValueError(f"Unsupported EveryOrg source extension: {path.suffix}")


class EveryorgCauseRow(RawRow):
    """One EveryOrg cause, validated before upsert."""

    cause_id: str = Field(min_length=1, max_length=100)
    cause_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=20)
    category: str | None = Field(default=None, max_length=100)
    parent_id: str | None = Field(default=None, max_length=100)
    popularity_rank: int | None = None


# Migration: the legacy NTEE+EveryOrg combined table lived at public.cause_ntee
# with EveryOrg rows discriminated by cause_type='everyorg'. We do NOT auto-move
# those rows here — splitting the combined table is handled in the NTEE
# migration (codes.py). This loader just creates a clean bronze table.
_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_everyorg_causes (
        cause_id         VARCHAR(100) PRIMARY KEY,
        cause_name       VARCHAR(255) NOT NULL,
        description      TEXT,
        icon             VARCHAR(20),
        category         VARCHAR(100),
        parent_id        VARCHAR(100),
        popularity_rank  INTEGER,
        ingestion_date   TIMESTAMP DEFAULT NOW()
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(
        "CREATE INDEX IF NOT EXISTS idx_beoc_category "
        "ON bronze.bronze_everyorg_causes(category)"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_beoc_popularity "
        "ON bronze.bronze_everyorg_causes(popularity_rank)"
    ),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_everyorg_causes")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_everyorg_causes
        (cause_id, cause_name, description, icon, category, parent_id, popularity_rank)
    VALUES
        (:cause_id, :cause_name, :description, :icon, :category, :parent_id, :popularity_rank)
    ON CONFLICT (cause_id) DO UPDATE SET
        cause_name      = EXCLUDED.cause_name,
        description     = EXCLUDED.description,
        icon            = EXCLUDED.icon,
        category        = EXCLUDED.category,
        parent_id       = EXCLUDED.parent_id,
        popularity_rank = EXCLUDED.popularity_rank,
        ingestion_date  = NOW()
    """
)


class EveryorgCausesPipeline(DataSourcePipeline[EveryorgCauseRow]):
    source = "everyorg_causes"
    batch_size = 100
    row_schema = EveryorgCauseRow

    def __init__(
        self,
        *,
        path: Path | None = None,
        limit: int | None = None,
        allow_download: bool = True,
    ):
        self._path = path
        self._limit = limit
        self._allow_download = allow_download

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = resolve_source_path(self._path, allow_download=self._allow_download)
        rows = _read_rows(path)

        emitted = 0
        for row in rows:
            if self._limit is not None and emitted >= self._limit:
                return
            cause_id = _safe_str(row.get("cause_id"), 100)
            if not cause_id:
                continue
            cause_name = _safe_str(row.get("cause_name"), 255)
            if not cause_name:
                continue
            yield {
                "source": self.source,
                "source_version": path.stem,
                "natural_key": cause_id,
                "cause_id": cause_id,
                "cause_name": cause_name,
                "description": _safe_str(row.get("description")),
                "icon": _safe_str(row.get("icon"), 20),
                "category": _safe_str(row.get("category"), 100),
                "parent_id": _safe_str(row.get("parent_id"), 100),
                "popularity_rank": _safe_int(row.get("popularity_rank")),
            }
            emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[EveryorgCauseRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "cause_id": r.cause_id,
                "cause_name": r.cause_name,
                "description": r.description,
                "icon": r.icon,
                "category": r.category,
                "parent_id": r.parent_id,
                "popularity_rank": r.popularity_rank,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load EveryOrg causes into bronze.bronze_everyorg_causes"
    )
    parser.add_argument(
        "--file", type=Path,
        help="Source file (yaml/csv/parquet). Default: cache override or vendored YAML.",
    )
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    parser.add_argument(
        "--no-download", action="store_true",
        help="Skip the HuggingFace download step; use cache or vendored YAML only.",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = EveryorgCausesPipeline(
        path=args.file,
        limit=args.limit,
        allow_download=not args.no_download,
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
