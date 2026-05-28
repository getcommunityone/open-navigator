#!/usr/bin/env python3
"""TPC Government Finance Database pipeline.

The "Government Finance Database" is the Tax Policy Center / Urban Institute's
unified republication of the Census Bureau's Annual Survey of State and Local
Government Finances + Census of Governments, stretching from 1977 onward. TPC
stitches the surveys together and reconciles the variable-name drift across
decades, then ships the result as wide CSVs (one row per government-year, with
~300 finance variables per row).

Catalog pages (human-navigation aids):
  - https://state-local-finance-data.taxpolicycenter.org/
  - https://datacatalog.urban.org/
  - https://my.willamette.edu/site/mba/public-datasets  (mirror w/ direct download)

Canonical bulk file: a Google Drive ZIP, file id
``1FtZQR34S69D2DnOeM_agRTeIVwojbaAK`` by default. The ZIP unpacks into one CSV
per government type (state, county, city, school_district, special_district).
Override the file id with ``--file-id`` if TPC re-publishes under a new id.

Pipeline shape (mirrors ingestion.bls.cpi):
  1. FETCH (``--fetch``): Drive download → ``data/cache/tpc/raw/{id}.zip``,
     auto-unzipped into ``data/cache/tpc/<gov_type>/*.csv``. Skips re-download
     when the zip is already cached unless ``--refresh``.
  2. LAND: stream each CSV row → ``BronzeTpcGovFinanceRow`` → upsert into
     ``bronze.bronze_tpc_government_finance``. Stable hot keys (id, name,
     state, gov_type, fiscal_year, population) are extracted; everything else
     is preserved verbatim in ``raw_record`` JSONB so staging models can
     normalize the wide variable space later without re-loading bronze.

Usage:
    # End-to-end: download + load every government type
    python -m ingestion.tpc.finance --fetch

    # Load from a pre-downloaded cache (operator drops the unzipped CSVs at
    # data/cache/tpc/<gov_type>/...)
    python -m ingestion.tpc.finance

    # Single file (e.g., a different release the operator has)
    python -m ingestion.tpc.finance --file data/cache/tpc/state/state.csv --gov-type state

    # Truncate + reload, with a row cap for smoke testing
    python -m ingestion.tpc.finance --fetch --truncate --limit 1000

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
    ``gdown`` is required for ``--fetch`` (``pip install gdown``). Without it,
    the pipeline prints a clear instruction to download the ZIP manually.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

import zipfile_deflate64 as zipfile
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/tpc")
DEFAULT_DRIVE_FILE_ID = "1FtZQR34S69D2DnOeM_agRTeIVwojbaAK"

# Government type names — also the subdirectory layout under CACHE_DIR.
KNOWN_GOV_TYPES: tuple[str, ...] = (
    "state",
    "county",
    "city",
    "school_district",
    "special_district",
)

# FIELD_MAP — TPC's column names have drifted across releases (`ID4` vs `ID`,
# `Year4` vs `Year` vs `fiscal_year`, etc.). We coalesce by trying each key in
# order; whichever appears in the row first wins.
# GOVSid (Census Government ID) is the canonical identifier in the "Government
# Finance Database" release; FIPSid is its FIPS-derived sibling and the
# fallback for the ~2% of rows where GOVSid is blank. Both must come before the
# older "ID"/"ID4" names so we don't drop every row of a modern bundle.
_ID_KEYS = ("GOVSid", "FIPSid", "ID", "id", "ID4", "id4", "GovID", "Government_ID", "gov_id", "tpc_id")
_NAME_KEYS = ("Name", "NAME", "name", "Name4", "name4", "GovName", "Government_Name")
# FIPS_Code_State carries the zero-padded 2-digit state FIPS ("01") in the
# Government Finance Database. We deliberately do NOT fall back to State_Code:
# that column is the Census GOVS alphabetical state code (AL=1, AK=2, …), which
# diverges from FIPS past Arkansas — treating it as FIPS would write wrong codes.
_STATE_FIPS_KEYS = ("FIPS_Code_State", "State", "STATE", "state", "State4", "state4", "STATEFIPS", "state_fips")
_STATE_POSTAL_KEYS = ("StateAbbrev", "state_postal", "STATE_ABBR", "state_abbr", "StateCode")
_YEAR_KEYS = ("Year", "YEAR", "year", "Year4", "year4", "fiscal_year", "FY")
_POPULATION_KEYS = ("Population", "POPULATION", "population", "Pop", "pop", "Pop4")

# 50 states + DC + territories. Used to back-fill state_code when a CSV gives
# only state_fips (the Census numeric code) or vice-versa.
STATE_FIPS_TO_POSTAL: dict[str, str] = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY",
    "60": "AS", "66": "GU", "69": "MP", "72": "PR", "78": "VI",
}


def _first_match(row: dict, keys: tuple[str, ...]) -> Any:
    """Return the first non-empty value among ``keys`` in ``row``."""
    for k in keys:
        v = row.get(k)
        if v is not None and str(v).strip() != "":
            return v
    return None


def _safe_str(v: Any, maxlen: int | None = 500) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def infer_gov_type(filename: str) -> str:
    """Heuristic mapping of a TPC bundle filename to one of KNOWN_GOV_TYPES.

    Falls back to ``'other'`` so we never crash on an unfamiliar shipment;
    operators can pass ``--gov-type`` explicitly to pin the assignment.
    """
    n = filename.lower()
    if "school" in n:
        return "school_district"
    if "special" in n:
        return "special_district"
    if "city" in n or "municipal" in n:
        return "city"
    if "county" in n:
        return "county"
    if "state" in n:
        return "state"
    return "other"


def fetch_drive_zip(
    file_id: str,
    *,
    cache_dir: Path,
    refresh: bool = False,
) -> Path:
    """Download a Google Drive file by id; cache to ``cache_dir/{file_id}.zip``.

    Uses ``gdown`` to handle Drive's "is this safe?" confirm-token dance for
    files >100MB. ``gdown`` is a lazy import so the pipeline is importable
    (and the cache-only path is runnable) without the optional dep.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{file_id}.zip"
    if out.exists() and not refresh:
        logger.info("TPC drive cache hit: {}", out)
        return out
    try:
        import gdown  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "gdown is not installed (required for --fetch). Install with "
            "`pip install gdown`, or download the file manually from "
            f"https://drive.google.com/file/d/{file_id}/view and drop the "
            f".zip at {out}, then re-run without --fetch."
        ) from e

    logger.info("Downloading TPC bundle from Drive id={} -> {}", file_id, out)
    gdown.download(id=file_id, output=str(out), quiet=False)
    if not out.exists():
        raise RuntimeError(
            f"gdown reported no error but the cache file {out} is missing. "
            f"The Drive link may require sign-in — try opening it in a browser "
            f"and download manually."
        )
    return out


def extract_bundle(zip_path: Path, *, cache_dir: Path) -> dict[str, list[Path]]:
    """Unzip a TPC bundle into ``cache_dir/<gov_type>/<filename>.csv``.

    Files whose names contain none of the known gov-type tokens land in
    ``cache_dir/other/`` so they're still discoverable; operators can rename
    or remove them as needed.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    discovered: dict[str, list[Path]] = {}
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.endswith("/"):
                continue
            basename = Path(member).name
            if not basename:
                continue
            gov_type = infer_gov_type(basename)
            dest_dir = cache_dir / gov_type
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / basename
            with zf.open(member) as src, dest.open("wb") as out_fh:
                out_fh.write(src.read())
            discovered.setdefault(gov_type, []).append(dest)
            logger.info("Extracted -> {} (gov_type={})", dest, gov_type)
    return discovered


def _iter_csv_rows(path: Path) -> Iterable[dict[str, Any]]:
    """Stream rows from ``path`` (csv) one dict per row."""
    with path.open("r", encoding="utf-8", newline="", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            yield row


def row_to_bronze_dict(
    row: dict[str, Any], *, gov_type: str, source_file: str
) -> dict[str, Any] | None:
    """Translate one wide CSV row into the bronze upsert dict.

    Returns ``None`` if the essential keys (id, year) are missing or
    un-parseable — those rows are skipped with a debug log rather than
    failing the whole batch, because TPC bundles occasionally include
    summary/total rows that legitimately have no id_code.
    """
    id_code_raw = _first_match(row, _ID_KEYS)
    year_raw = _first_match(row, _YEAR_KEYS)
    if not id_code_raw or not year_raw:
        return None
    try:
        # Validate it's a real (numeric) year, but carry it as a 4-char string
        # to match the VARCHAR(4) bronze column.
        fiscal_year = str(int(str(year_raw).strip()))
    except (TypeError, ValueError):
        return None
    if len(fiscal_year) != 4:
        return None

    state_fips: str | None = None
    s_raw = _first_match(row, _STATE_FIPS_KEYS)
    if s_raw is not None:
        s = str(s_raw).strip()
        if s.isdigit():
            state_fips = s.zfill(2)

    state_code: str | None = None
    p_raw = _first_match(row, _STATE_POSTAL_KEYS)
    if p_raw is not None:
        s = str(p_raw).strip().upper()
        if len(s) == 2 and s.isalpha():
            state_code = s
    if state_code is None and state_fips is not None:
        state_code = STATE_FIPS_TO_POSTAL.get(state_fips)

    population: int | None = None
    pop_raw = _first_match(row, _POPULATION_KEYS)
    if pop_raw not in (None, ""):
        try:
            population = int(float(str(pop_raw)))
        except (TypeError, ValueError):
            population = None

    id_code = str(id_code_raw).strip()[:64]
    return {
        "source": "tpc_government_finance",
        "source_version": source_file,
        "natural_key": f"{gov_type}:{id_code}:{fiscal_year}",
        "id_code": id_code,
        "name": _safe_str(_first_match(row, _NAME_KEYS)),
        "state_fips": state_fips,
        "state_code": state_code,
        "gov_type": gov_type,
        "fiscal_year": fiscal_year,
        "population": population,
        # raw_record carries the full row verbatim, including the columns we
        # extracted. Bronze is "raw with a few hot keys hoisted for indexing";
        # downstream staging models can normalize without re-loading.
        "raw_record": dict(row),
        "source_file": source_file,
    }


class TpcGovernmentFinanceRow(RawRow):
    """One TPC government-year observation."""

    id_code: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=500)
    state_fips: str | None = Field(default=None, max_length=2)
    state_code: str | None = Field(default=None, max_length=2)
    gov_type: str = Field(min_length=1, max_length=32)
    fiscal_year: str = Field(min_length=1, max_length=4)
    population: int | None = None
    raw_record: dict
    source_file: str = Field(min_length=1, max_length=255)


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

# Idempotent — matches migration 078 exactly. Re-running is a no-op against a
# DB that already applied the migration.
_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_tpc_government_finance (
        id_code        VARCHAR(64)   NOT NULL,
        name           TEXT,
        state_fips     CHAR(2),
        state_code     CHAR(2),
        gov_type       VARCHAR(32)   NOT NULL,
        fiscal_year    VARCHAR(4)    NOT NULL,
        population     BIGINT,
        raw_record     JSONB         NOT NULL,
        source_file    TEXT          NOT NULL,
        loaded_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
        last_updated   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
        PRIMARY KEY (gov_type, id_code, fiscal_year)
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(
        "CREATE INDEX IF NOT EXISTS idx_btpc_state_gov "
        "ON bronze.bronze_tpc_government_finance (state_fips, gov_type)"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_btpc_year "
        "ON bronze.bronze_tpc_government_finance (fiscal_year)"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_btpc_state_code "
        "ON bronze.bronze_tpc_government_finance (state_code) "
        "WHERE state_code IS NOT NULL"
    ),
)

# The UPSERT below relies on the (gov_type, id_code, fiscal_year) primary key as
# its ON CONFLICT arbiter. Migration 078 creates that PK, but the bronze
# passthrough dbt model (materialized='table', same relation) rebuilds the table
# via CTAS on every `dbt run`, which silently drops the PK (and indexes). The
# CREATE INDEX statements above are already self-healing; the PK is not, because
# it lives inside CREATE TABLE IF NOT EXISTS, which no-ops once the table exists.
# So re-establish it idempotently here — Postgres has no ADD CONSTRAINT IF NOT
# EXISTS, hence the pg_constraint guard.
_ENSURE_PK_SQL = text(
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'bronze.bronze_tpc_government_finance'::regclass
              AND contype = 'p'
        ) THEN
            ALTER TABLE bronze.bronze_tpc_government_finance
                ADD PRIMARY KEY (gov_type, id_code, fiscal_year);
        END IF;
    END $$;
    """
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_tpc_government_finance")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_tpc_government_finance
        (id_code, name, state_fips, state_code, gov_type, fiscal_year,
         population, raw_record, source_file, loaded_at, last_updated)
    VALUES
        (:id_code, :name, :state_fips, :state_code, :gov_type, :fiscal_year,
         :population, CAST(:raw_record AS JSONB), :source_file, NOW(), NOW())
    ON CONFLICT (gov_type, id_code, fiscal_year) DO UPDATE SET
        name         = EXCLUDED.name,
        state_fips   = EXCLUDED.state_fips,
        state_code   = EXCLUDED.state_code,
        population   = EXCLUDED.population,
        raw_record   = EXCLUDED.raw_record,
        source_file  = EXCLUDED.source_file,
        last_updated = NOW()
    """
)


class TpcGovernmentFinancePipeline(DataSourcePipeline[TpcGovernmentFinanceRow]):
    source = "tpc_government_finance"
    batch_size = 500
    row_schema = TpcGovernmentFinanceRow

    def __init__(
        self,
        *,
        file: Path | None = None,
        gov_type: str | None = None,
        cache_dir: Path = CACHE_DIR,
        file_id: str = DEFAULT_DRIVE_FILE_ID,
        fetch: bool = False,
        refresh: bool = False,
        limit: int | None = None,
    ):
        self._file = file
        self._gov_type = gov_type
        self._cache_dir = cache_dir
        self._file_id = file_id
        self._fetch = fetch
        self._refresh = refresh
        self._limit = limit

    def _resolve_files(self) -> list[tuple[str, Path]]:
        """Return ``[(gov_type, csv_path), ...]`` for the run."""
        if self._file is not None:
            gov_type = self._gov_type or infer_gov_type(self._file.name)
            return [(gov_type, self._file)]

        if self._fetch:
            zip_path = fetch_drive_zip(
                self._file_id,
                cache_dir=self._cache_dir / "raw",
                refresh=self._refresh,
            )
            extract_bundle(zip_path, cache_dir=self._cache_dir)

        out: list[tuple[str, Path]] = []
        gov_types: tuple[str, ...] = (
            (self._gov_type,) if self._gov_type else KNOWN_GOV_TYPES + ("other",)
        )
        for gov_type in gov_types:
            subdir = self._cache_dir / gov_type
            if subdir.exists():
                for csv_path in sorted(subdir.glob("*.csv")):
                    out.append((gov_type, csv_path))

        if not out:
            raise FileNotFoundError(
                f"No TPC CSVs found under {self._cache_dir}. Either pass "
                f"--fetch to download the bundle "
                f"(file_id={self._file_id}), or place the unzipped CSVs "
                f"at {self._cache_dir}/<gov_type>/."
            )
        return out

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        files = self._resolve_files()
        emitted = 0
        for gov_type, csv_path in files:
            logger.info(
                "TPC LAND: gov_type={} file={} (emitted_so_far={})",
                gov_type, csv_path, emitted,
            )
            for row in _iter_csv_rows(csv_path):
                if self._limit is not None and emitted >= self._limit:
                    return
                d = row_to_bronze_dict(
                    row, gov_type=gov_type, source_file=csv_path.name
                )
                if d is None:
                    continue
                yield d
                emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[TpcGovernmentFinanceRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "id_code": r.id_code,
                "name": r.name,
                "state_fips": r.state_fips,
                "state_code": r.state_code,
                "gov_type": r.gov_type,
                "fiscal_year": r.fiscal_year,
                "population": r.population,
                "raw_record": json.dumps(r.raw_record),
                "source_file": r.source_file,
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
        await session.execute(_ENSURE_PK_SQL)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Load TPC Government Finance data into "
            "bronze.bronze_tpc_government_finance"
        )
    )
    parser.add_argument(
        "--file",
        type=Path,
        help=(
            "Single CSV file path. If omitted, the pipeline scans "
            "data/cache/tpc/<gov_type>/*.csv subdirs."
        ),
    )
    parser.add_argument(
        "--gov-type",
        choices=KNOWN_GOV_TYPES + ("other",),
        help=(
            "Government type. With --file, overrides filename inference. "
            "Without --file, restricts the scan to that subdir."
        ),
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help=(
            "Download the bundle from Google Drive (requires `pip install "
            "gdown`) and unzip into data/cache/tpc/."
        ),
    )
    parser.add_argument(
        "--file-id",
        default=DEFAULT_DRIVE_FILE_ID,
        help="Google Drive file id for --fetch (default: %(default)s).",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-download even if a cached zip exists.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads).",
    )
    parser.add_argument("--limit", type=int, help="Limit records (for testing).")
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = TpcGovernmentFinancePipeline(
        file=args.file,
        gov_type=args.gov_type,
        file_id=args.file_id,
        fetch=args.fetch,
        refresh=args.refresh,
        limit=args.limit,
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
