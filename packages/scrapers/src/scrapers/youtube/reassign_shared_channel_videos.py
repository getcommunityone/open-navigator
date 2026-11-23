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

Read-only by default: it prints a summary and writes a CSV of planned moves.
``--apply`` performs the moves in one transaction; each UPDATE also matches the old
``jurisdiction_id``, so a row changed since the plan is not touched. Only
``jurisdiction_id``, ``jurisdiction_name`` and ``city`` change (``city`` is cleared for a
county); ``video_id`` (the
primary key) and the analysis columns stay as they are. Rebuild the dbt event
marts afterwards.

Usage::

    python -m scrapers.youtube.reassign_shared_channel_videos                 # dry run
    python -m scrapers.youtube.reassign_shared_channel_videos --channel-id UCZ47nYYggC17NbmBs0Mx3Ww
    python -m scrapers.youtube.reassign_shared_channel_videos --apply         # writes
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

_UPDATE_SQL = """
    UPDATE bronze.bronze_event_youtube
    SET jurisdiction_id = %(to_jurisdiction_id)s,
        jurisdiction_name = %(to_name)s,
        city = CASE WHEN %(to_jurisdiction_type)s = 'county' THEN NULL
                    WHEN city IS NULL THEN NULL ELSE %(to_name)s END,
        last_updated = now()
    WHERE video_id = %(video_id)s AND jurisdiction_id = %(from_jurisdiction_id)s
"""


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
    parser.add_argument("--apply", action="store_true", help="Perform the moves (default: dry run)")
    args = parser.parse_args(argv)

    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(args.database_url or _default_dsn())
    params = conn.get_dsn_parameters()
    logger.info("Database {}:{}/{} ({})", params.get("host"), params.get("port"), params.get("dbname"),
                "WRITE" if args.apply else "read-only")
    try:
        conn.set_session(readonly=not args.apply)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(_SIBLINGS_SQL, {"channel_id": args.channel_id})
            siblings: dict[str, list[dict]] = {}
            for row in cur.fetchall():
                siblings.setdefault(row["channel_id"], []).append(dict(row))
            cur.execute(_VIDEOS_SQL, (list(siblings),))
            planned = plan_moves(cur.fetchall(), siblings)

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

        if not args.apply:
            logger.success("Dry run: nothing written. Re-run with --apply to move {} videos.", len(moves))
            return 0

        with conn.cursor() as cur:
            changed = 0
            for p in moves:
                cur.execute(_UPDATE_SQL, asdict(p))
                changed += cur.rowcount
        conn.commit()
        logger.success("Moved {} of {} planned videos; rebuild the dbt event marts next.", changed, len(moves))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
