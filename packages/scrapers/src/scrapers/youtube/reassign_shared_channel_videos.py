"""
Move YouTube videos filed under the wrong jurisdiction of a shared channel (#777).

A channel can serve several governments: ``49 County News.Net``
(``UCZ47nYYggC17NbmBs0Mx3Ww``) posts council meetings for seven Marion County, AL
towns, and LocalView linked it to all seven. The loader filed every new video under
whichever town it was refreshing, and its upsert overwrites ``jurisdiction_id``, so
Hamilton City Council meetings ended up under Winfield.

This tool looks at every video on a channel linked to more than one jurisdiction
(in ``bronze.bronze_event_youtube`` or ``intermediate.int_events_channels``). When
the title names a government other than the one it is filed under
(``title_names_other_government``) and names exactly one of the channel's other
jurisdictions, the video moves there. Every other flagged video is reported as
``unresolved`` and left alone.

The database is only read. By default the tool prints a summary and writes a CSV of
the plan. ``--write-seed`` appends each move as a per-video row (issue 777, the
title as evidence) to ``dbt_project/seeds/youtube_channel_attribution_override.csv``,
skipping videos the seed already lists. The correction then lands through the
reviewed #514 path, which updates bronze, ``civic_event``, the append-only event
marts, ``event_documents`` and question instances together::

    cd dbt_project
    dbt seed --select youtube_channel_attribution_override
    dbt run --select int_youtube__attribution_override
    dbt run-operation repair_youtube_channel_attribution                    # dry run
    dbt run-operation repair_youtube_channel_attribution --args '{dry_run: false}'

Per-video seed rows never touch the channel catalogs: those steps of the repair
read only channel-wide rows.

Usage::

    python -m scrapers.youtube.reassign_shared_channel_videos                 # plan only
    python -m scrapers.youtube.reassign_shared_channel_videos --channel-id UCZ47nYYggC17NbmBs0Mx3Ww
    python -m scrapers.youtube.reassign_shared_channel_videos --write-seed    # add moves to the seed
"""

from __future__ import annotations

import argparse
import csv
import os
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from loguru import logger

from scrapers.discovery.channel_government_mismatch import (
    pick_named_sibling,
    title_names_other_government,
)

_SIBLINGS_SQL = """
    WITH links AS (
        SELECT channel_id, jurisdiction_id
        FROM bronze.bronze_event_youtube
        WHERE channel_id IS NOT NULL AND jurisdiction_id IS NOT NULL
        UNION
        SELECT youtube_channel_id, jurisdiction_id
        FROM intermediate.int_events_channels
        WHERE youtube_channel_id IS NOT NULL AND jurisdiction_id IS NOT NULL
    ), shared AS (
        SELECT channel_id FROM links GROUP BY 1 HAVING count(DISTINCT jurisdiction_id) > 1
    )
    SELECT l.channel_id, j.jurisdiction_id, j.name, j.jurisdiction_type::text, j.state_code
    FROM links l
    JOIN shared USING (channel_id)
    JOIN intermediate.int_jurisdictions j ON j.jurisdiction_id = l.jurisdiction_id
    WHERE (%(channel_id)s::text IS NULL OR l.channel_id = %(channel_id)s)
"""

_VIDEOS_SQL = """
    SELECT video_id, channel_id, jurisdiction_id, title, city,
           policy_analysis_at IS NOT NULL OR policy_analysis_full_at IS NOT NULL AS analyzed
    FROM bronze.bronze_event_youtube
    WHERE channel_id = ANY(%s) AND jurisdiction_id IS NOT NULL AND title IS NOT NULL
"""

SEED_PATH = Path("dbt_project/seeds/youtube_channel_attribution_override.csv")
SEED_FIELDS = ["channel_id", "video_id", "jurisdiction_id", "state_code", "issue", "evidence"]


def seed_rows(moves: Iterable[Planned], already_listed: set[str], state_codes: dict[str, str]) -> list[dict]:
    """Pure: per-video override rows for *moves* not already in the seed."""
    rows = []
    for p in moves:
        if p.action != "move" or p.video_id in already_listed:
            continue
        rows.append({
            "channel_id": p.channel_id,
            "video_id": p.video_id,
            "jurisdiction_id": p.to_jurisdiction_id,
            "state_code": state_codes.get(p.to_jurisdiction_id or "", ""),
            "issue": "777",
            "evidence": f"title: {p.title}",
        })
    return rows


@dataclass(frozen=True)
class Planned:
    video_id: str
    channel_id: str
    title: str
    from_jurisdiction_id: str
    to_jurisdiction_id: str | None
    to_name: str | None
    to_jurisdiction_type: str | None
    reason: str
    action: str  # "move" | "unresolved"
    analyzed: bool


def plan_moves(
    videos: Iterable[dict],
    siblings_by_channel: dict[str, list[dict]],
) -> list[Planned]:
    """Pure: the move (or ``unresolved``) for each misfiled video on a shared channel."""
    out: list[Planned] = []
    for v in videos:
        sibs = siblings_by_channel.get(v["channel_id"]) or []
        own = next((s for s in sibs if s["jurisdiction_id"] == v["jurisdiction_id"]), None)
        if own is None:
            continue
        reason = title_names_other_government(
            v["title"],
            jurisdiction_name=own["name"],
            jurisdiction_type=own["jurisdiction_type"],
            state_code=own["state_code"] or "",
        )
        if not reason:
            continue
        others = [s for s in sibs if s["jurisdiction_id"] != own["jurisdiction_id"]]
        target = pick_named_sibling(v["title"], others)
        out.append(
            Planned(
                video_id=v["video_id"],
                channel_id=v["channel_id"],
                title=v["title"],
                from_jurisdiction_id=own["jurisdiction_id"],
                to_jurisdiction_id=target["jurisdiction_id"] if target else None,
                to_name=target["name"] if target else None,
                to_jurisdiction_type=target["jurisdiction_type"] if target else None,
                reason=reason,
                action="move" if target else "unresolved",
                analyzed=bool(v.get("analyzed")),
            )
        )
    return out


def _default_dsn() -> str:
    """The local warehouse (localhost:5433), never Neon: pass --database-url for anything else.
    ``POSTGRES_PORT`` in .env points at another server, so the port is fixed here."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    return (os.environ.get("OPEN_NAVIGATOR_DATABASE_URL") or "").strip() or (
        "host=localhost port=5433 dbname=open_navigator user={u} password={pw}".format(
            u=os.environ.get("POSTGRES_USER", "postgres"),
            pw=os.environ.get("POSTGRES_PASSWORD", ""),
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--channel-id", help="Only this channel")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/cache/youtube_shared_channel_reassign.csv"),
        help="CSV of planned moves and unresolved rows",
    )
    parser.add_argument("--database-url", help="Default: local warehouse on localhost:5433")
    parser.add_argument(
        "--write-seed",
        nargs="?",
        const=SEED_PATH,
        type=Path,
        help=f"Append the moves as per-video rows to this seed (default {SEED_PATH})",
    )
    args = parser.parse_args(argv)

    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(args.database_url or _default_dsn())
    params = conn.get_dsn_parameters()
    logger.info("Database {}:{}/{} (read-only)", params.get("host"), params.get("port"), params.get("dbname"))
    try:
        conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(_SIBLINGS_SQL, {"channel_id": args.channel_id})
            siblings: dict[str, list[dict]] = {}
            for row in cur.fetchall():
                siblings.setdefault(row["channel_id"], []).append(dict(row))
            cur.execute(_VIDEOS_SQL, (list(siblings),))
            planned = plan_moves(cur.fetchall(), siblings)
    finally:
        conn.close()

    moves = [p for p in planned if p.action == "move"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(Planned.__dataclass_fields__))
        writer.writeheader()
        for p in planned:
            writer.writerow(asdict(p))
    logger.info(
        "{} shared channels; {} misfiled videos: {} to move ({} already analyzed), {} unresolved; CSV {}",
        len(siblings),
        len(planned),
        len(moves),
        sum(p.analyzed for p in moves),
        len(planned) - len(moves),
        args.out,
    )
    if not args.write_seed:
        logger.success("Plan only. Re-run with --write-seed to add {} moves to the override seed.", len(moves))
        return 0

    with args.write_seed.open(newline="") as fh:
        listed = {r["video_id"].strip() for r in csv.DictReader(fh) if (r.get("video_id") or "").strip()}
    state_codes = {s["jurisdiction_id"]: s["state_code"] or "" for sibs in siblings.values() for s in sibs}
    rows = seed_rows(moves, listed, state_codes)
    rows.sort(key=lambda r: (r["channel_id"], r["jurisdiction_id"], r["video_id"]))
    with args.write_seed.open("a", newline="") as fh:
        csv.DictWriter(fh, fieldnames=SEED_FIELDS, lineterminator="\n").writerows(rows)
    logger.success("Added {} per-video rows to {} ({} already listed)", len(rows), args.write_seed,
                   len(moves) - len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
