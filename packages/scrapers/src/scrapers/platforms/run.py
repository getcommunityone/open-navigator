"""Read Granicus and Legistar portals into bronze (#536).

Reads the portals of the data center governments from the #460 survey, then finds
more Legistar portals by URL pattern (see :mod:`scrapers.platforms.discover`), and
lands every meeting in ``bronze.bronze_platform_meeting`` (captions in
``bronze_platform_meeting_caption``, portal statuses in ``bronze_platform_portal``).

Videos without captions are marked ``transcription_status = 'queued_whisper'``; they
are transcribed later by Colab Whisper (#489), never here. ``--export-whisper-queue``
writes that queue as a TSV (``platform, meeting_uid, meeting_date, video_url``).

Usage::

    python -m scrapers.platforms.run --data-center --pattern-target 20            # dry run
    python -m scrapers.platforms.run --data-center --pattern-target 20 --apply
    python -m scrapers.platforms.run --legistar-client dakota --apply
    python -m scrapers.platforms.run --export-whisper-queue data/cache/platform_meetings/whisper_queue.tsv

Free: public pages and the public Legistar Web API only. Local warehouse only.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

from loguru import logger

from scrapers.platforms import granicus, legistar
from scrapers.platforms.discover import (
    PortalTarget,
    load_candidates,
    load_survey_rows,
    probe_legistar,
    survey_targets,
)
from scrapers.platforms.http import PoliteClient
from scrapers.platforms.model import PortalResult


def report_dir() -> Path:
    from scrapers.discovery.survey_meeting_sources import repo_root

    return repo_root() / "data" / "cache" / "platform_meetings"


async def read_target(
    http: PoliteClient, t: PortalTarget, args: argparse.Namespace, store: Any
) -> PortalResult:
    if t.platform == "granicus":
        return await granicus.read_portal(
            http,
            t.portal,
            view_ids=args.granicus_view_id or [1, 2, 3],
            since=args.since,
            jurisdiction_id=t.jurisdiction_id,
            state_code=t.state_code,
            found_via=t.found_via,
            data_center=t.data_center,
        )
    known = store.known_modified("legistar", t.portal) if store is not None and not args.full else None
    return await legistar.read_client(
        http,
        t.portal,
        since=args.since,
        jurisdiction_id=t.jurisdiction_id,
        state_code=t.state_code,
        granicus_host=t.granicus_host,
        max_events=args.max_events,
        known_modified=known,
        found_via=t.found_via,
        data_center=t.data_center,
    )


def summarize(results: Sequence[PortalResult]) -> dict[str, Any]:
    today = date.today()
    meetings = [m for r in results for m in r.meetings]
    held = [m.meeting_date for m in meetings if m.meeting_date and m.meeting_date <= today]
    return {
        "portals": len(results),
        "portals_by_status": dict(Counter(f"{r.platform}:{r.status}" for r in results)),
        "meetings_read": len(meetings),
        "with_agenda_url": sum(1 for m in meetings if m.agenda_url),
        "with_minutes_url": sum(1 for m in meetings if m.minutes_url),
        "with_agenda_text": sum(1 for m in meetings if m.agenda_text),
        "with_minutes_text": sum(1 for m in meetings if m.minutes_text),
        "with_captions": sum(1 for m in meetings if m.transcription_status == "captions"),
        "transcription_status": dict(Counter(m.transcription_status for m in meetings)),
        "newest_held_meeting": max(held).isoformat() if held else None,
        "portal_detail": [
            {
                "platform": r.platform, "portal": r.portal, "jurisdiction_id": r.jurisdiction_id,
                "found_via": r.found_via, "data_center": r.data_center, "status": r.status, "detail": r.detail,
                "meetings": len(r.meetings),
                "newest_held": max((m.meeting_date for m in r.meetings if m.meeting_date and m.meeting_date <= today),
                                   default=None),
            }
            for r in results
        ],
    }


def export_whisper_queue(store: Any, out: Path) -> int:
    from scrapers.platforms.store import MEETING_TABLE

    with store._conn.cursor() as cur:  # noqa: SLF001 - read-only helper on the same connection
        cur.execute(
            f"SELECT platform, meeting_uid, meeting_date, video_url FROM {MEETING_TABLE} "
            "WHERE transcription_status = 'queued_whisper' AND meeting_date <= current_date ORDER BY meeting_date DESC NULLS LAST, platform, meeting_uid"
        )
        rows = cur.fetchall()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["platform", "meeting_uid", "meeting_date", "video_url"])
        w.writerows(rows)
    logger.success("Wrote {:,} queued videos to {}", len(rows), out)
    return len(rows)


async def run(args: argparse.Namespace, store: Any) -> dict[str, Any]:
    targets: list[PortalTarget] = []
    cur = store._conn.cursor() if store is not None else None  # noqa: SLF001
    if args.data_center:
        if cur is None:
            raise SystemExit("--data-center needs the warehouse (it reads the #460 survey)")
        targets += survey_targets(load_survey_rows(cur))
    for client in args.legistar_client or []:
        targets.append(PortalTarget("legistar", client, args.jurisdiction_id, args.state_code, found_via="manual"))
    for host in args.granicus_host or []:
        targets.append(PortalTarget("granicus", granicus.portal_host(host), args.jurisdiction_id, args.state_code,
                                    found_via="manual"))

    results: list[PortalResult] = []
    probed = 0
    async with PoliteClient(min_interval_s=args.min_interval) as http:
        for t in targets:
            res = await read_target(http, t, args, store)
            results.append(res)
            if store is not None and args.apply:
                store.write_portal(res)
        if args.pattern_target and cur is not None:
            have = {t.jurisdiction_id for t in targets if t.platform == "legistar"}
            granicus_hosts = {t.jurisdiction_id: t.portal for t in targets if t.platform == "granicus"}
            candidates = load_candidates(cur, have, limit=args.max_probes)
            found, probed = await probe_legistar(
                http, candidates, target=args.pattern_target, max_probes=args.max_probes,
                skip_clients=[t.portal for t in targets if t.platform == "legistar"], granicus_hosts=granicus_hosts,
            )
            for t in found:
                res = await read_target(http, t, args, store)
                results.append(res)
                if store is not None and args.apply:
                    store.write_portal(res)
        requests = http.requests

    summary = summarize(results)
    summary.update({"governments_probed_by_pattern": probed, "http_requests": requests, "since": args.since.isoformat(),
                    "applied": bool(args.apply)})
    out = args.report_dir or report_dir()
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (out / f"platform_meetings_{stamp}.json").write_text(json.dumps(summary, indent=2, default=str))
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-center", action="store_true", help="read the #460 survey's Granicus/Legistar portals")
    p.add_argument("--pattern-target", type=int, default=0, help="find this many more Legistar portals by URL pattern")
    p.add_argument("--max-probes", type=int, default=250, help="most governments to probe by URL pattern")
    p.add_argument("--legistar-client", action="append", help="read this Legistar client (repeatable)")
    p.add_argument("--granicus-host", action="append", help="read this Granicus host (repeatable)")
    p.add_argument("--granicus-view-id", type=int, action="append")
    p.add_argument("--jurisdiction-id", help="jurisdiction for --legistar-client / --granicus-host")
    p.add_argument("--state-code")
    p.add_argument("--since", type=date.fromisoformat, default=date(2025, 1, 1))
    p.add_argument("--max-events", type=int, default=400, help="most recent meetings per Legistar client")
    p.add_argument("--min-interval", type=float, default=0.75, help="seconds between requests to one host")
    p.add_argument("--full", action="store_true", help="re-read meetings already landed and unchanged")
    p.add_argument("--apply", action="store_true", help="write to the local warehouse bronze tables")
    p.add_argument("--report-dir", type=Path)
    p.add_argument("--export-whisper-queue", type=Path, help="write the queued_whisper videos as TSV and exit")
    p.add_argument("--dsn", help="warehouse DSN (default: local warehouse, never Neon)")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    from scrapers.platforms.store import PlatformStore

    store = PlatformStore(args.dsn)
    try:
        if args.export_whisper_queue:
            export_whisper_queue(store, args.export_whisper_queue)
            return 0
        if args.apply:
            store.ensure_tables()
        summary = asyncio.run(run(args, store))
    finally:
        store.close()
    detail = summary.pop("portal_detail")
    for row in detail:
        logger.info("{platform:9} {portal:28} {status:18} meetings={meetings:<4} newest={newest_held} via={found_via}", **row)
    logger.success("Summary: {}", json.dumps(summary, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
