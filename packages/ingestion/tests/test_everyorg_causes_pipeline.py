"""Unit tests for the EveryOrg causes pipeline (bronze.bronze_everyorg_causes)."""
from __future__ import annotations

import asyncio
import csv
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest


from ingestion.everyorg.causes import (  # noqa: E402
    EveryorgCauseRow,
    EveryorgCausesPipeline,
    VENDORED_YAML,
    _safe_int,
    _safe_str,
    resolve_source_path,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _write_csv(path: Path, rows: list[dict]) -> Path:
    if not rows:
        path.write_text(
            "cause_id,cause_name,description,icon,category,parent_id,popularity_rank\n"
        )
        return path
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if v is None else v) for k, v in row.items()})
    return path


def test_safe_str_trims_and_truncates():
    assert _safe_str("  hello  ") == "hello"
    assert _safe_str("") is None
    assert _safe_str("   ") is None
    assert _safe_str(None) is None
    assert _safe_str("abcdef", 3) == "abc"


def test_safe_int_coerces_and_rejects_garbage():
    assert _safe_int(1) == 1
    assert _safe_int("42") == 42
    assert _safe_int(None) is None
    assert _safe_int("") is None
    assert _safe_int("not-a-number") is None


def test_row_schema_enforces_constraints():
    row = EveryorgCauseRow(
        source="everyorg_causes",
        source_version="causes",
        natural_key="animals",
        cause_id="animals",
        cause_name="Animals",
        description="protecting animals",
        icon="🐾",
        category="animals",
        parent_id=None,
        popularity_rank=1,
    )
    assert row.cause_id == "animals"
    assert row.popularity_rank == 1

    # cause_id required (min_length=1)
    with pytest.raises(Exception):
        EveryorgCauseRow(
            source="everyorg_causes",
            source_version="v",
            natural_key="x",
            cause_id="",
            cause_name="Animals",
        )
    # cause_name required (min_length=1)
    with pytest.raises(Exception):
        EveryorgCauseRow(
            source="everyorg_causes",
            source_version="v",
            natural_key="animals",
            cause_id="animals",
            cause_name="",
        )
    # cause_id capped at 100
    with pytest.raises(Exception):
        EveryorgCauseRow(
            source="everyorg_causes",
            source_version="v",
            natural_key="x",
            cause_id="x" * 101,
            cause_name="X",
        )


def test_pipeline_metadata():
    p = EveryorgCausesPipeline()
    assert p.source == "everyorg_causes"
    assert p.batch_size == 100
    assert p.row_schema is EveryorgCauseRow


def test_resolve_source_path_explicit_wins(tmp_path):
    explicit = tmp_path / "explicit.yaml"
    explicit.write_text("causes: []\n")
    assert resolve_source_path(explicit) == explicit


def test_resolve_source_path_cache_dir_preferred(tmp_path, monkeypatch):
    import ingestion.everyorg.causes as cp

    monkeypatch.setattr(cp, "CACHE_DIR", tmp_path)
    csv_path = tmp_path / "causes.csv"
    csv_path.write_text("cause_id,cause_name\nanimals,Animals\n")
    assert resolve_source_path() == csv_path


def test_resolve_source_path_falls_back_to_vendored(tmp_path, monkeypatch):
    import ingestion.everyorg.causes as cp

    monkeypatch.setattr(cp, "CACHE_DIR", tmp_path)
    assert resolve_source_path() == VENDORED_YAML


def test_resolve_source_path_prefers_parquet_over_csv(tmp_path, monkeypatch):
    import ingestion.everyorg.causes as cp

    monkeypatch.setattr(cp, "CACHE_DIR", tmp_path)
    (tmp_path / "causes.csv").write_text("cause_id,cause_name\nanimals,Animals\n")
    parquet = tmp_path / "causes.parquet"
    pd.DataFrame([{"cause_id": "animals", "cause_name": "Animals"}]).to_parquet(parquet)
    assert resolve_source_path() == parquet


def test_extract_from_csv_yields_validated_rows(tmp_path):
    path = _write_csv(
        tmp_path / "causes.csv",
        [
            {
                "cause_id": "animals", "cause_name": "Animals",
                "description": "protecting animals", "icon": "🐾",
                "category": "animals", "parent_id": "", "popularity_rank": "1",
            },
            {
                "cause_id": "mental-health", "cause_name": "Mental Health",
                "description": "wellbeing", "icon": "🧠",
                "category": "health", "parent_id": "health", "popularity_rank": "12",
            },
            {
                "cause_id": "", "cause_name": "junk",  # dropped — empty natural key
                "description": "", "icon": "", "category": "", "parent_id": "",
                "popularity_rank": "",
            },
        ],
    )
    p = EveryorgCausesPipeline(path=path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    assert extracted[0]["cause_id"] == "animals"
    assert extracted[0]["popularity_rank"] == 1
    assert extracted[0]["parent_id"] is None
    assert extracted[1]["parent_id"] == "health"
    assert extracted[1]["natural_key"] == "mental-health"

    for raw in extracted:
        assert p.validate(raw) is not None


def test_extract_vendored_yaml_is_loadable():
    """The package-vendored YAML must be parseable and validate cleanly."""
    p = EveryorgCausesPipeline(path=VENDORED_YAML)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    # Seed ships a representative subset.
    assert len(extracted) >= 10
    cause_ids = {row["cause_id"] for row in extracted}
    assert "animals" in cause_ids
    assert "health" in cause_ids
    for raw in extracted:
        assert p.validate(raw) is not None


def test_extract_from_parquet_yields_validated_rows(tmp_path):
    path = tmp_path / "causes.parquet"
    pd.DataFrame(
        [
            {
                "cause_id": "climate", "cause_name": "Climate",
                "description": "addressing climate change", "icon": "🌍",
                "category": "environment", "parent_id": None, "popularity_rank": 3,
            }
        ]
    ).to_parquet(path)

    p = EveryorgCausesPipeline(path=path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 1
    assert extracted[0]["cause_id"] == "climate"
    assert extracted[0]["parent_id"] is None


def test_limit_caps_extracted_rows(tmp_path):
    rows = [
        {
            "cause_id": f"cause-{i}", "cause_name": f"C{i}",
            "description": "", "icon": "", "category": "", "parent_id": "",
            "popularity_rank": str(i),
        }
        for i in range(10)
    ]
    path = _write_csv(tmp_path / "causes.csv", rows)
    p = EveryorgCausesPipeline(path=path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3
