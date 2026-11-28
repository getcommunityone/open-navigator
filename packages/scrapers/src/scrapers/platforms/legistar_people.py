"""Read who sits on which body from the Legistar Web API (#1443).

Legistar clients publish their bodies and their members' office records through the same public Web API the
meeting reader uses (#536):

- ``https://webapi.legistar.com/v1/<client>/bodies``: each body (council, committees, boards) with its type and
  whether it is active;
- ``https://webapi.legistar.com/v1/<client>/officerecords``: one record per person per body seat, with the title
  ("Mayor", "Chair", "Council Member") and start/end dates.

Only current records are read (end date today or later, or none). Kept per record: the person's Legistar id and full
name, the body, the title and member type, and the dates. The record's email is a public office address, but no
feature needs it, so it is not stored.

Politeness (AGENTS.md, "Scraping"): every request goes through :class:`scrapers.platforms.http.PoliteClient`
(robots.txt honoured, the open-navigator User-Agent, at least ``--min-interval`` seconds between requests, and a
403/429 or challenge page stops that portal; it is recorded as ``blocked``, never retried with another identity).
A client that answers with Legistar's "not set up" message is recorded as ``not_configured``.

Writes (local warehouse only, never Neon), idempotent upserts:

- ``bronze.bronze_legistar_body`` PK (portal, body_id)
- ``bronze.bronze_legistar_office_record`` PK (portal, office_record_id)
- ``bronze.bronze_legistar_people_portal`` PK (portal): status of the last read

Usage::

    python -m scrapers.platforms.legistar_people --portals-from-warehouse --apply   # every portal we read meetings from
    python -m scrapers.platforms.legistar_people --client charlottenc                # one client, dry run
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional, Sequence
from urllib.parse import quote

from loguru import logger

from scrapers.platforms.http import Blocked, PlatformFetchError, PoliteClient, RobotsDisallowed
from scrapers.platforms.legistar import API_BASE, PAGE_SIZE, classify_error

BODY_TABLE = "bronze.bronze_legistar_body"
RECORD_TABLE = "bronze.bronze_legistar_office_record"
PORTAL_TABLE = "bronze.bronze_legistar_people_portal"

DDL = f"""
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS {BODY_TABLE} (
    portal           text        NOT NULL,
    body_id          integer     NOT NULL,
    jurisdiction_id  text,
    body_name        text        NOT NULL,
    body_type_name   text,
    active_flag      boolean,
    member_count     integer,
    fetched_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT bronze_legistar_body_pkey PRIMARY KEY (portal, body_id)
);

CREATE TABLE IF NOT EXISTS {RECORD_TABLE} (
    portal            text        NOT NULL,
    office_record_id  integer     NOT NULL,
    jurisdiction_id   text,
    person_id         integer,
    full_name         text        NOT NULL,
    body_id           integer,
    body_name         text,
    title             text,
    member_type       text,
    start_date        date,
    end_date          date,
    fetched_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT bronze_legistar_office_record_pkey PRIMARY KEY (portal, office_record_id)
);

CREATE TABLE IF NOT EXISTS {PORTAL_TABLE} (
    portal           text        NOT NULL PRIMARY KEY,
    jurisdiction_id  text,
    status           text        NOT NULL,
    message          text,
    bodies           integer     NOT NULL DEFAULT 0,
    office_records   integer     NOT NULL DEFAULT 0,
    fetched_at       timestamptz NOT NULL DEFAULT now()
);
"""


# --------------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------------


def bodies_url(client: str) -> str:
    return f"{API_BASE}/{client}/bodies"


def office_records_url(client: str, today: date, top: int = PAGE_SIZE, skip: int = 0) -> str:
    cond = f"OfficeRecordEndDate ge datetime'{today.isoformat()}'"
    flt = quote(cond, safe="")
    order = quote("OfficeRecordId", safe="")
    return f"{API_BASE}/{client}/officerecords?$filter={flt}&$orderby={order}&$top={top}&$skip={skip}"


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = " ".join(str(value).split())
    return s or None


def _date(value: Any) -> Optional[date]:
    s = _clean(value)
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:19]).date()
    except ValueError:
        return None


def _int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_body(item: dict[str, Any]) -> Optional[dict[str, Any]]:
    body_id, name = _int(item.get("BodyId")), _clean(item.get("BodyName"))
    if body_id is None or not name:
        return None
    return {
        "body_id": body_id,
        "body_name": name,
        "body_type_name": _clean(item.get("BodyTypeName")),
        "active_flag": None if item.get("BodyActiveFlag") is None else bool(item.get("BodyActiveFlag")),
        "member_count": _int(item.get("BodyNumberOfMembers")),
    }


def parse_office_record(item: dict[str, Any]) -> Optional[dict[str, Any]]:
    """One office record, or None when it has no id or no name. The email is deliberately not kept."""
    rec_id = _int(item.get("OfficeRecordId"))
    name = _clean(item.get("OfficeRecordFullName")) or _clean(
        f"{item.get('OfficeRecordFirstName') or ''} {item.get('OfficeRecordLastName') or ''}"
    )
    if rec_id is None or not name:
        return None
    return {
        "office_record_id": rec_id,
        "person_id": _int(item.get("OfficeRecordPersonId")),
        "full_name": name,
        "body_id": _int(item.get("OfficeRecordBodyId")),
        "body_name": _clean(item.get("OfficeRecordBodyName")),
        "title": _clean(item.get("OfficeRecordTitle")),
        "member_type": _clean(item.get("OfficeRecordMemberType")),
        "start_date": _date(item.get("OfficeRecordStartDate")),
        "end_date": _date(item.get("OfficeRecordEndDate")),
    }


@dataclass
class PeopleResult:
    portal: str
    jurisdiction_id: Optional[str]
    status: str = "ok"
    message: Optional[str] = None
    bodies: list[dict[str, Any]] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)


# --------------------------------------------------------------------------------
# Fetch
# --------------------------------------------------------------------------------


async def _get_json(http: PoliteClient, url: str) -> Any:
    resp = await http.get(url, allow_status=(400, 500))
    payload = resp.json()
    err = classify_error(payload)
    if err:
        status, msg = err
        raise PlatformFetchError(f"{status}: {msg}")
    return payload


async def read_portal(
    http: PoliteClient, client: str, jurisdiction_id: Optional[str], *, today: Optional[date] = None, max_pages: int = 20
) -> PeopleResult:
    res = PeopleResult(client, jurisdiction_id)
    today = today or date.today()
    try:
        payload = await _get_json(http, bodies_url(client))
        res.bodies = [b for b in (parse_body(it) for it in payload or []) if b]
        for page in range(max_pages):
            items = await _get_json(http, office_records_url(client, today, skip=page * PAGE_SIZE))
            res.records += [r for r in (parse_office_record(it) for it in items or []) if r]
            if len(items or []) < PAGE_SIZE:
                break
    except RobotsDisallowed as exc:
        res.status, res.message = "robots_disallowed", str(exc)
    except Blocked as exc:
        res.status, res.message = "blocked", str(exc)
    except PlatformFetchError as exc:
        msg = str(exc)
        res.status = "not_configured" if msg.startswith("not_configured") else "error"
        res.message = msg[:500]
    except ValueError as exc:  # not JSON
        res.status, res.message = "error", f"not JSON: {exc}"[:500]
    return res


# --------------------------------------------------------------------------------
# Store
# --------------------------------------------------------------------------------


def warehouse_portals(conn: Any) -> list[tuple[str, Optional[str]]]:
    """Legistar clients we already read meetings from, with their jurisdiction."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT portal, jurisdiction_id FROM bronze.bronze_platform_portal "
            "WHERE platform = 'legistar' AND status IN ('ok', 'empty') ORDER BY portal"
        )
        return [(p, j) for p, j in cur.fetchall()]


def write_result(conn: Any, res: PeopleResult) -> None:
    import psycopg2.extras

    now = datetime.now(timezone.utc)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            if res.bodies:
                psycopg2.extras.execute_values(
                    cur,
                    f"""INSERT INTO {BODY_TABLE} (portal, body_id, jurisdiction_id, body_name, body_type_name,
                        active_flag, member_count, fetched_at) VALUES %s
                        ON CONFLICT (portal, body_id) DO UPDATE SET jurisdiction_id = EXCLUDED.jurisdiction_id,
                        body_name = EXCLUDED.body_name, body_type_name = EXCLUDED.body_type_name,
                        active_flag = EXCLUDED.active_flag, member_count = EXCLUDED.member_count,
                        fetched_at = EXCLUDED.fetched_at""",
                    [(res.portal, b["body_id"], res.jurisdiction_id, b["body_name"], b["body_type_name"],
                      b["active_flag"], b["member_count"], now) for b in res.bodies],
                )
            if res.status == "ok":
                # The current set replaces the last one: a record no longer current must not linger as a member.
                cur.execute(f"DELETE FROM {RECORD_TABLE} WHERE portal = %s", (res.portal,))
            if res.records:
                psycopg2.extras.execute_values(
                    cur,
                    f"""INSERT INTO {RECORD_TABLE} (portal, office_record_id, jurisdiction_id, person_id, full_name,
                        body_id, body_name, title, member_type, start_date, end_date, fetched_at) VALUES %s
                        ON CONFLICT (portal, office_record_id) DO NOTHING""",
                    [(res.portal, r["office_record_id"], res.jurisdiction_id, r["person_id"], r["full_name"],
                      r["body_id"], r["body_name"], r["title"], r["member_type"], r["start_date"], r["end_date"], now)
                     for r in res.records],
                )
            cur.execute(
                f"""INSERT INTO {PORTAL_TABLE} (portal, jurisdiction_id, status, message, bodies, office_records,
                    fetched_at) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (portal) DO UPDATE SET jurisdiction_id = EXCLUDED.jurisdiction_id,
                    status = EXCLUDED.status, message = EXCLUDED.message, bodies = EXCLUDED.bodies,
                    office_records = EXCLUDED.office_records, fetched_at = EXCLUDED.fetched_at""",
                (res.portal, res.jurisdiction_id, res.status, res.message, len(res.bodies), len(res.records), now),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = True


# --------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------


async def run(targets: Sequence[tuple[str, Optional[str]]], *, min_interval: float, conn: Any = None) -> list[PeopleResult]:
    results: list[PeopleResult] = []
    async with PoliteClient(min_interval_s=min_interval, use_vpn_bypass=False) as http:
        for client, jid in targets:
            res = await read_portal(http, client, jid)
            logger.info("{:28} {:18} bodies={:<4} office_records={}", client, res.status, len(res.bodies), len(res.records))
            if conn is not None:
                write_result(conn, res)
            results.append(res)
    return results


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--client", action="append", help="Legistar client slug (repeatable)")
    p.add_argument("--jurisdiction-id", help="jurisdiction for --client")
    p.add_argument("--portals-from-warehouse", action="store_true", help="every Legistar portal in bronze_platform_portal")
    p.add_argument("--min-interval", type=float, default=1.0, help="seconds between requests to the API host")
    p.add_argument("--apply", action="store_true", help="write to the local warehouse bronze tables")
    p.add_argument("--dsn", help="warehouse DSN (default: local warehouse, never Neon)")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    conn = None
    if args.apply or args.portals_from_warehouse:
        import psycopg2

        from scrapers.discovery.survey_meeting_sources import warehouse_dsn

        conn = psycopg2.connect(args.dsn or warehouse_dsn())
        conn.autocommit = True
        if args.apply:
            with conn.cursor() as cur:
                cur.execute(DDL)
    targets: list[tuple[str, Optional[str]]] = [(c, args.jurisdiction_id) for c in args.client or []]
    if args.portals_from_warehouse and conn is not None:
        targets += [t for t in warehouse_portals(conn) if t[0] not in {c for c, _ in targets}]
    results = asyncio.run(run(targets, min_interval=args.min_interval, conn=conn if args.apply else None))
    summary: dict[str, Any] = {}
    for r in results:
        summary[r.status] = summary.get(r.status, 0) + 1
    logger.success("Legistar people: {} portals {}; {} office records", len(results), json.dumps(summary),
                   sum(len(r.records) for r in results))
    if conn is not None:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
