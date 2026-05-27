#!/usr/bin/env python3
"""Google Civic elections/voter-info pipeline: land cached payloads into bronze.

Ported from load_google_civic_officials_to_c1.py to the core_lib
DataSourcePipeline contract.

=============================================================================
TRANSFORMATION-HEAVY / DERIVATION JOB — READ THIS.
=============================================================================
The legacy loader was NOT a simple "land a cached file into one bronze table"
job. It (a) called the Google Civic API live (elections.electionQuery,
voterInfoQuery, divisionsByAddress), (b) read jurisdiction *targets* from the
``intermediate.int_jurisdictions`` DB table, (c) wrote per-jurisdiction cache
JSON to disk as a side effect, (d) inserted derived OCD-EP-0020 rows into
``bronze.bronze_elections_scraped`` (and best-effort Ballotpedia link rows into
``bronze.bronze_websites_ballotpedia``), then (e) PROMOTED bronze -> c1 via
``upsert_divisions / upsert_elections / upsert_candidate_contests /
upsert_candidacies / upsert_ballot_measures``.

Steps (a)/(b)/(e) are live-network + cross-table joins/aggregations building
derived tables — that promotion logic belongs in dbt, not in an ingestion
landing pipeline, and is intentionally NOT carried over here. What this port
faithfully preserves is the bronze *landing transformation* (step d): given the
cached Google Civic JSON payloads the legacy loader already writes under
``data/cache/google_civic/``, reproduce — verbatim where the logic is pure —
the row shaping done by ``_persist_voterinfo_bronze`` (election + candidacy +
ballot_measure rows from a voterInfoQuery payload) and the election-snapshot
insert (election rows from the elections.electionQuery snapshot), and land them
into ``bronze.bronze_elections_scraped``.

Data source: Google Civic Information API (elections / voterInfo), cached by the
legacy loader into:
  * data/cache/google_civic/elections/upcoming_elections_*.json  (snapshot)
  * data/cache/google_civic/<STATE>/<segment>/<folder>/<jid>_voterinfo_<eid>_*.json

Usage:
    python -m ingestion.google_civic.officials
    python ingestion/google_civic/officials.py --truncate
    python ingestion/google_civic/officials.py \\
        --cache-dir data/cache/google_civic --states MA,GA --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded psycopg2 + NEON_DATABASE_URL_DEV / localhost connection).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any, AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/google_civic")

# Preserved verbatim from the legacy loader.
DEFAULT_PRIORITY_STATES = ("AL", "GA", "IN", "MA", "WA", "WI")
DEFAULT_INCLUDE_TYPES = ("municipality", "county")
_UUID_NS = uuid.UUID("b1ed9a39-f6a5-44f7-8e4b-5e0f58d4c0da")
GOOGLE_SOURCE_NAME = "bronze_election_google"
BALLOTPEDIA_SOURCE_NAME = "bronze_election_ballotpedia"


# ---------------------------------------------------------------------------
# Pure helpers preserved verbatim from the legacy loader.
# ---------------------------------------------------------------------------
def _stable_id(prefix: str, key: str) -> str:
    return f"ocd-{prefix}/{uuid.uuid5(_UUID_NS, key)}"


def _stable_key(*parts: str | None) -> str:
    return "|".join((p or "").strip().lower() for p in parts)


def _state_code_from_ocd_id(ocd_id: str | None) -> str | None:
    if not ocd_id:
        return None
    for part in ocd_id.split("/"):
        if part.startswith("state:") and len(part) == len("state:xx"):
            return part.split(":", 1)[1].upper()
    return None


def _parse_election_day(value: Any) -> date:
    if isinstance(value, date):
        return value
    text_value = str(value or "").strip()
    if not text_value:
        return date.today()
    try:
        return date.fromisoformat(text_value[:10])
    except ValueError:
        return date.today()


# ---------------------------------------------------------------------------
# Bronze row shaping preserved from the legacy loader's insert helpers
# (_insert_bronze_row / _insert_bronze_ballot_measure_row /
# _persist_voterinfo_bronze) and the election-snapshot insert in main().
# Each returns a fully-populated dict matching the bronze_elections_scraped
# columns; missing per-record columns default to None.
# ---------------------------------------------------------------------------
_BRONZE_COLUMNS = (
    "scrape_batch_id",
    "record_type",
    "ocd_id",
    "election_name",
    "election_date",
    "election_type",
    "election_status",
    "ocd_jurisdiction_id",
    "state_code",
    "jurisdiction_id",
    "candidate_name",
    "candidate_party",
    "candidate_post",
    "candidate_status",
    "measure_title",
    "measure_outcome",
    "source_url",
    "source_name",
    "raw_row",
)


def _bronze_record(
    *,
    scrape_batch_id: str,
    record_type: str,
    ocd_id: str,
    source_name: str,
    raw_row: dict[str, Any],
    election_name: str | None = None,
    election_date: date | None = None,
    election_type: str | None = None,
    election_status: str | None = None,
    ocd_jurisdiction_id: str | None = None,
    state_code: str | None = None,
    jurisdiction_id: str | None = None,
    candidate_name: str | None = None,
    candidate_party: str | None = None,
    candidate_post: str | None = None,
    candidate_status: str | None = None,
    measure_title: str | None = None,
    measure_outcome: str | None = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Assemble one bronze.bronze_elections_scraped column dict (record-type agnostic)."""
    return {
        "scrape_batch_id": scrape_batch_id,
        "record_type": record_type,
        "ocd_id": ocd_id,
        "election_name": election_name,
        "election_date": election_date,
        "election_type": election_type,
        "election_status": election_status,
        "ocd_jurisdiction_id": ocd_jurisdiction_id,
        "state_code": state_code,
        "jurisdiction_id": jurisdiction_id,
        "candidate_name": candidate_name,
        "candidate_party": candidate_party,
        "candidate_post": candidate_post,
        "candidate_status": candidate_status,
        "measure_title": measure_title,
        "measure_outcome": measure_outcome,
        "source_url": source_url,
        "source_name": source_name,
        "raw_row": raw_row,
    }


def election_snapshot_records(
    *,
    scrape_batch_id: str,
    elections: list[dict[str, Any]],
    source_url: str | None = None,
) -> list[dict[str, Any]]:
    """Bronze 'election' rows from an elections.electionQuery snapshot.

    Mirrors the upcoming-elections insert loop in the legacy loader's main().
    """
    records: list[dict[str, Any]] = []
    for election in elections:
        if not isinstance(election, dict):
            election = {"payload": election}
        civic_id = str(election.get("id") or "")
        division_id = election.get("ocdDivisionId") or "ocd-division/country:us"
        state_code = _state_code_from_ocd_id(division_id)
        election_id = _stable_id(
            "election",
            _stable_key("google_civic", civic_id, election.get("name"), election.get("electionDay")),
        )
        records.append(
            _bronze_record(
                scrape_batch_id=scrape_batch_id,
                record_type="election",
                ocd_id=election_id,
                election_name=election.get("name") or "Google Civic election",
                election_date=_parse_election_day(election.get("electionDay")),
                election_type="civic_calendar",
                election_status="confirmed",
                ocd_jurisdiction_id=division_id,
                state_code=state_code,
                jurisdiction_id=division_id,
                source_url=source_url,
                source_name=GOOGLE_SOURCE_NAME,
                raw_row=election,
            )
        )
    return records


def voterinfo_records(
    *,
    scrape_batch_id: str,
    voter_info: dict[str, Any],
    state_code: str,
    jurisdiction_id: str,
    division_id: str,
    civic_address: str,
    source_url: str | None = None,
) -> list[dict[str, Any]]:
    """Bronze rows from a voterInfoQuery payload (election + candidacy + ballot_measure).

    Faithful port of _persist_voterinfo_bronze: the live civic_voterinfo_url()
    call is replaced by the source_url already captured in the cached payload.
    """
    election_meta = voter_info.get("election") or {}
    civic_election_id = str(voter_info.get("election_id") or election_meta.get("id") or "")
    election_name = election_meta.get("name") or f"Google Civic voter info ({civic_election_id or 'unknown'})"
    election_day = _parse_election_day(election_meta.get("electionDay"))
    src_url = source_url or voter_info.get("source_url")
    election_row_id = _stable_id(
        "election",
        _stable_key(GOOGLE_SOURCE_NAME, civic_election_id, jurisdiction_id, civic_address, election_day.isoformat()),
    )
    records: list[dict[str, Any]] = [
        _bronze_record(
            scrape_batch_id=scrape_batch_id,
            record_type="election",
            ocd_id=election_row_id,
            election_name=election_name,
            election_date=election_day,
            election_type="civic_voterinfo",
            election_status="confirmed",
            ocd_jurisdiction_id=division_id,
            state_code=state_code,
            jurisdiction_id=jurisdiction_id,
            source_url=src_url,
            source_name=GOOGLE_SOURCE_NAME,
            raw_row={
                "source": GOOGLE_SOURCE_NAME,
                "address": civic_address,
                "jurisdiction_id": jurisdiction_id,
                "division_id": division_id,
                "election": election_meta,
                "polling_locations": voter_info.get("polling_locations") or [],
                "early_vote_sites": voter_info.get("early_vote_sites") or [],
                "drop_off_locations": voter_info.get("drop_off_locations") or [],
                "state_officials": voter_info.get("state") or [],
                "normalized_input": voter_info.get("normalizedInput"),
            },
        )
    ]

    for contest in voter_info.get("contests") or []:
        if not isinstance(contest, dict):
            continue
        contest_type = (contest.get("type") or "").strip()
        office_name = contest.get("office") or contest.get("district") or contest.get("level") or "Office"
        if contest_type.lower() == "referendum" or contest.get("referendumTitle"):
            measure_title = (
                contest.get("referendumTitle")
                or contest.get("referendumBrief")
                or contest.get("ballotTitle")
                or "Referendum"
            )
            measure_id = _stable_id(
                "ballotmeasure",
                _stable_key(GOOGLE_SOURCE_NAME, jurisdiction_id, civic_election_id, measure_title),
            )
            records.append(
                _bronze_record(
                    scrape_batch_id=scrape_batch_id,
                    record_type="ballot_measure",
                    ocd_id=measure_id,
                    state_code=state_code,
                    jurisdiction_id=jurisdiction_id,
                    ocd_jurisdiction_id=division_id,
                    measure_title=measure_title,
                    measure_outcome=None,
                    source_url=src_url,
                    source_name=GOOGLE_SOURCE_NAME,
                    raw_row={**contest, "jurisdiction_id": jurisdiction_id, "election_id": civic_election_id},
                )
            )
            continue

        for candidate in contest.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            person_name = candidate.get("name") or "Unknown candidate"
            candidacy_id = _stable_id(
                "candidacy",
                _stable_key(GOOGLE_SOURCE_NAME, election_row_id, office_name, person_name, civic_election_id),
            )
            records.append(
                _bronze_record(
                    scrape_batch_id=scrape_batch_id,
                    record_type="candidacy",
                    ocd_id=candidacy_id,
                    election_name=election_name,
                    election_date=election_day,
                    election_type="civic_voterinfo",
                    election_status="confirmed",
                    ocd_jurisdiction_id=division_id,
                    state_code=state_code,
                    jurisdiction_id=jurisdiction_id,
                    candidate_name=person_name,
                    candidate_party=candidate.get("party"),
                    candidate_post=office_name,
                    candidate_status=contest_type or "candidate",
                    source_url=(candidate.get("candidateUrl") or candidate.get("url") or src_url),
                    source_name=GOOGLE_SOURCE_NAME,
                    raw_row={
                        "source": GOOGLE_SOURCE_NAME,
                        "contest": contest,
                        "candidate": candidate,
                        "jurisdiction_id": jurisdiction_id,
                        "division_id": division_id,
                        "election_id": civic_election_id,
                    },
                )
            )

    return records


# ---------------------------------------------------------------------------
# Cache-file discovery.
# ---------------------------------------------------------------------------
def find_snapshot_files(cache_dir: Path) -> list[Path]:
    """elections.electionQuery snapshots under <cache>/elections/."""
    return sorted((cache_dir / "elections").glob("upcoming_elections_*.json"))


def find_voterinfo_files(cache_dir: Path, states: tuple[str, ...] = ()) -> list[Path]:
    """Per-jurisdiction voterInfoQuery cache payloads (optionally state-filtered)."""
    files: list[Path] = []
    if states:
        bases = [cache_dir / s.upper() for s in states]
    else:
        bases = [cache_dir]
    for base in bases:
        if not base.exists():
            continue
        files.extend(base.rglob("*_voterinfo_*.json"))
    # Exclude error sidecars written for failed voterInfoQuery calls.
    files = [p for p in files if "_error" not in p.name]
    return sorted(files)


def discover_cache_files(cache_dir: Path, states: tuple[str, ...] = ()) -> list[tuple[str, Path]]:
    """Return (kind, path) tuples for all relevant cached Google Civic payloads.

    Raises FileNotFoundError when the cache directory is absent (mirrors the
    raise-when-missing discovery convention of the template loaders).
    """
    if not cache_dir.exists():
        raise FileNotFoundError(
            f"Google Civic cache dir not found: {cache_dir}. "
            "Run the legacy fetch (load_google_civic_officials_to_c1) first."
        )
    found: list[tuple[str, Path]] = []
    found.extend(("snapshot", p) for p in find_snapshot_files(cache_dir))
    found.extend(("voterinfo", p) for p in find_voterinfo_files(cache_dir, states))
    return found


class GoogleCivicOfficialsRow(RawRow):
    """One bronze.bronze_elections_scraped row, validated before insert.

    Column types/nullability mirror migration 047_create_bronze_elections_scraped.
    record_type is constrained to the same CHECK set as the DB. raw_row maps to a
    JSONB column and is JSON-cast at insert.
    """

    scrape_batch_id: str = Field(min_length=1)
    record_type: str = Field(pattern=r"^(election|candidacy|ballot_measure)$")
    ocd_id: str | None = None
    election_name: str | None = None
    election_date: date | None = None
    election_type: str | None = None
    election_status: str | None = None
    ocd_jurisdiction_id: str | None = None
    state_code: str | None = Field(default=None, max_length=2)
    jurisdiction_id: str | None = None
    candidate_name: str | None = None
    candidate_party: str | None = None
    candidate_post: str | None = None
    candidate_status: str | None = None
    measure_title: str | None = None
    measure_outcome: str | None = None
    source_url: str | None = None
    source_name: str | None = None
    raw_row: dict[str, Any] | None = None


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_elections_scraped (
        id                          BIGSERIAL PRIMARY KEY,
        scrape_batch_id             UUID NOT NULL,
        record_type                 TEXT NOT NULL CHECK (record_type IN ('election', 'candidacy', 'ballot_measure')),
        ocd_id                      TEXT,
        election_name               TEXT,
        election_date               DATE,
        election_type               TEXT,
        election_status             TEXT,
        ocd_jurisdiction_id         TEXT,
        state_code                  CHAR(2),
        jurisdiction_id             TEXT,
        candidate_name              TEXT,
        candidate_party             TEXT,
        candidate_post              TEXT,
        candidate_status            TEXT,
        candidate_vote_count        BIGINT,
        candidate_vote_percent      DOUBLE PRECISION,
        measure_title               TEXT,
        measure_summary             TEXT,
        measure_classification      TEXT,
        measure_yes_count           BIGINT,
        measure_no_count            BIGINT,
        measure_outcome             TEXT,
        source_url                  TEXT,
        source_name                 TEXT,
        raw_row                     JSONB NOT NULL DEFAULT '{}'::JSONB,
        scraped_at                  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        loaded_at                   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bronze_elections_scraped_record_type ON bronze.bronze_elections_scraped (record_type)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_elections_scraped_state ON bronze.bronze_elections_scraped (state_code)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_elections_scraped_jurisdiction ON bronze.bronze_elections_scraped (jurisdiction_id)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_elections_scraped_ocd_jur ON bronze.bronze_elections_scraped (ocd_jurisdiction_id)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_elections_scraped_date ON bronze.bronze_elections_scraped (election_date)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_elections_scraped_batch ON bronze.bronze_elections_scraped (scrape_batch_id)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_elections_scraped_ocd_id ON bronze.bronze_elections_scraped (ocd_id)"),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_elections_scraped")

_INSERT_COLUMNS = ", ".join(_BRONZE_COLUMNS)
_INSERT_PLACEHOLDERS = ", ".join(
    "CAST(:scrape_batch_id AS UUID)" if c == "scrape_batch_id"
    else "CAST(:raw_row AS JSONB)" if c == "raw_row"
    else f":{c}"
    for c in _BRONZE_COLUMNS
)

_INSERT_SQL = text(
    f"""
    INSERT INTO bronze.bronze_elections_scraped
        ({_INSERT_COLUMNS})
    VALUES
        ({_INSERT_PLACEHOLDERS})
    """
)


class GoogleCivicOfficialsPipeline(DataSourcePipeline[GoogleCivicOfficialsRow]):
    source = "google_civic_officials"
    batch_size = 1_000
    row_schema = GoogleCivicOfficialsRow

    def __init__(
        self,
        *,
        path: Path | None = None,
        cache_dir: Path | None = None,
        states: tuple[str, ...] = (),
        scrape_batch_id: str | None = None,
        limit: int | None = None,
    ):
        self._path = path
        self._cache_dir = cache_dir or CACHE_DIR
        self._states = states
        # Stable per-run batch id, as the legacy loader allocated one uuid4() per run.
        self._scrape_batch_id = scrape_batch_id or str(uuid.uuid4())
        self._limit = limit

    def _discover(self) -> list[tuple[str, Path]]:
        if self._path is not None:
            # Infer kind from filename; default to voterInfo payload shape.
            kind = "snapshot" if self._path.name.startswith("upcoming_elections_") else "voterinfo"
            return [(kind, self._path)]
        return discover_cache_files(self._cache_dir, self._states)

    def _records_for_file(self, kind: str, payload: Any) -> list[dict[str, Any]]:
        if kind == "snapshot":
            elections = payload.get("elections") if isinstance(payload, dict) else None
            return election_snapshot_records(
                scrape_batch_id=self._scrape_batch_id,
                elections=list(elections or []),
                source_url=payload.get("source_url") if isinstance(payload, dict) else None,
            )
        # voterinfo
        if not isinstance(payload, dict):
            return []
        state_code = (payload.get("state_code") or "").upper()
        jurisdiction_id = payload.get("jurisdiction_id") or ""
        division_id = (
            payload.get("resolved_division_id")
            or payload.get("division_id")
            or jurisdiction_id
        )
        civic_address = payload.get("address") or ""
        return voterinfo_records(
            scrape_batch_id=self._scrape_batch_id,
            voter_info=payload,
            state_code=state_code,
            jurisdiction_id=jurisdiction_id,
            division_id=division_id,
            civic_address=civic_address,
            source_url=payload.get("source_url"),
        )

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        emitted = 0
        for kind, path in self._discover():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for record in self._records_for_file(kind, payload):
                if self._limit is not None and emitted >= self._limit:
                    return
                yield {
                    "source": self.source,
                    "source_version": path.stem,
                    "natural_key": f"{record['scrape_batch_id']}:{record['record_type']}:{record['ocd_id']}",
                    **record,
                }
                emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[GoogleCivicOfficialsRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                **{c: getattr(r, c) for c in _BRONZE_COLUMNS if c != "raw_row"},
                "raw_row": json.dumps(r.raw_row or {}, default=str),
            }
            for r in rows
        ]
        await session.execute(_INSERT_SQL, params)


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
        description="Land cached Google Civic elections/voterInfo payloads into bronze.bronze_elections_scraped"
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=CACHE_DIR,
        help=f"Google Civic cache directory (default: {CACHE_DIR})",
    )
    parser.add_argument(
        "--file", type=Path, help="Path to a single cached payload (snapshot or voterInfo JSON)",
    )
    parser.add_argument(
        "--states", default=",".join(DEFAULT_PRIORITY_STATES),
        help=f"Comma-separated state codes to filter voterInfo payloads (default: {','.join(DEFAULT_PRIORITY_STATES)})",
    )
    parser.add_argument("--limit", type=int, help="Load only the first N records")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip()) if args.states else ()
    pipeline = GoogleCivicOfficialsPipeline(
        path=args.file,
        cache_dir=args.cache_dir,
        states=states,
        limit=args.limit,
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
