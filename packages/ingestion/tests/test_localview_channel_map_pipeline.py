"""Offline unit tests for ingestion.localview.channel_map and runner entrypoint paths."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pandas as pd
import pytest

import ingestion.localview.channel_map as _cm_module
from core_lib.pipeline.schemas import PipelineContext
from ingestion.localview.channel_map import (
    LocalviewVideoChannelRow,
    LocalviewVideoChannelsPipeline,
    build_parser,
    extract_parquet_mappings,
    find_parquet_files,
)


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="test-channel-map", started_at=datetime.now(timezone.utc))


def _write_parquet(path: Path, records: list[dict[str, Any]]) -> Path:
    pd.DataFrame(records).to_parquet(path)
    return path


class TestFindParquetFiles:
    def test_raises_when_directory_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_cm_module, "CACHE_DIR", tmp_path)
        with pytest.raises(FileNotFoundError):
            find_parquet_files()

    def test_returns_sorted_parquet_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_cm_module, "CACHE_DIR", tmp_path)
        for yr in (2024, 2022, 2023):
            (tmp_path / f"meetings.{yr}.parquet").write_text("")
        files = find_parquet_files()
        assert [f.name for f in files] == [
            "meetings.2022.parquet",
            "meetings.2023.parquet",
            "meetings.2024.parquet",
        ]


class TestExtractParquetMappings:
    def test_extracts_valid_rows_and_filters_invalid(self, tmp_path: Path) -> None:
        p = _write_parquet(
            tmp_path / "meetings.2023.parquet",
            [
                {
                    "vid_id": "  vid_valid_1  ",
                    "channel_id": "  UC_chan_1  ",
                    "channel_title": "City Council TV",
                },
                {
                    "vid_id": None,
                    "channel_id": "UC_chan_2",
                    "channel_title": "Missing Vid",
                },
                {
                    "vid_id": "vid_missing_chan",
                    "channel_id": float("nan"),
                    "channel_title": "Missing Chan",
                },
                {
                    "vid_id": "   ",
                    "channel_id": "UC_chan_3",
                    "channel_title": "Blank Vid",
                },
                {
                    "vid_id": "vid_blank_chan",
                    "channel_id": "   ",
                    "channel_title": "Blank Chan",
                },
            ],
        )
        rows = extract_parquet_mappings(files=[p])
        assert len(rows) == 1
        row = rows[0]
        assert row["video_id"] == "vid_valid_1"
        assert row["channel_id"] == "UC_chan_1"
        assert row["channel_title"] == "City Council TV"
        assert row["youtube_url"] == "https://www.youtube.com/watch?v=vid_valid_1"
        assert row["source_version"] == "meetings.2023"

    def test_deduplicates_by_vid_id_and_backfills_missing_title(
        self, tmp_path: Path
    ) -> None:
        p1 = _write_parquet(
            tmp_path / "meetings.2022.parquet",
            [
                {
                    "vid_id": "vid_dup",
                    "channel_id": "UC_first",
                    "channel_title": None,
                },
            ],
        )
        p2 = _write_parquet(
            tmp_path / "meetings.2023.parquet",
            [
                {
                    "vid_id": "vid_dup",
                    "channel_id": "UC_second",
                    "channel_title": "Backfilled Channel Title",
                },
            ],
        )
        rows = extract_parquet_mappings(files=[p1, p2])
        assert len(rows) == 1
        assert rows[0]["video_id"] == "vid_dup"
        assert rows[0]["channel_id"] == "UC_first"
        assert rows[0]["channel_title"] == "Backfilled Channel Title"

    def test_truncates_channel_title_at_500_chars(self, tmp_path: Path) -> None:
        p = _write_parquet(
            tmp_path / "meetings.2023.parquet",
            [
                {
                    "vid_id": "vid_long_title",
                    "channel_id": "UC_long",
                    "channel_title": "T" * 650,
                }
            ],
        )
        rows = extract_parquet_mappings(files=[p])
        assert len(rows) == 1
        assert len(rows[0]["channel_title"]) == 500

    def test_respects_limit_across_files(self, tmp_path: Path) -> None:
        p1 = _write_parquet(
            tmp_path / "meetings.2022.parquet",
            [
                {"vid_id": f"v1_{i}", "channel_id": f"UC_{i}", "channel_title": "TV"}
                for i in range(3)
            ],
        )
        p2 = _write_parquet(
            tmp_path / "meetings.2023.parquet",
            [
                {"vid_id": f"v2_{i}", "channel_id": f"UC_{i}", "channel_title": "TV"}
                for i in range(3)
            ],
        )
        rows = extract_parquet_mappings(limit=4, files=[p1, p2])
        assert len(rows) == 4
        assert [r["video_id"] for r in rows] == ["v1_0", "v1_1", "v1_2", "v2_0"]

    def test_skips_parquet_missing_required_columns(self, tmp_path: Path) -> None:
        p = _write_parquet(
            tmp_path / "meetings.bad.parquet",
            [{"some_other_col": "val"}],
        )
        rows = extract_parquet_mappings(files=[p])
        assert rows == []


class TestLocalviewVideoChannelRowSchema:
    def test_accepts_valid_row(self) -> None:
        r = LocalviewVideoChannelRow(
            source="localview_video_channels",
            source_version="meetings.2023",
            natural_key="vid123",
            video_id="vid123",
            youtube_url="https://www.youtube.com/watch?v=vid123",
            channel_id="UC123",
            channel_title="Channel 123",
        )
        assert r.video_id == "vid123"
        assert r.channel_id == "UC123"

    def test_rejects_empty_video_id_or_channel_id(self) -> None:
        with pytest.raises(Exception):
            LocalviewVideoChannelRow(
                source="localview_video_channels",
                source_version="v",
                natural_key="x",
                video_id="",
                channel_id="UC123",
            )
        with pytest.raises(Exception):
            LocalviewVideoChannelRow(
                source="localview_video_channels",
                source_version="v",
                natural_key="x",
                video_id="vid123",
                channel_id="",
            )


class TestLocalviewVideoChannelsPipeline:
    def test_pipeline_metadata(self) -> None:
        p = LocalviewVideoChannelsPipeline()
        assert p.source == "localview_video_channels"
        assert p.batch_size == 500
        assert p.row_schema is LocalviewVideoChannelRow

    def test_extract_and_validate_roundtrip(self, tmp_path: Path) -> None:
        path = _write_parquet(
            tmp_path / "meetings.2023.parquet",
            [
                {
                    "vid_id": "vid_abc",
                    "channel_id": "UC_xyz",
                    "channel_title": "Metro Gov TV",
                }
            ],
        )
        p = LocalviewVideoChannelsPipeline(path=path)

        async def collect():
            return [r async for r in p.extract(_ctx())]

        extracted = asyncio.run(collect())
        assert len(extracted) == 1
        validated = p.validate(extracted[0])
        assert validated is not None
        assert validated.video_id == "vid_abc"
        assert validated.channel_id == "UC_xyz"

    def test_load_batch_dry_run_skips_session_execute(self) -> None:
        p = LocalviewVideoChannelsPipeline(dry_run=True)
        session = AsyncMock()
        row = LocalviewVideoChannelRow(
            source="localview_video_channels",
            source_version="meetings.2023",
            natural_key="vid_abc",
            video_id="vid_abc",
            youtube_url="https://www.youtube.com/watch?v=vid_abc",
            channel_id="UC_xyz",
            channel_title="Metro Gov TV",
        )
        asyncio.run(p.load_batch(session, [row], _ctx()))
        session.execute.assert_not_called()

    def test_load_batch_executes_upsert(self) -> None:
        p = LocalviewVideoChannelsPipeline(dry_run=False)
        session = AsyncMock()
        row = LocalviewVideoChannelRow(
            source="localview_video_channels",
            source_version="meetings.2023",
            natural_key="vid_abc",
            video_id="vid_abc",
            youtube_url="https://www.youtube.com/watch?v=vid_abc",
            channel_id="UC_xyz",
            channel_title="Metro Gov TV",
        )
        asyncio.run(p.load_batch(session, [row], _ctx()))
        session.execute.assert_called_once()
        args, _ = session.execute.call_args
        params = args[1]
        assert len(params) == 1
        assert params[0]["video_id"] == "vid_abc"
        assert params[0]["channel_id"] == "UC_xyz"
        assert isinstance(params[0]["fetched_at"], datetime)


class TestLegacyShimAndMasterRunners:
    def test_backfill_shim_reexports_pipeline_symbols(self) -> None:
        import scripts.datasources.localview.backfill_localview_youtube_channel_map as shim

        assert shim.LocalviewVideoChannelRow is LocalviewVideoChannelRow
        assert shim.LocalviewVideoChannelsPipeline is LocalviewVideoChannelsPipeline
        assert shim.extract_parquet_mappings is extract_parquet_mappings
        assert shim.find_parquet_files is find_parquet_files
        assert shim.build_parser is build_parser

    def test_master_runners_reference_existing_scripts(self) -> None:
        import scripts.download_bronze as dl_bronze
        import scripts.load_bronze as ld_bronze

        repo_root = Path(ld_bronze.PROJECT_ROOT)
        for loader in ld_bronze.LOADERS:
            script_path = repo_root / loader["script"]
            assert script_path.is_file(), (
                f"load_bronze loader '{loader['key']}' references missing script: {loader['script']}"
            )
        for downloader in dl_bronze.DOWNLOADERS:
            script_path = repo_root / downloader["script"]
            assert script_path.is_file(), (
                f"download_bronze downloader '{downloader['key']}' references missing script: {downloader['script']}"
            )
