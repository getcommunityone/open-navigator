"""Load USAspending assistance awards to local governments into bronze.

    python -m ingestion.usaspending.load_awards --fy-start 2019 --fy-end 2026
    python -m ingestion.usaspending.load_awards --aln 14.218 --fy-start 2023 --fy-end 2023
    python -m ingestion.usaspending.load_awards --dry-run --limit 5

Source: USAspending.gov API (public domain, no key). Assistance types 02-05 (block /
formula / project grants, cooperative agreements); recipient type ``local_government``
(city, county, township, special district). The API returns one row per award with the
award's CURRENT total obligation, so the loader upserts by ``generated_unique_award_id``
(an award seen in several action-date windows is stored once). Bronze keeps source
fidelity; typing and the jurisdiction match happen in dbt.

Not yet loaded: state-government recipients (their own volume class) and the bulk
award archives (https://www.usaspending.gov/download_center/award_data_archive), which
the same bronze table can take later; see the decision page.
"""

from __future__ import annotations

import argparse
import calendar
from datetime import date
from typing import Any

from loguru import logger
from sqlalchemy import text

from ..pgutil import get_engine
from .client import RateLimited, UsaSpendingClient

TABLE = "bronze.bronze_usaspending_award"
DATA_SOURCE = "USAspending.gov API v2"

_DDL = [
    "CREATE SCHEMA IF NOT EXISTS bronze",
    f"""CREATE TABLE IF NOT EXISTS {TABLE} (
        generated_unique_award_id TEXT PRIMARY KEY,
        award_id_fain       TEXT,
        recipient_name      TEXT,
        recipient_uei       TEXT,
        recipient_type      TEXT,
        aln                 TEXT,
        aln_title           TEXT,
        aln_all             TEXT,
        awarding_agency     TEXT,
        funding_agency      TEXT,
        award_type          TEXT,
        total_obligation    NUMERIC(18,2),
        total_outlays       NUMERIC(18,2),
        period_start        DATE,
        period_end          DATE,
        description         TEXT,
        pop_state_code      TEXT,
        pop_state           TEXT,
        pop_county          TEXT,
        pop_city            TEXT,
        recipient_state_code TEXT,
        recipient_city      TEXT,
        recipient_county    TEXT,
        source_updated_at   TIMESTAMP,
        data_source         TEXT,
        ingestion_date      TIMESTAMP DEFAULT NOW()
    )""",
    f"CREATE INDEX IF NOT EXISTS idx_bus_award_aln ON {TABLE}(aln)",
    f"CREATE INDEX IF NOT EXISTS idx_bus_award_state ON {TABLE}(pop_state_code)",
]

_COLS = [
    "generated_unique_award_id", "award_id_fain", "recipient_name", "recipient_uei",
    "recipient_type", "aln", "aln_title", "aln_all", "awarding_agency", "funding_agency",
    "award_type", "total_obligation", "total_outlays", "period_start", "period_end",
    "description", "pop_state_code", "pop_state", "pop_county", "pop_city",
    "recipient_state_code", "recipient_city", "recipient_county", "source_updated_at",
    "data_source",
]
_UPSERT = text(
    f"INSERT INTO {TABLE} ({', '.join(_COLS)}) VALUES ({', '.join(':' + c for c in _COLS)}) "
    f"ON CONFLICT (generated_unique_award_id) DO UPDATE SET "
    + ", ".join(f"{c}=EXCLUDED.{c}" for c in _COLS[1:])
    + ", ingestion_date = NOW()"
)


def _s(v: Any) -> str | None:
    if v is None:
        return None
    v = str(v).strip()
    return v or None


def _date(v: Any) -> str | None:
    s = _s(v)
    return s[:10] if s else None


def to_record(hit: dict[str, Any], recipient_type: str) -> dict[str, Any] | None:
    """One API result -> bronze row. Returns None when the award has no stable id."""
    gid = _s(hit.get("generated_internal_id"))
    if not gid:
        return None
    alns = hit.get("Assistance Listings") or []
    first = alns[0] if alns else {}
    pop = hit.get("Primary Place of Performance") or {}
    loc = hit.get("Recipient Location") or {}
    return {
        "generated_unique_award_id": gid,
        "award_id_fain": _s(hit.get("Award ID")),
        "recipient_name": _s(hit.get("Recipient Name")),
        "recipient_uei": _s(hit.get("Recipient UEI")),
        "recipient_type": recipient_type,
        "aln": _s(first.get("cfda_number")),
        "aln_title": _s(first.get("cfda_program_title")),
        "aln_all": ",".join(a.get("cfda_number", "") for a in alns) or None,
        "awarding_agency": _s(hit.get("Awarding Agency")),
        "funding_agency": _s(hit.get("Funding Agency")),
        "award_type": _s(hit.get("Award Type")),
        "total_obligation": hit.get("Award Amount"),
        "total_outlays": hit.get("Total Outlays"),
        "period_start": _date(hit.get("Start Date")),
        "period_end": _date(hit.get("End Date")),
        "description": _s(hit.get("Description")),
        "pop_state_code": _s(pop.get("state_code")),
        "pop_state": _s(pop.get("state_name")),
        "pop_county": _s(pop.get("county_name")),
        "pop_city": _s(pop.get("city_name")),
        "recipient_state_code": _s(loc.get("state_code")),
        "recipient_city": _s(loc.get("city_name")),
        "recipient_county": _s(loc.get("county_name")),
        "source_updated_at": _s(hit.get("Last Modified Date")),
        "data_source": DATA_SOURCE,
    }


def month_windows(fy_start: int, fy_end: int) -> list[tuple[date, date]]:
    """Calendar-month windows covering federal fiscal years fy_start..fy_end (Oct-Sep)."""
    out: list[tuple[date, date]] = []
    y, m = fy_start - 1, 10
    while (y, m) <= (fy_end, 9):
        out.append((date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Load USAspending local-government assistance awards")
    p.add_argument("--fy-start", type=int, default=2019)
    p.add_argument("--fy-end", type=int, default=2026)
    p.add_argument("--aln", help="Restrict to one Assistance Listing Number, e.g. 14.218")
    p.add_argument("--recipient-type", default="local_government")
    p.add_argument("--resume-from", help="Skip months before YYYY-MM (restart after an interruption)")
    p.add_argument("--limit", type=int, help="Stop after N awards")
    p.add_argument("--batch", type=int, default=500)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)

    client = UsaSpendingClient()
    engine = None if a.dry_run else get_engine()
    if engine is not None:
        with engine.begin() as cx:
            for stmt in _DDL:
                cx.execute(text(stmt))

    buf: list[dict[str, Any]] = []
    total = 0

    def flush() -> None:
        nonlocal buf
        if buf and engine is not None:
            with engine.begin() as cx:
                cx.execute(_UPSERT, buf)
        buf = []

    try:
        for start, end in month_windows(a.fy_start, a.fy_end):
            if a.resume_from and start.isoformat()[:7] < a.resume_from:
                continue
            for hit in client.iter_awards(start, end, a.recipient_type, a.aln):
                rec = to_record(hit, a.recipient_type)
                if rec is None:
                    continue
                total += 1
                if a.dry_run:
                    logger.info("{} {} {}", rec["recipient_name"], rec["aln"], rec["total_obligation"])
                else:
                    buf.append(rec)
                    if len(buf) >= a.batch:
                        flush()
                if a.limit and total >= a.limit:
                    flush()
                    logger.success("Stopped at --limit ({:,} awards)", total)
                    return 0
            flush()
    except RateLimited as exc:
        flush()
        logger.error("{}; loaded {:,} so far", exc, total)
        return 2
    logger.success("Loaded {:,} awards into {}", total, TABLE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
