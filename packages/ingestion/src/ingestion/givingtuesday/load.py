#!/usr/bin/env python3
"""Load cached GivingTuesday 990 datamart CSVs into bronze.

Companion to ``ingestion.givingtuesday.download`` (which lands the curated
datamart CSVs in ``data/cache/giving_tuesday/``). This loads the two datamarts
that feed the nonprofit lineage:

    financials  ->  bronze.bronze_organizations_990_financials
                    (990CN120Fields: total revenue/expenses/assets, etc.)
    missions    ->  bronze.bronze_organizations_990_missions
                    (990Part1Missions: Part 1 mission statement text)
    schedule_i  ->  bronze.bronze_grants_gt990_schedule_i
                    (ScheduleIPart2Grants: grantmaking — grantor org -> grantee
                    org, cash amount, purpose; feeds the `grant` mart)

The financials/missions datamarts hold one row per filing (i.e. multiple tax
years per EIN); their bronze tables preserve that grain with
``UNIQUE(ein, tax_year)`` and downstream dbt staging (``stg_givingtuesday__*``)
picks the latest filing per EIN before joining into ``int_nonprofits_combined``.
The officers / schedule_j / schedule_i datamarts are line-item child tables with
no natural unique key — they are append-only INSERTs and must be loaded with
``--truncate`` for a clean reload.

The source CSVs are large (financials ~1.6 GB, missions ~1.1 GB), so rows are
read in chunks with only the needed columns projected, then batched-upserted via
the standard ``DataSourcePipeline`` contract.

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.

Usage:
    # 1. download first (see ingestion.givingtuesday.download)
    python -m ingestion.givingtuesday.download --match 990CN120Fields,Missions

    # 2. load into bronze
    python -m ingestion.givingtuesday.load --datamart all
    python -m ingestion.givingtuesday.load --datamart financials --truncate
    python -m ingestion.givingtuesday.load --datamart missions --file <path.csv> --limit 1000
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import AsyncIterator

import pandas as pd
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/giving_tuesday")
_CHUNK_ROWS = 100_000

# RawRow envelope fields that are not columns on the bronze tables.
_BASE_FIELDS = {"source", "source_version", "ingested_at", "natural_key"}


# --------------------------------------------------------------------------- #
# helpers (mirror ingestion.irs.bmf)
# --------------------------------------------------------------------------- #
def _safe_str(val: object, maxlen: int | None = None) -> str | None:
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def _safe_int(val: object) -> int | None:
    if val is None:
        return None
    num = pd.to_numeric(val, errors="coerce")
    if pd.isna(num):
        return None
    return int(num)


def _safe_num(val: object) -> float | None:
    """Convert a decimal cell (e.g. average hours '40.00') to a nullable float."""
    if val is None:
        return None
    num = pd.to_numeric(val, errors="coerce")
    if pd.isna(num):
        return None
    return float(num)


def _safe_bool(val: object) -> bool:
    """Form 990 'X'/blank checkbox -> bool (any non-empty value is True)."""
    return _safe_str(val) is not None


def _ein(val: object) -> str | None:
    """Normalize EIN to 9 digits with leading zeros."""
    s = _safe_str(val)
    if s is None:
        return None
    s = s.replace("-", "")
    return s.zfill(9) if s.isdigit() else s


def _latest_cached(substr: str) -> Path:
    """Find the most recent cached datamart CSV whose name contains ``substr``."""
    files = sorted(CACHE_DIR.glob(f"*{substr}*.csv"), reverse=True)
    if not files:
        raise FileNotFoundError(
            f"No cached datamart matching '*{substr}*.csv' in {CACHE_DIR}. "
            f"Download first: python -m ingestion.givingtuesday.download --match {substr}"
        )
    return files[0]


# A full (non-limited) load must capture essentially the entire source file.
# Below this fraction we treat the result as a partial load and fail loudly —
# this is the guard that catches a silent under-load (e.g. a stray --limit that
# once left bronze_organizations_990_officers at 2.75M of 40.1M source rows).
_COMPLETENESS_THRESHOLD = 0.95
_COUNT_BUF = 1024 * 1024  # 1 MiB byte scan window for row counting


def _count_source_rows(path: Path) -> int:
    """Fast data-row count for a datamart CSV (newline count minus the header).

    Uses a buffered byte scan rather than a full CSV parse: it is exact enough to
    detect gross under-loads (the failure mode being guarded against). Quoted
    embedded newlines could in theory inflate the count by a negligible amount,
    so this is treated as an upper bound against a generous threshold.
    """
    with path.open("rb") as fh:
        newlines = sum(buf.count(b"\n") for buf in iter(lambda: fh.read(_COUNT_BUF), b""))
    return max(newlines - 1, 0)  # subtract the header row


def _read_chunks(path: Path, columns: list[str]) -> AsyncIterator[dict]:
    """Yield row dicts from ``path``, projecting only the needed source columns."""
    header = pd.read_csv(path, dtype=str, nrows=0)
    present = [c for c in columns if c in header.columns]
    missing = set(columns) - set(present)
    if missing:
        raise ValueError(f"{path.name} missing expected columns: {sorted(missing)}")
    return pd.read_csv(path, dtype=str, usecols=present, chunksize=_CHUNK_ROWS)


# --------------------------------------------------------------------------- #
# financials datamart (990CN120Fields)
# --------------------------------------------------------------------------- #
class Form990FinancialsRow(RawRow):
    ein: str = Field(min_length=1, max_length=20)
    tax_year: int | None = None
    name: str | None = None
    state_code: str | None = Field(default=None, max_length=2)
    total_revenue: int | None = None
    total_expenses: int | None = None
    total_assets: int | None = None
    total_liabilities: int | None = None
    net_assets: int | None = None
    total_contributions: int | None = None
    program_service_revenue: int | None = None
    source_url: str | None = None


_FIN_DDL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_organizations_990_financials (
        id SERIAL PRIMARY KEY,
        ein VARCHAR(20) NOT NULL,
        tax_year INTEGER,
        name TEXT,
        state_code VARCHAR(2),
        total_revenue BIGINT,
        total_expenses BIGINT,
        total_assets BIGINT,
        total_liabilities BIGINT,
        net_assets BIGINT,
        total_contributions BIGINT,
        program_service_revenue BIGINT,
        source_url TEXT,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ein, tax_year)
    )
    """
)
_FIN_INDEXES = (
    text("CREATE INDEX IF NOT EXISTS idx_bronze_990fin_ein ON bronze.bronze_organizations_990_financials(ein)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_990fin_state ON bronze.bronze_organizations_990_financials(state_code)"),
)
_FIN_UPSERT = text(
    """
    INSERT INTO bronze.bronze_organizations_990_financials (
        ein, tax_year, name, state_code, total_revenue, total_expenses,
        total_assets, total_liabilities, net_assets, total_contributions,
        program_service_revenue, source_url
    ) VALUES (
        :ein, :tax_year, :name, :state_code, :total_revenue, :total_expenses,
        :total_assets, :total_liabilities, :net_assets, :total_contributions,
        :program_service_revenue, :source_url
    )
    ON CONFLICT (ein, tax_year) DO UPDATE SET
        name = EXCLUDED.name,
        state_code = EXCLUDED.state_code,
        total_revenue = EXCLUDED.total_revenue,
        total_expenses = EXCLUDED.total_expenses,
        total_assets = EXCLUDED.total_assets,
        total_liabilities = EXCLUDED.total_liabilities,
        net_assets = EXCLUDED.net_assets,
        total_contributions = EXCLUDED.total_contributions,
        program_service_revenue = EXCLUDED.program_service_revenue,
        source_url = EXCLUDED.source_url,
        loaded_at = CURRENT_TIMESTAMP
    """
)
# source CSV column -> meaning (see data_dictionary.xlsx "990 Basic Fields")
_FIN_SRC_COLS = [
    "FILEREIN", "TAXYEAR", "FILERNAME1", "FILERUSSTATE", "TOTREVCURYEA",
    "TOTEXPCURYEA", "TOASEOOYY", "TOLIEOOYY", "NAFBEOY", "TOTACASHCONT",
    "TOTPROSERREV", "URL",
]


class Form990FinancialsPipeline(DataSourcePipeline[Form990FinancialsRow]):
    source = "givingtuesday_990_financials"
    batch_size = 50_000
    row_schema = Form990FinancialsRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or _latest_cached("990CN120Fields")
        emitted = 0
        for chunk in _read_chunks(path, _FIN_SRC_COLS):
            for row in chunk.to_dict("records"):
                if self._limit is not None and emitted >= self._limit:
                    return
                ein = _ein(row.get("FILEREIN"))
                if not ein:
                    continue
                yield {
                    "source": self.source,
                    "source_version": path.stem,
                    "natural_key": f"{ein}|{_safe_str(row.get('TAXYEAR')) or ''}",
                    "ein": ein,
                    "tax_year": _safe_int(row.get("TAXYEAR")),
                    "name": _safe_str(row.get("FILERNAME1")),
                    "state_code": _safe_str(row.get("FILERUSSTATE"), 2),
                    "total_revenue": _safe_int(row.get("TOTREVCURYEA")),
                    "total_expenses": _safe_int(row.get("TOTEXPCURYEA")),
                    "total_assets": _safe_int(row.get("TOASEOOYY")),
                    "total_liabilities": _safe_int(row.get("TOLIEOOYY")),
                    "net_assets": _safe_int(row.get("NAFBEOY")),
                    "total_contributions": _safe_int(row.get("TOTACASHCONT")),
                    "program_service_revenue": _safe_int(row.get("TOTPROSERREV")),
                    "source_url": _safe_str(row.get("URL")),
                }
                emitted += 1

    async def load_batch(self, session: AsyncSession, rows: list[Form990FinancialsRow], ctx: PipelineContext) -> None:
        await session.execute(_FIN_UPSERT, [r.model_dump(exclude=_BASE_FIELDS) for r in rows])


# --------------------------------------------------------------------------- #
# missions datamart (990Part1Missions)
# --------------------------------------------------------------------------- #
class Form990MissionRow(RawRow):
    ein: str = Field(min_length=1, max_length=20)
    tax_year: int | None = None
    name: str | None = None
    mission: str | None = None
    source_url: str | None = None


_MIS_DDL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_organizations_990_missions (
        id SERIAL PRIMARY KEY,
        ein VARCHAR(20) NOT NULL,
        tax_year INTEGER,
        name TEXT,
        mission TEXT,
        source_url TEXT,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ein, tax_year)
    )
    """
)
_MIS_INDEXES = (
    text("CREATE INDEX IF NOT EXISTS idx_bronze_990mis_ein ON bronze.bronze_organizations_990_missions(ein)"),
)
_MIS_UPSERT = text(
    """
    INSERT INTO bronze.bronze_organizations_990_missions (
        ein, tax_year, name, mission, source_url
    ) VALUES (
        :ein, :tax_year, :name, :mission, :source_url
    )
    ON CONFLICT (ein, tax_year) DO UPDATE SET
        name = EXCLUDED.name,
        mission = EXCLUDED.mission,
        source_url = EXCLUDED.source_url,
        loaded_at = CURRENT_TIMESTAMP
    """
)
_MIS_SRC_COLS = ["FILEREIN", "TAXYEAR", "FILERNAME1", "MISSION", "URL"]


class Form990MissionPipeline(DataSourcePipeline[Form990MissionRow]):
    source = "givingtuesday_990_missions"
    batch_size = 50_000
    row_schema = Form990MissionRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or _latest_cached("990Part1Missions")
        emitted = 0
        for chunk in _read_chunks(path, _MIS_SRC_COLS):
            for row in chunk.to_dict("records"):
                if self._limit is not None and emitted >= self._limit:
                    return
                ein = _ein(row.get("FILEREIN"))
                if not ein:
                    continue
                yield {
                    "source": self.source,
                    "source_version": path.stem,
                    "natural_key": f"{ein}|{_safe_str(row.get('TAXYEAR')) or ''}",
                    "ein": ein,
                    "tax_year": _safe_int(row.get("TAXYEAR")),
                    "name": _safe_str(row.get("FILERNAME1")),
                    "mission": _safe_str(row.get("MISSION")),
                    "source_url": _safe_str(row.get("URL")),
                }
                emitted += 1

    async def load_batch(self, session: AsyncSession, rows: list[Form990MissionRow], ctx: PipelineContext) -> None:
        await session.execute(_MIS_UPSERT, [r.model_dump(exclude=_BASE_FIELDS) for r in rows])


# --------------------------------------------------------------------------- #
# officers datamart (990Part7AOfficers) — person-level child table
# --------------------------------------------------------------------------- #
class Form990OfficerRow(RawRow):
    ein: str = Field(min_length=1, max_length=20)
    tax_year: int | None = None
    org_name: str | None = None
    person_name: str | None = None
    title: str | None = None
    avg_hours_org: float | None = None
    avg_hours_related: float | None = None
    is_officer: bool = False
    is_director_trustee: bool = False
    is_institutional_trustee: bool = False
    is_key_employee: bool = False
    is_highest_comp: bool = False
    is_former: bool = False
    reportable_comp_org: int | None = None
    reportable_comp_related: int | None = None
    other_comp: int | None = None
    source_url: str | None = None


_OFF_DDL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_organizations_990_officers (
        id SERIAL PRIMARY KEY,
        ein VARCHAR(20) NOT NULL,
        tax_year INTEGER,
        org_name TEXT,
        person_name TEXT,
        title TEXT,
        avg_hours_org NUMERIC,
        avg_hours_related NUMERIC,
        is_officer BOOLEAN DEFAULT FALSE,
        is_director_trustee BOOLEAN DEFAULT FALSE,
        is_institutional_trustee BOOLEAN DEFAULT FALSE,
        is_key_employee BOOLEAN DEFAULT FALSE,
        is_highest_comp BOOLEAN DEFAULT FALSE,
        is_former BOOLEAN DEFAULT FALSE,
        reportable_comp_org BIGINT,
        reportable_comp_related BIGINT,
        other_comp BIGINT,
        source_url TEXT,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)
_OFF_INDEXES = (
    text("CREATE INDEX IF NOT EXISTS idx_bronze_990off_ein ON bronze.bronze_organizations_990_officers(ein)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_990off_ein_year ON bronze.bronze_organizations_990_officers(ein, tax_year)"),
)
_OFF_INSERT = text(
    """
    INSERT INTO bronze.bronze_organizations_990_officers (
        ein, tax_year, org_name, person_name, title,
        avg_hours_org, avg_hours_related,
        is_officer, is_director_trustee, is_institutional_trustee,
        is_key_employee, is_highest_comp, is_former,
        reportable_comp_org, reportable_comp_related, other_comp, source_url
    ) VALUES (
        :ein, :tax_year, :org_name, :person_name, :title,
        :avg_hours_org, :avg_hours_related,
        :is_officer, :is_director_trustee, :is_institutional_trustee,
        :is_key_employee, :is_highest_comp, :is_former,
        :reportable_comp_org, :reportable_comp_related, :other_comp, :source_url
    )
    """
)
# A Part VII listee's name lands in NAMEPEPERSON (PersonNm, ~98.8% of rows) OR
# BUNABUNALIIN1 (the BusinessName-line variant, ~1.2%); the two are mutually
# exclusive. Both must be read and coalesced, else the BusinessName-variant rows
# are silently dropped (for some orgs that's ~45% of their officers).
_OFF_SRC_COLS = [
    "FILEREIN", "TAXYEAR", "FILERNAME1", "NAMEPEPERSON", "BUNABUNALIIN1", "TITLEITLE",
    "AVHOPEWEREEL", "AVEHOUPERWEE", "OFFICERFFICE", "INDITRUSDIRE",
    "INSTITTRUSTE", "KEYEMPEMPLOY", "HIGHCOMPEMPL", "FORMERORMER",
    "REPCOMFROORG", "RECOFRRLORRG", "OTHERCCOMPEN", "URL",
]


class Form990OfficerPipeline(DataSourcePipeline[Form990OfficerRow]):
    source = "givingtuesday_990_officers"
    batch_size = 25_000
    row_schema = Form990OfficerRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or _latest_cached("990Part7AOfficers")
        emitted = 0
        for chunk in _read_chunks(path, _OFF_SRC_COLS):
            for row in chunk.to_dict("records"):
                if self._limit is not None and emitted >= self._limit:
                    return
                ein = _ein(row.get("FILEREIN"))
                person = _safe_str(row.get("NAMEPEPERSON")) or _safe_str(row.get("BUNABUNALIIN1"))
                if not ein or not person:
                    continue
                yield {
                    "source": self.source,
                    "source_version": path.stem,
                    "natural_key": f"{ein}|{_safe_str(row.get('TAXYEAR')) or ''}|{person}",
                    "ein": ein,
                    "tax_year": _safe_int(row.get("TAXYEAR")),
                    "org_name": _safe_str(row.get("FILERNAME1")),
                    "person_name": person,
                    "title": _safe_str(row.get("TITLEITLE")),
                    "avg_hours_org": _safe_num(row.get("AVHOPEWEREEL")),
                    "avg_hours_related": _safe_num(row.get("AVEHOUPERWEE")),
                    "is_officer": _safe_bool(row.get("OFFICERFFICE")),
                    "is_director_trustee": _safe_bool(row.get("INDITRUSDIRE")),
                    "is_institutional_trustee": _safe_bool(row.get("INSTITTRUSTE")),
                    "is_key_employee": _safe_bool(row.get("KEYEMPEMPLOY")),
                    "is_highest_comp": _safe_bool(row.get("HIGHCOMPEMPL")),
                    "is_former": _safe_bool(row.get("FORMERORMER")),
                    "reportable_comp_org": _safe_int(row.get("REPCOMFROORG")),
                    "reportable_comp_related": _safe_int(row.get("RECOFRRLORRG")),
                    "other_comp": _safe_int(row.get("OTHERCCOMPEN")),
                    "source_url": _safe_str(row.get("URL")),
                }
                emitted += 1

    async def load_batch(self, session: AsyncSession, rows: list[Form990OfficerRow], ctx: PipelineContext) -> None:
        await session.execute(_OFF_INSERT, [r.model_dump(exclude=_BASE_FIELDS) for r in rows])


# --------------------------------------------------------------------------- #
# Schedule J datamart (ScheduleJPart2Officers) — person-level child table
# --------------------------------------------------------------------------- #
class Form990ScheduleJRow(RawRow):
    ein: str = Field(min_length=1, max_length=20)
    tax_year: int | None = None
    org_name: str | None = None
    person_name: str | None = None
    title: str | None = None
    base_comp_org: int | None = None
    base_comp_related: int | None = None
    bonus_org: int | None = None
    bonus_related: int | None = None
    other_comp_org: int | None = None
    other_comp_related: int | None = None
    deferred_comp_org: int | None = None
    deferred_comp_related: int | None = None
    nontaxable_benefits_org: int | None = None
    nontaxable_benefits_related: int | None = None
    total_comp_org: int | None = None
    total_comp_related: int | None = None
    prior_reported_org: int | None = None
    prior_reported_related: int | None = None
    source_url: str | None = None


_SJ_DDL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_organizations_990_schedule_j (
        id SERIAL PRIMARY KEY,
        ein VARCHAR(20) NOT NULL,
        tax_year INTEGER,
        org_name TEXT,
        person_name TEXT,
        title TEXT,
        base_comp_org BIGINT,
        base_comp_related BIGINT,
        bonus_org BIGINT,
        bonus_related BIGINT,
        other_comp_org BIGINT,
        other_comp_related BIGINT,
        deferred_comp_org BIGINT,
        deferred_comp_related BIGINT,
        nontaxable_benefits_org BIGINT,
        nontaxable_benefits_related BIGINT,
        total_comp_org BIGINT,
        total_comp_related BIGINT,
        prior_reported_org BIGINT,
        prior_reported_related BIGINT,
        source_url TEXT,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)
_SJ_INDEXES = (
    text("CREATE INDEX IF NOT EXISTS idx_bronze_990sj_ein ON bronze.bronze_organizations_990_schedule_j(ein)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_990sj_ein_year ON bronze.bronze_organizations_990_schedule_j(ein, tax_year)"),
)
_SJ_INSERT = text(
    """
    INSERT INTO bronze.bronze_organizations_990_schedule_j (
        ein, tax_year, org_name, person_name, title,
        base_comp_org, base_comp_related, bonus_org, bonus_related,
        other_comp_org, other_comp_related, deferred_comp_org, deferred_comp_related,
        nontaxable_benefits_org, nontaxable_benefits_related,
        total_comp_org, total_comp_related, prior_reported_org, prior_reported_related,
        source_url
    ) VALUES (
        :ein, :tax_year, :org_name, :person_name, :title,
        :base_comp_org, :base_comp_related, :bonus_org, :bonus_related,
        :other_comp_org, :other_comp_related, :deferred_comp_org, :deferred_comp_related,
        :nontaxable_benefits_org, :nontaxable_benefits_related,
        :total_comp_org, :total_comp_related, :prior_reported_org, :prior_reported_related,
        :source_url
    )
    """
)
# source CSV column -> meaning. Schedule J Part 2 person-comp columns are not in
# the published data dictionary; mapped from the standard IRS Schedule J Part 2
# layout (base / bonus / other / deferred / nontaxable / total / prior-reported,
# each split filing-org vs related-org).
_SJ_SRC_COLS = [
    # NAMEPEPERSON holds the name for ~95% of rows; the rest carry it in the
    # BusinessName-line variant NABUBUNALIIN1/2 (cf. BUNABUNALIIN1 in officers).
    # Read all three and coalesce, else those rows are silently dropped.
    "FILEREIN", "TAXYEAR", "FILERNAME1", "NAMEPEPERSON", "NABUBUNALIIN1",
    "NABUBUNALIIN2", "TITLEITLE",
    "BASCOMFILORG", "COBAONREORRG", "BONUFILIORGR", "BONURELAORGS",
    "OTHCOMFILORG", "OTHCOMRELORG", "DEFCOMFILORG", "DEFCOMRELORG",
    "NONBENFILORG", "NONBENRELORG", "TOTCOMFILORG", "TOTCOMRELORG",
    "COREPRFIORRG", "COREPRREORRG", "URL",
]


class Form990ScheduleJPipeline(DataSourcePipeline[Form990ScheduleJRow]):
    source = "givingtuesday_990_schedule_j"
    batch_size = 25_000
    row_schema = Form990ScheduleJRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or _latest_cached("ScheduleJPart2Officers")
        emitted = 0
        for chunk in _read_chunks(path, _SJ_SRC_COLS):
            for row in chunk.to_dict("records"):
                if self._limit is not None and emitted >= self._limit:
                    return
                ein = _ein(row.get("FILEREIN"))
                person = (
                    _safe_str(row.get("NAMEPEPERSON"))
                    or _safe_str(row.get("NABUBUNALIIN1"))
                    or _safe_str(row.get("NABUBUNALIIN2"))
                )
                if not ein or not person:
                    continue
                yield {
                    "source": self.source,
                    "source_version": path.stem,
                    "natural_key": f"{ein}|{_safe_str(row.get('TAXYEAR')) or ''}|{person}",
                    "ein": ein,
                    "tax_year": _safe_int(row.get("TAXYEAR")),
                    "org_name": _safe_str(row.get("FILERNAME1")),
                    "person_name": person,
                    "title": _safe_str(row.get("TITLEITLE")),
                    "base_comp_org": _safe_int(row.get("BASCOMFILORG")),
                    "base_comp_related": _safe_int(row.get("COBAONREORRG")),
                    "bonus_org": _safe_int(row.get("BONUFILIORGR")),
                    "bonus_related": _safe_int(row.get("BONURELAORGS")),
                    "other_comp_org": _safe_int(row.get("OTHCOMFILORG")),
                    "other_comp_related": _safe_int(row.get("OTHCOMRELORG")),
                    "deferred_comp_org": _safe_int(row.get("DEFCOMFILORG")),
                    "deferred_comp_related": _safe_int(row.get("DEFCOMRELORG")),
                    "nontaxable_benefits_org": _safe_int(row.get("NONBENFILORG")),
                    "nontaxable_benefits_related": _safe_int(row.get("NONBENRELORG")),
                    "total_comp_org": _safe_int(row.get("TOTCOMFILORG")),
                    "total_comp_related": _safe_int(row.get("TOTCOMRELORG")),
                    "prior_reported_org": _safe_int(row.get("COREPRFIORRG")),
                    "prior_reported_related": _safe_int(row.get("COREPRREORRG")),
                    "source_url": _safe_str(row.get("URL")),
                }
                emitted += 1

    async def load_batch(self, session: AsyncSession, rows: list[Form990ScheduleJRow], ctx: PipelineContext) -> None:
        await session.execute(_SJ_INSERT, [r.model_dump(exclude=_BASE_FIELDS) for r in rows])


# --------------------------------------------------------------------------- #
# Schedule I Part II datamart (ScheduleIPart2Grants) — grant-line child table
# --------------------------------------------------------------------------- #
# Schedule I Part II = grants & other assistance to domestic ORGANIZATIONS
# (one row per grant line: grantor filer -> grantee org, cash amount, purpose).
# This is the grantmaking source for the `grant` mart. Part III (grants to
# individuals) is a separate datamart and is NOT loaded here.
#
# There is no stable per-line natural key in the source, so this is an
# append-only INSERT (like officers / schedule_j) — always run with --truncate
# for a clean reload. A surrogate grant_id is minted downstream in dbt.
class Form990ScheduleIRow(RawRow):
    grantor_ein: str = Field(min_length=1, max_length=20)
    tax_year: int | None = None
    grantor_name: str | None = None
    grantee_name: str | None = None
    grantee_ein: str | None = None
    grantee_city: str | None = None
    grantee_state_code: str | None = None
    grantee_zip: str | None = None
    irc_section: str | None = None
    cash_grant_amount: int | None = None
    noncash_assistance_amount: int | None = None
    valuation_method: str | None = None
    noncash_description: str | None = None
    purpose: str | None = None
    source_url: str | None = None


_SI_DDL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_grants_gt990_schedule_i (
        id SERIAL PRIMARY KEY,
        grantor_ein VARCHAR(20) NOT NULL,
        tax_year INTEGER,
        grantor_name TEXT,
        grantee_name TEXT,
        grantee_ein VARCHAR(20),
        grantee_city TEXT,
        grantee_state_code VARCHAR(2),
        grantee_zip VARCHAR(10),
        irc_section TEXT,
        cash_grant_amount BIGINT,
        noncash_assistance_amount BIGINT,
        valuation_method TEXT,
        noncash_description TEXT,
        purpose TEXT,
        source_url TEXT,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)
_SI_INDEXES = (
    text("CREATE INDEX IF NOT EXISTS idx_bronze_990si_grantor_ein ON bronze.bronze_grants_gt990_schedule_i(grantor_ein)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_990si_grantee_ein ON bronze.bronze_grants_gt990_schedule_i(grantee_ein)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_990si_grantor_year ON bronze.bronze_grants_gt990_schedule_i(grantor_ein, tax_year)"),
)
_SI_INSERT = text(
    """
    INSERT INTO bronze.bronze_grants_gt990_schedule_i (
        grantor_ein, tax_year, grantor_name, grantee_name, grantee_ein,
        grantee_city, grantee_state_code, grantee_zip, irc_section,
        cash_grant_amount, noncash_assistance_amount, valuation_method,
        noncash_description, purpose, source_url
    ) VALUES (
        :grantor_ein, :tax_year, :grantor_name, :grantee_name, :grantee_ein,
        :grantee_city, :grantee_state_code, :grantee_zip, :irc_section,
        :cash_grant_amount, :noncash_assistance_amount, :valuation_method,
        :noncash_description, :purpose, :source_url
    )
    """
)
# source CSV column -> meaning (Schedule I Part II layout; abbreviations confirmed
# against the 2025_08_29_All_Years_ScheduleIPart2Grants.csv header + sample rows).
# The grantee BusinessName lands on RTRNBBNLINE11 (line 1) and RTRNBBNLINE22
# (line 2, the continuation); coalesce/concatenate both, else 2-line org names
# are truncated.
_SI_SRC_COLS = [
    "FILEREIN", "FILERNAME1", "FILERNAME2", "TAXYEAR",
    "RTRNBBNLINE11", "RTRNBBNLINE22", "RTEINORECIPI",
    "RECTABADDCIT", "RECTABADDSTA", "RTAZIPCODE", "RETAIRRCCSSE",
    "RETAAMOFCAGR", "RTAONCASSIST", "RETAMEOFVAAL", "RTDONCASSIST",
    "RETAPUOFGRRA", "URL",
]


class Form990ScheduleIPipeline(DataSourcePipeline[Form990ScheduleIRow]):
    source = "givingtuesday_990_schedule_i"
    batch_size = 25_000
    row_schema = Form990ScheduleIRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or _latest_cached("ScheduleIPart2Grants")
        emitted = 0
        for chunk in _read_chunks(path, _SI_SRC_COLS):
            for row in chunk.to_dict("records"):
                if self._limit is not None and emitted >= self._limit:
                    return
                grantor_ein = _ein(row.get("FILEREIN"))
                name1 = _safe_str(row.get("RTRNBBNLINE11"))
                name2 = _safe_str(row.get("RTRNBBNLINE22"))
                grantee_name = " ".join(p for p in (name1, name2) if p) or None
                grantor_name = " ".join(
                    p for p in (_safe_str(row.get("FILERNAME1")), _safe_str(row.get("FILERNAME2"))) if p
                ) or None
                # Drop lines with neither a grantor EIN nor a grantee — not a usable grant.
                if not grantor_ein or not grantee_name:
                    continue
                yield {
                    "source": self.source,
                    "source_version": path.stem,
                    "natural_key": (
                        f"{grantor_ein}|{_safe_str(row.get('TAXYEAR')) or ''}|"
                        f"{grantee_name}|{_safe_str(row.get('RETAAMOFCAGR')) or ''}"
                    ),
                    "grantor_ein": grantor_ein,
                    "tax_year": _safe_int(row.get("TAXYEAR")),
                    "grantor_name": grantor_name,
                    "grantee_name": grantee_name,
                    "grantee_ein": _ein(row.get("RTEINORECIPI")),
                    "grantee_city": _safe_str(row.get("RECTABADDCIT")),
                    "grantee_state_code": _safe_str(row.get("RECTABADDSTA"), 2),
                    "grantee_zip": _safe_str(row.get("RTAZIPCODE"), 10),
                    "irc_section": _safe_str(row.get("RETAIRRCCSSE")),
                    "cash_grant_amount": _safe_int(row.get("RETAAMOFCAGR")),
                    "noncash_assistance_amount": _safe_int(row.get("RTAONCASSIST")),
                    "valuation_method": _safe_str(row.get("RETAMEOFVAAL")),
                    "noncash_description": _safe_str(row.get("RTDONCASSIST")),
                    "purpose": _safe_str(row.get("RETAPUOFGRRA")),
                    "source_url": _safe_str(row.get("URL")),
                }
                emitted += 1

    async def load_batch(self, session: AsyncSession, rows: list[Form990ScheduleIRow], ctx: PipelineContext) -> None:
        await session.execute(_SI_INSERT, [r.model_dump(exclude=_BASE_FIELDS) for r in rows])


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
# Person-level child tables (officers, schedule_j) are append-only INSERTs with
# no natural unique key — always run them with --truncate for a clean reload.
_DATAMARTS = {
    "financials": (Form990FinancialsPipeline, _FIN_DDL, _FIN_INDEXES,
                   "bronze.bronze_organizations_990_financials", "990CN120Fields"),
    "missions": (Form990MissionPipeline, _MIS_DDL, _MIS_INDEXES,
                 "bronze.bronze_organizations_990_missions", "990Part1Missions"),
    "officers": (Form990OfficerPipeline, _OFF_DDL, _OFF_INDEXES,
                 "bronze.bronze_organizations_990_officers", "990Part7AOfficers"),
    "schedule_j": (Form990ScheduleJPipeline, _SJ_DDL, _SJ_INDEXES,
                   "bronze.bronze_organizations_990_schedule_j", "ScheduleJPart2Officers"),
    "schedule_i": (Form990ScheduleIPipeline, _SI_DDL, _SI_INDEXES,
                   "bronze.bronze_grants_gt990_schedule_i", "ScheduleIPart2Grants"),
}


async def _prepare_target(ddl, indexes, table: str, truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(text("CREATE SCHEMA IF NOT EXISTS bronze"))
        await session.execute(ddl)
        for idx in indexes:
            await session.execute(idx)
        if truncate:
            await session.execute(text(f"TRUNCATE TABLE {table}"))


async def _table_count(table: str) -> int:
    async with async_session() as session:
        result = await session.execute(text(f"SELECT count(*) FROM {table}"))
        return int(result.scalar_one())


async def _load_one(
    name: str, *, file: Path | None, limit: int | None, truncate: bool, allow_partial: bool = False
) -> None:
    from loguru import logger

    pipeline_cls, ddl, indexes, table, substr = _DATAMARTS[name]
    path = file or _latest_cached(substr)

    # A --limit load writes a partial table that downstream cannot tell apart
    # from a complete one. Refuse it for real loads unless explicitly allowed.
    if limit is not None and not allow_partial:
        raise SystemExit(
            f"Refusing to load '{name}' with --limit {limit:,} into {table}: this writes a "
            f"PARTIAL table indistinguishable from a complete load. Pass --allow-partial if a "
            f"partial load is intentional (e.g. testing)."
        )

    await _prepare_target(ddl, indexes, table, truncate)
    run = await pipeline_cls(path=path, limit=limit).run()

    # --- completeness validation: source rows vs. what we actually read/loaded.
    expected = _count_source_rows(path)
    db_rows = await _table_count(table)
    completeness = (run.extracted / expected) if expected else 0.0

    logger.success(
        f"{name}: loaded {run.loaded:,} rows into {table} "
        f"(extracted {run.extracted:,}, rejected {run.rejected:,}); "
        f"source {path.name} has {expected:,} data rows -> read {completeness:.1%}; "
        f"{table} now holds {db_rows:,} rows"
    )

    if run.loaded != run.extracted:
        raise RuntimeError(
            f"{name}: loaded {run.loaded:,} != extracted {run.extracted:,} — "
            f"rows were lost on insert into {table}."
        )
    if limit is None and completeness < _COMPLETENESS_THRESHOLD:
        raise RuntimeError(
            f"{name}: INCOMPLETE LOAD — read only {completeness:.1%} of {expected:,} source "
            f"rows ({run.extracted:,}) with no --limit. {table} is partial; investigate the "
            f"source CSV and pipeline before trusting it."
        )
    if limit is not None:
        logger.warning(
            f"{name}: PARTIAL load ({run.extracted:,} of {expected:,} source rows, "
            f"{completeness:.1%}) due to --limit; {table} is intentionally incomplete."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load cached GivingTuesday 990 datamarts into bronze",
    )
    parser.add_argument(
        "--datamart", choices=[*_DATAMARTS, "all"], default="all",
        help="Which datamart to load (default: all)",
    )
    parser.add_argument("--file", type=Path, help="Explicit CSV path (default: latest cached match)")
    parser.add_argument("--limit", type=int, help="Limit rows (for testing)")
    parser.add_argument("--truncate", action="store_true", help="TRUNCATE table before loading")
    parser.add_argument(
        "--allow-partial", action="store_true",
        help="Permit a --limit (partial) load into the real table; otherwise refused",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    names = list(_DATAMARTS) if args.datamart == "all" else [args.datamart]
    for name in names:
        await _load_one(
            name, file=args.file, limit=args.limit, truncate=args.truncate,
            allow_partial=args.allow_partial,
        )


def main() -> None:
    setup_logging()
    asyncio.run(_run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
