#!/usr/bin/env python3
"""
Load Ballotpedia ballot-measure JSON snapshots into ``bronze.bronze_ballot_measures_ballotpedia``.

Reads timestamped JSON files produced by ``download_ballotpedia_measures.py`` (and
compatible snapshots written by the Google Civic loader path), maps fields into the
NIST-aligned bronze columns, resolves ``ocd_division_id`` via OCD crosswalk, and
stores the full measure dict in ``raw_row``.

By default only measures with ``election_year`` in **2025** or **2026** are loaded.

Usage
-----
    python scripts/datasources/ballotpedia/load_ballotpedia_measures_to_bronze.py
    python scripts/datasources/ballotpedia/load_ballotpedia_measures_to_bronze.py --truncate
    python scripts/datasources/ballotpedia/load_ballotpedia_measures_to_bronze.py \\
        --years 2025,2026 --cache-dir data/cache/ballotpedia
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv
from loguru import logger
from psycopg2.extras import Json, execute_batch

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))
load_dotenv(_ROOT / ".env")

CACHE_DIR = _ROOT / "data" / "cache" / "ballotpedia"
DEFAULT_ELECTION_YEARS = ("2025", "2026")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DATABASE_URL = (
    os.getenv("NEON_DATABASE_URL_DEV", "").strip()
    or os.getenv("OPEN_NAVIGATOR_DATABASE_URL", "").strip()
    or f"postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator"
)

TABLE = "bronze.bronze_ballot_measures_ballotpedia"
_UUID_NS = uuid.UUID("b1ed9a39-f6a5-44f7-8e4b-5e0f58d4c0da")

CREATE_TABLE_SQL = """
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE IF NOT EXISTS bronze.bronze_ballot_measures_ballotpedia (
        id                  BIGSERIAL PRIMARY KEY,
        scrape_batch_id     UUID NOT NULL,
        measure_id          TEXT NOT NULL,
        ocd_division_id     TEXT,
        state_code          CHAR(2),
        jurisdiction_id     TEXT,
        jurisdiction_name   TEXT,
        jurisdiction_type   TEXT,
        election_date       DATE,
        election_year       VARCHAR(4),
        measure_number      TEXT,
        measure_title       TEXT NOT NULL,
        full_text           TEXT,
        summary_text        TEXT,
        measure_type        TEXT,
        subject_areas       TEXT,
        yes_votes           BIGINT,
        no_votes            BIGINT,
        passed              BOOLEAN,
        source_url          TEXT,
        measure_page_url    TEXT,
        raw_row             JSONB NOT NULL DEFAULT '{}'::JSONB,
        source_json_path    TEXT,
        scraped_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        loaded_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_bbmb_ocd    ON bronze.bronze_ballot_measures_ballotpedia (ocd_division_id);
    CREATE INDEX IF NOT EXISTS idx_bbmb_state  ON bronze.bronze_ballot_measures_ballotpedia (state_code);
    CREATE INDEX IF NOT EXISTS idx_bbmb_jur    ON bronze.bronze_ballot_measures_ballotpedia (jurisdiction_id);
    CREATE INDEX IF NOT EXISTS idx_bbmb_date   ON bronze.bronze_ballot_measures_ballotpedia (election_date);
    CREATE INDEX IF NOT EXISTS idx_bbmb_year   ON bronze.bronze_ballot_measures_ballotpedia (election_year);
    CREATE INDEX IF NOT EXISTS idx_bbmb_batch  ON bronze.bronze_ballot_measures_ballotpedia (scrape_batch_id);
    CREATE INDEX IF NOT EXISTS idx_bbmb_mid    ON bronze.bronze_ballot_measures_ballotpedia (measure_id);
"""

INSERT_SQL = """
    INSERT INTO bronze.bronze_ballot_measures_ballotpedia (
        scrape_batch_id, measure_id, ocd_division_id,
        state_code, jurisdiction_id, jurisdiction_name, jurisdiction_type,
        election_date, election_year, measure_number,
        measure_title, full_text, summary_text, measure_type, subject_areas,
        yes_votes, no_votes, passed,
        source_url, measure_page_url, raw_row, source_json_path, scraped_at
    ) VALUES (
        %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s, %s, %s
    )
"""

_PASSED_RE = re.compile(r"\b(?:pass(?:ed|es|ing)?|approv(?:ed|es|al)|adopt(?:ed|s)?|yes)\b", re.I)
_FAILED_RE = re.compile(r"\b(?:fail(?:ed|s|ure)?|defeat(?:ed|s)?|reject(?:ed|s)?|no)\b", re.I)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_VOTE_PAIR_RE = re.compile(
    r"(?P<yes>\d[\d,]*)\s*(?:yes|for|in favor)[^\d]{0,40}(?P<no>\d[\d,]*)\s*(?:no|against)",
    re.I,
)
_CACHE_DEDUPE_RE = re.compile(r"^(?P<prefix>.+_ballot_measures(?:_\d{4})?)_\d{8}T", re.I)


def _parse_years(raw: str | None) -> frozenset[str]:
    if not raw or not raw.strip():
        return frozenset(DEFAULT_ELECTION_YEARS)
    years = frozenset(y.strip() for y in raw.split(",") if y.strip())
    return years or frozenset(DEFAULT_ELECTION_YEARS)


def _cache_dedupe_key(path: Path) -> str:
    """One newest snapshot per state/jurisdiction + election year label."""
    m = _CACHE_DEDUPE_RE.match(path.name)
    prefix = m.group("prefix") if m else path.stem
    return str(path.parent / prefix)


def _stable_id(prefix: str, key: str) -> str:
    return f"ocd-{prefix}/{uuid.uuid5(_UUID_NS, key)}"


def _stable_key(*parts: str | None) -> str:
    return "|".join((p or "").strip().lower() for p in parts)


def _parse_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        s = str(val).replace(",", "").strip()
        return int(float(s)) if s else None
    except (ValueError, TypeError):
        return None


def _parse_passed(outcome: str | None) -> bool | None:
    if not outcome:
        return None
    if _PASSED_RE.search(outcome) and not _FAILED_RE.search(outcome):
        return True
    if _FAILED_RE.search(outcome) and not _PASSED_RE.search(outcome):
        return False
    return None


def _extract_year(text: str | None, explicit: Any = None) -> str | None:
    if explicit is not None and str(explicit).strip():
        m = _YEAR_RE.search(str(explicit))
        if m:
            return m.group(0)
    if text:
        m = _YEAR_RE.search(text)
        if m:
            return m.group(0)
    return None


def _extract_votes(outcome: str | None) -> tuple[int | None, int | None]:
    if not outcome:
        return None, None
    m = _VOTE_PAIR_RE.search(outcome)
    if not m:
        return None, None
    return _parse_int(m.group("yes")), _parse_int(m.group("no"))


def _state_code_from_name(state: str | None) -> str | None:
    if not state:
        return None
    s = state.strip()
    if len(s) == 2 and s.isalpha():
        return s.upper()
    from scripts.datasources.ballotpedia.ballotpedia_integration import BallotpediaDiscovery
    for code, name in BallotpediaDiscovery.STATE_NAME_BY_CODE.items():
        if name.lower() == s.lower():
            return code
    return None


def _resolve_ocd_division_id(
    *,
    state_code: str | None,
    jurisdiction_name: str | None,
    jurisdiction_type: str | None,
    scope: str | None,
) -> str | None:
    if scope == "state" and state_code:
        return f"ocd-division/country:us/state:{state_code.lower()}"
    if jurisdiction_name and state_code:
        from scripts.datasources.jurisdiction_pilot.load_ocd_jurisdictions import find_ocd_match
        return find_ocd_match(jurisdiction_name, state_code, jurisdiction_type=jurisdiction_type)
    if state_code:
        return f"ocd-division/country:us/state:{state_code.lower()}"
    return None


def _normalize_measure(
    measure: dict[str, Any],
    *,
    envelope: dict[str, Any],
    source_path: Path,
) -> dict[str, Any] | None:
    title = (
        measure.get("measure_title")
        or measure.get("measure_name")
        or measure.get("title")
        or ""
    ).strip()
    if not title:
        return None

    state_code = (
        envelope.get("state_code")
        or _state_code_from_name(measure.get("state"))
        or _state_code_from_name(envelope.get("state"))
    )
    jurisdiction_id = envelope.get("jurisdiction_id") or measure.get("jurisdiction_id")
    jurisdiction_name = measure.get("jurisdiction") or envelope.get("jurisdiction_name")
    jurisdiction_type = envelope.get("jurisdiction_type") or measure.get("jurisdiction_type")
    scope = envelope.get("scope") or measure.get("scope")

    outcome = measure.get("measure_outcome") or measure.get("status")
    yes_votes = _parse_int(measure.get("yes_votes"))
    no_votes = _parse_int(measure.get("no_votes"))
    if yes_votes is None and no_votes is None:
        yes_votes, no_votes = _extract_votes(outcome)

    election_year = _extract_year(title, envelope.get("election_year") or measure.get("year"))

    ocd_division_id = measure.get("ocd_division_id") or _resolve_ocd_division_id(
        state_code=state_code,
        jurisdiction_name=jurisdiction_name if scope != "state" else None,
        jurisdiction_type=jurisdiction_type,
        scope=scope,
    )

    measure_id = measure.get("measure_id") or _stable_id(
        "ballotmeasure",
        _stable_key(
            "ballotpedia",
            state_code,
            jurisdiction_id,
            title,
            election_year,
            measure.get("measure_url"),
            outcome,
        ),
    )

    scraped_raw = measure.get("scraped_at") or envelope.get("scraped_at")
    scraped_at = None
    if scraped_raw:
        try:
            scraped_at = datetime.fromisoformat(str(scraped_raw).replace("Z", "+00:00"))
        except ValueError:
            scraped_at = None

    return {
        "measure_id": measure_id,
        "ocd_division_id": ocd_division_id,
        "state_code": state_code,
        "jurisdiction_id": jurisdiction_id,
        "jurisdiction_name": jurisdiction_name,
        "jurisdiction_type": jurisdiction_type,
        "election_date": measure.get("election_date"),
        "election_year": election_year,
        "measure_number": measure.get("measure_number") or measure.get("number"),
        "measure_title": title,
        "full_text": measure.get("full_text"),
        "summary_text": measure.get("summary_text") or measure.get("measure_summary"),
        "measure_type": measure.get("measure_type") or measure.get("type"),
        "subject_areas": measure.get("subject_areas"),
        "yes_votes": yes_votes,
        "no_votes": no_votes,
        "passed": measure.get("passed") if measure.get("passed") is not None else _parse_passed(outcome),
        "source_url": measure.get("source_url") or envelope.get("source_url"),
        "measure_page_url": measure.get("measure_url") or measure.get("measure_page_url"),
        "raw_row": measure,
        "source_json_path": str(source_path),
        "scraped_at": scraped_at,
    }


def _iter_cache_files(cache_dir: Path) -> list[Path]:
    patterns = ("*_ballot_measures_*.json", "*_ballot_measures.json")
    skip_dirs = {"fetch_debug", "playwright_debug"}
    files: list[Path] = []
    for pat in patterns:
        for path in cache_dir.rglob(pat):
            if any(part in skip_dirs for part in path.parts):
                continue
            files.append(path)
    # De-dupe and prefer newest per directory prefix
    seen: set[str] = set()
    ordered: list[Path] = []
    for path in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True):
        key = _cache_dedupe_key(path)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
    return sorted(ordered, key=lambda p: p.stat().st_mtime)


def _load_json(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {}, data
    measures = data.get("measures") or data.get("ballot_measures") or []
    if not measures and isinstance(data.get("measure_title"), str):
        measures = [data]
    return data if isinstance(data, dict) else {}, measures


def parse_cache(
    cache_dir: Path,
    *,
    years: frozenset[str],
    limit_files: int | None = None,
) -> tuple[list[tuple], uuid.UUID, int, int]:
    files = _iter_cache_files(cache_dir)
    if limit_files:
        files = files[:limit_files]
    if not files:
        raise FileNotFoundError(
            f"No ballot-measures JSON under {cache_dir}. "
            "Run download_ballotpedia_measures.py first."
        )

    batch_id = uuid.uuid4()
    records: list[tuple] = []
    source_measures = 0
    skipped_year = 0

    for path in files:
        envelope, measures = _load_json(path)
        source_measures += len(measures)
        for measure in measures:
            row = _normalize_measure(measure, envelope=envelope, source_path=path)
            if not row:
                continue
            election_year = row.get("election_year")
            if election_year not in years:
                skipped_year += 1
                continue
            records.append((
                str(batch_id),
                row["measure_id"],
                row["ocd_division_id"],
                row["state_code"],
                row["jurisdiction_id"],
                row["jurisdiction_name"],
                row["jurisdiction_type"],
                row["election_date"],
                row["election_year"],
                row["measure_number"],
                row["measure_title"],
                row["full_text"],
                row["summary_text"],
                row["measure_type"],
                row["subject_areas"],
                row["yes_votes"],
                row["no_votes"],
                row["passed"],
                row["source_url"],
                row["measure_page_url"],
                Json(row["raw_row"]),
                row["source_json_path"],
                row["scraped_at"],
            ))

    return records, batch_id, source_measures, skipped_year


def load(
    records: list[tuple],
    *,
    dry_run: bool,
    truncate: bool,
) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(CREATE_TABLE_SQL)
    conn.commit()

    if truncate:
        cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
        before = cur.fetchone()[0]
        cur.execute(f"TRUNCATE TABLE {TABLE} RESTART IDENTITY")
        conn.commit()
        logger.info("Truncated {} ({:,} rows removed)", TABLE, before)

    if dry_run:
        logger.warning("DRY RUN — first 3 records:")
        for r in records[:3]:
            logger.info("  {}", r[:6])
        cur.close()
        conn.close()
        return 0

    execute_batch(cur, INSERT_SQL, records, page_size=500)
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
    total = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE ocd_division_id IS NOT NULL")
    with_ocd = cur.fetchone()[0]
    logger.success("Inserted {:,} rows → {} (table total: {:,}, with ocd_division_id: {:,})",
                   len(records), TABLE, total, with_ocd)

    cur.execute(f"""
        SELECT state_code, COUNT(*) AS cnt
        FROM {TABLE}
        WHERE state_code IS NOT NULL
        GROUP BY state_code ORDER BY cnt DESC LIMIT 10
    """)
    for sc, cnt in cur.fetchall():
        logger.info("  {}: {:,}", sc, cnt)

    cur.close()
    conn.close()
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument(
        "--years",
        default=",".join(DEFAULT_ELECTION_YEARS),
        help=f"Comma-separated election years to load (default: {','.join(DEFAULT_ELECTION_YEARS)})",
    )
    parser.add_argument("--limit", type=int, help="Limit number of cache files to read")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--truncate", action="store_true")
    args = parser.parse_args()

    years = _parse_years(args.years)

    logger.info("=" * 70)
    logger.info("Ballotpedia measures → {}", TABLE)
    logger.info("Election years: {}", ", ".join(sorted(years)))
    logger.info("=" * 70)

    records, batch_id, source_measures, skipped_year = parse_cache(
        args.cache_dir, years=years, limit_files=args.limit,
    )
    logger.info(
        "batch_id={} | {} cache measure(s) → {} bronze row(s) (skipped {} outside years)",
        batch_id, source_measures, len(records), skipped_year,
    )

    if not records:
        logger.error("No measures parsed from cache — nothing to load")
        return 1

    load(records, dry_run=args.dry_run, truncate=args.truncate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
