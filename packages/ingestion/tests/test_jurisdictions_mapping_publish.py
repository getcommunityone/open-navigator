"""Unit tests for ingestion.jurisdictions.columns, ingestion.jurisdictions.mapping.publish_hf, and legacy script path reconciliation."""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from ingestion.jurisdictions import (
    DETAILS_TO_JURISDICTION,
    JURISDICTION_TABLE,
    map_legacy_jurisdiction_column,
)
from ingestion.jurisdictions.mapping import publish_hf
from scripts.datasources.jurisdictions import (
    public_jurisdiction_columns,
    publish_jurisdiction_mapping_analysis_to_hf,
)


def test_jurisdiction_columns_and_legacy_shim():
    assert JURISDICTION_TABLE == "jurisdiction"
    assert public_jurisdiction_columns.JURISDICTION_TABLE == "jurisdiction"
    assert public_jurisdiction_columns.DETAILS_TO_JURISDICTION is DETAILS_TO_JURISDICTION
    assert map_legacy_jurisdiction_column("jurisdiction_name") == "name"
    assert map_legacy_jurisdiction_column("jurisdiction_type") == "type"
    assert map_legacy_jurisdiction_column("status") == "discovery_status"
    assert map_legacy_jurisdiction_column("state_code") == "state_code"


def test_publish_hf_db_url_and_default_repo_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(publish_hf, "load_dotenv", lambda *args, **kwargs: False)
    for k in (
        "OPEN_NAVIGATOR_DATABASE_URL",
        "NEON_DATABASE_URL_DEV",
        "NEON_DATABASE_URL",
        "DATABASE_URL",
    ):
        monkeypatch.delenv(k, raising=False)

    assert publish_hf._db_url() == "postgresql://postgres:password@localhost:5433/open_navigator"

    monkeypatch.setenv("NEON_DATABASE_URL", "postgres://neon:pass@neon.example.com:5432/db")
    assert publish_hf._db_url() == "postgresql://neon:pass@neon.example.com:5432/db"

    monkeypatch.setenv("HF_ORGANIZATION", "CommunityOne")
    monkeypatch.setenv("HF_DATASET_PREFIX", "one")
    monkeypatch.setenv("HF_JURISDICTION_MAPPING_ANALYSIS_DATASET", "jurisdiction-mapping-analysis")
    assert publish_hf._default_repo_id() == "CommunityOne/one-jurisdiction-mapping-analysis"


def test_fetch_dataframe_coerces_decimals_and_timestamps(monkeypatch: pytest.MonkeyPatch):
    class _FakeCursor:
        def execute(self, sql: str) -> None:
            assert publish_hf.TABLE in sql

        def fetchall(self) -> list[dict[str, Any]]:
            return [
                {
                    "jurisdiction_id": "county_01125",
                    "name": "Tuscaloosa County",
                    "state_code": "AL",
                    "n_website_candidate_rows": Decimal("3"),
                    "score": Decimal("0.925"),
                    "updated_at": datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
                }
            ]

        def __enter__(self) -> "_FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class _FakeConn:
        def cursor(self, cursor_factory=None) -> _FakeCursor:
            return _FakeCursor()

        def close(self) -> None:
            return None

    monkeypatch.setattr(publish_hf.psycopg2, "connect", lambda url: _FakeConn())
    df = publish_hf._fetch_dataframe()
    assert len(df) == 1
    assert df.loc[0, "jurisdiction_id"] == "county_01125"
    assert int(df.loc[0, "n_website_candidate_rows"]) == 3
    assert float(df.loc[0, "score"]) == pytest.approx(0.925)


def test_publish_hf_parquet_only_cli_and_shim(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    sample_df = pd.DataFrame(
        [
            {
                "jurisdiction_id": "city_2507000",
                "name": "Boston",
                "state_code": "MA",
                "jurisdiction_type": "city",
            }
        ]
    )
    monkeypatch.setattr(publish_hf, "_fetch_dataframe", lambda: sample_df)
    monkeypatch.setattr(publish_hf, "load_dotenv", lambda *args, **kwargs: False)

    rc = publish_jurisdiction_mapping_analysis_to_hf.main(
        ["--parquet-only", "--parquet-dir", str(tmp_path)]
    )
    assert rc == 0
    out_file = tmp_path / "jurisdiction_mapping_analysis.parquet"
    assert out_file.exists()
    loaded = pd.read_parquet(out_file)
    assert len(loaded) == 1
    assert loaded.loc[0, "jurisdiction_id"] == "city_2507000"


def test_reconciled_runner_scripts_reference_canonical_modules():
    root = publish_hf.ROOT

    localview_sh = (root / "scripts" / "datasources" / "localview" / "load_priority_states.sh").read_text(
        encoding="utf-8"
    )
    assert "localview_ingestion.py" not in localview_sh
    assert "scripts/localview/check_meeting_data.py" not in localview_sh
    assert "python -m ingestion.localview.events" in localview_sh
    assert "scripts/datasources/localview/check_meeting_data.py" in localview_sh

    check_py = (root / "scripts" / "datasources" / "localview" / "check_meeting_data.py").read_text(
        encoding="utf-8"
    )
    assert "localview_ingestion.py" not in check_py
    assert "python -m ingestion.localview.events" in check_py

    openstates_sh = (
        root / "packages" / "scrapers" / "scripts" / "openstates_parallel_download.sh"
    ).read_text(encoding="utf-8")
    assert "/home/developer/projects/open-navigator" not in openstates_sh
    assert "scripts/datasources/openstates/download_documents.py" not in openstates_sh
    assert "python -m scrapers.openstates.load_openstates_documents" in openstates_sh
    assert "scrapers.openstates.download_documents" not in openstates_sh
    # The module the runner calls must actually exist.
    assert importlib.util.find_spec("scrapers.openstates.load_openstates_documents") is not None

    locations_py = (root / "api" / "routes" / "locations.py").read_text(encoding="utf-8")
    assert "load_hifld_to_postgres.py" not in locations_py
    assert "python -m ingestion.hifld.locations" in locations_py
