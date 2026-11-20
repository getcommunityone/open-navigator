"""Site-belt + mention-jurisdiction agenda coverage scoreboard (#632).

Reads the warehouse (survey + agendas + data-center mentions + YouTube dates) and
writes a markdown report. Does not fetch the network; does not bypass blocks.

Usage::

    python -m scrapers.discovery.data_center_agenda_scoreboard
    python -m scrapers.discovery.data_center_agenda_scoreboard --out web_docs/docs/development/data-center-agenda-scoreboard.md
"""

from __future__ import annotations

import argparse
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

import psycopg2
from loguru import logger

from scrapers.discovery.meeting_source_fingerprints import PLATFORM_MEDIA, VIDEO_PLATFORMS
from scrapers.discovery.survey_meeting_sources import PLATFORMS_ALREADY_READ

# Document platforms we fingerprint but do not yet fully land as agenda text
# (Granicus page fetch is robots-disallowed; API path is Legistar-only today).
READERS_NEEDED = frozenset(
    {
        "civicplus_agenda_center",
        "civicclerk",
        "granicus",
        "civicweb",
        "escribe",
        "primegov",
        "novusagenda",
        "iqm2",
        "municode_meetings",
        "boarddocs",
    }
)

NONE_PLATFORM = "none"


@dataclass(frozen=True)
class GovRow:
    jurisdiction_id: str
    name: str
    state_code: str
    jurisdiction_type: str
    website_status: str
    platforms: tuple[str, ...]
    agenda_docs: int
    meetings_known: int
    meetings_with_agenda: int
    transcript_date_min: Optional[date]
    transcript_date_max: Optional[date]
    dc_videos: int
    classification: str
    notes: str


def _connect():
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    url = os.getenv("NEON_DATABASE_URL_DEV") or os.getenv("NEON_DATABASE_URL")
    if not url:
        raise SystemExit("NEON_DATABASE_URL_DEV or NEON_DATABASE_URL is required")
    return psycopg2.connect(url)


def _classify(
    *,
    agenda_docs: int,
    website_status: str,
    platforms: set[str],
) -> tuple[str, str]:
    """Return (classification, notes). One label per government."""
    doc_plats = {p for p in platforms if p not in VIDEO_PLATFORMS and p != NONE_PLATFORM}
    unread = doc_plats & READERS_NEEDED
    readable_docs = doc_plats & PLATFORMS_ALREADY_READ

    if agenda_docs > 0:
        return "has_agenda", f"agenda_docs={agenda_docs}"
    if website_status == "blocked":
        note = "website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429)"
        if unread:
            note += f"; also reader_needed={sorted(unread)}"
        if readable_docs:
            note += f"; survey found readable docs={sorted(readable_docs)} (vendor/YouTube path)"
        return "blocked", note
    if website_status == "unreachable":
        return "unreachable", "website_status=unreachable"
    if unread and not readable_docs:
        return "reader_needed", f"platforms={sorted(unread)}"
    if unread and readable_docs:
        # Prefer reader_needed so CivicPlus/etc. stay visible even if Legistar also listed
        return "reader_needed", f"unread={sorted(unread)}; also_readable={sorted(readable_docs)}"
    if website_status == "missing":
        return "no_document_platform", "website_status=missing"
    return "no_document_platform", f"platforms={sorted(platforms) or ['(none)']}"


def build_scoreboard(conn) -> dict[str, Any]:
    cur = conn.cursor()

    cur.execute(
        "SELECT DISTINCT jurisdiction_id FROM intermediate.int_data_center_site__jurisdiction"
    )
    site_jids = {r[0] for r in cur.fetchall()}

    cur.execute(
        "SELECT DISTINCT jurisdiction_id FROM public.data_center_meeting_mention "
        "WHERE jurisdiction_id IS NOT NULL"
    )
    mention_jids = {r[0] for r in cur.fetchall()}

    cur.execute(
        "SELECT jurisdiction_id, count(DISTINCT video_id) "
        "FROM public.data_center_meeting_mention "
        "WHERE jurisdiction_id IS NOT NULL GROUP BY 1"
    )
    dc_videos_by_jid = dict(cur.fetchall())

    cur.execute(
        """
        SELECT jurisdiction_id, platform, website_status, url, media, found_on
        FROM bronze.bronze_jurisdiction_meeting_source
        """
    )
    platforms_by_jid: dict[str, set[str]] = defaultdict(set)
    status_by_jid: dict[str, str] = {}
    urls_by_jid: dict[str, list[tuple]] = defaultdict(list)
    for jid, plat, st, url, media, found_on in cur.fetchall():
        platforms_by_jid[jid].add(plat)
        # Prefer non-ok only when every row agrees; otherwise keep worst
        prev = status_by_jid.get(jid)
        if prev is None or _status_rank(st) < _status_rank(prev):
            status_by_jid[jid] = st
        urls_by_jid[jid].append((plat, url, media, found_on))

    cur.execute(
        """
        SELECT jurisdiction_id, count(*)
        FROM public.event_meeting_document
        WHERE document_type ILIKE %s
        GROUP BY 1
        """,
        ("%agenda%",),
    )
    agenda_by_jid = dict(cur.fetchall())

    cur.execute(
        """
        SELECT jurisdiction_id, platform, status, detail, portal, portal_url
        FROM bronze.bronze_platform_portal
        """
    )
    portals = cur.fetchall()
    portal_by_jid: dict[str, list[tuple]] = defaultdict(list)
    for jid, platform, status, detail, portal, portal_url in portals:
        if jid:
            portal_by_jid[jid].append((platform, status, detail, portal, portal_url))

    # Transcript / YouTube date range and meetings known (YouTube with date)
    all_jids = site_jids | set(status_by_jid) | mention_jids
    cur.execute(
        """
        SELECT jurisdiction_id,
               min(event_date::date),
               max(event_date::date),
               count(*) FILTER (WHERE event_date IS NOT NULL)
        FROM bronze.bronze_event_youtube
        WHERE jurisdiction_id = ANY(%s)
        GROUP BY 1
        """,
        (list(all_jids),),
    )
    yt_range: dict[str, tuple[Optional[date], Optional[date], int]] = {
        r[0]: (r[1], r[2], int(r[3])) for r in cur.fetchall()
    }

    # Same-day agenda matches within each jid's YouTube date range
    cur.execute(
        """
        WITH yt AS (
          SELECT jurisdiction_id, event_date::date AS d
          FROM bronze.bronze_event_youtube
          WHERE jurisdiction_id = ANY(%s) AND event_date IS NOT NULL
        ),
        ag AS (
          SELECT DISTINCT jurisdiction_id, doc_date::date AS d
          FROM public.event_meeting_document
          WHERE document_type ILIKE %s AND doc_date IS NOT NULL
            AND jurisdiction_id = ANY(%s)
        ),
        bounds AS (
          SELECT jurisdiction_id, min(d) AS dmin, max(d) AS dmax
          FROM yt GROUP BY 1
        )
        SELECT y.jurisdiction_id,
               count(*) AS meetings_known,
               count(*) FILTER (
                 WHERE EXISTS (
                   SELECT 1 FROM ag a
                   WHERE a.jurisdiction_id = y.jurisdiction_id AND a.d = y.d
                 )
               ) AS with_agenda
        FROM yt y
        JOIN bounds b ON b.jurisdiction_id = y.jurisdiction_id
        WHERE y.d BETWEEN b.dmin AND b.dmax
        GROUP BY 1
        """,
        (list(all_jids), "%agenda%", list(all_jids)),
    )
    meeting_cov = {r[0]: (int(r[1]), int(r[2])) for r in cur.fetchall()}

    # Names
    cur.execute(
        """
        SELECT jurisdiction_id, coalesce(display_name, name), state_code, jurisdiction_type
        FROM public.jurisdictions
        WHERE jurisdiction_id = ANY(%s)
        """,
        (list(site_jids | set(status_by_jid)),),
    )
    names = {r[0]: (r[1], r[2] or "", r[3] or "") for r in cur.fetchall()}

    # Per-platform rolls
    def platform_stats(jid_set: set[str]) -> list[tuple[str, int, int]]:
        # platform -> (govs in set with that platform, dc videos in those govs)
        govs: dict[str, set[str]] = defaultdict(set)
        for jid in jid_set:
            for p in platforms_by_jid.get(jid, ()):
                govs[p].add(jid)
        rows = []
        for p, js in sorted(govs.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            vids = sum(dc_videos_by_jid.get(j, 0) for j in js)
            rows.append((p, len(js), vids))
        return rows

    site_platform = platform_stats(site_jids)
    mention_surveyed = mention_jids & set(status_by_jid)
    mention_platform = platform_stats(mention_jids)
    unsurveyed_mention = len(mention_jids - set(status_by_jid))
    unsurveyed_videos = sum(
        dc_videos_by_jid.get(j, 0) for j in (mention_jids - set(status_by_jid))
    )

    # Site-belt government rows (union of site jids and surveyed site-linked)
    gov_rows: list[GovRow] = []
    for jid in sorted(site_jids):
        name, state, jtype = names.get(jid, (jid, "", ""))
        plats = tuple(sorted(platforms_by_jid.get(jid, set())))
        st = status_by_jid.get(jid, "missing")
        agendas = int(agenda_by_jid.get(jid, 0))
        dmin, dmax, _ = yt_range.get(jid, (None, None, 0))
        known, with_ag = meeting_cov.get(jid, (yt_range.get(jid, (None, None, 0))[2], 0))
        # meeting_cov counts rows; if no yt, known=0
        if jid not in meeting_cov:
            known = int(yt_range.get(jid, (None, None, 0))[2])
            with_ag = 0
        cls, notes = _classify(agenda_docs=agendas, website_status=st, platforms=set(plats))
        # Attach robots portal notes
        for platform, status, detail, portal, portal_url in portal_by_jid.get(jid, []):
            if status == "robots_disallowed":
                notes += f"; portal {platform}/{portal}: robots_disallowed"
        gov_rows.append(
            GovRow(
                jurisdiction_id=jid,
                name=name,
                state_code=state,
                jurisdiction_type=jtype,
                website_status=st,
                platforms=plats,
                agenda_docs=agendas,
                meetings_known=known,
                meetings_with_agenda=with_ag,
                transcript_date_min=dmin,
                transcript_date_max=dmax,
                dc_videos=int(dc_videos_by_jid.get(jid, 0)),
                classification=cls,
                notes=notes,
            )
        )

    blocked_rows = [g for g in gov_rows if g.website_status == "blocked" or g.classification == "blocked"]

    class_counts = defaultdict(int)
    for g in gov_rows:
        class_counts[g.classification] += 1

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "generated_at": generated_at,
        "site_jid_count": len(site_jids),
        "mention_jid_count": len(mention_jids),
        "mention_surveyed": len(mention_surveyed),
        "mention_unsurveyed": unsurveyed_mention,
        "mention_unsurveyed_videos": unsurveyed_videos,
        "site_platform": site_platform,
        "mention_platform": mention_platform,
        "gov_rows": gov_rows,
        "blocked_rows": blocked_rows,
        "class_counts": dict(class_counts),
        "portals_robots": [
            (jid, platform, status, detail, portal, portal_url)
            for jid, platform, status, detail, portal, portal_url in portals
            if status == "robots_disallowed"
        ],
        "agenda_doc_total_site": sum(agenda_by_jid.get(j, 0) for j in site_jids),
        "dc_agenda_items": _scalar(
            cur, "SELECT count(*) FROM public.data_center_agenda_item"
        ),
        "upcoming_agenda_docs": _scalar(
            cur,
            "SELECT count(*) FROM public.event_meeting_document "
            "WHERE document_type ILIKE %s AND doc_date >= CURRENT_DATE",
            ("%agenda%",),
        ),
    }


def _status_rank(st: str) -> int:
    return {"blocked": 0, "unreachable": 1, "missing": 2, "ok": 3}.get(st, 9)


def _scalar(cur, sql: str, params=None) -> int:
    cur.execute(sql, params or ())
    return int(cur.fetchone()[0])


def render_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("---")
    a("sidebar_position: 37")
    a("title: Data center agenda coverage scoreboard")
    a(
        "description: Site-belt and mention-jurisdiction agenda coverage by platform "
        "(#632). Regenerated from the warehouse."
    )
    a("---")
    a("")
    a("# Data center agenda coverage scoreboard")
    a("")
    a(f"Generated **{data['generated_at']}** (UTC) for "
      f"[#632](https://github.com/getcommunityone/open-navigator/issues/632). "
      f"Design: [data-center-agenda-first-design](./data-center-agenda-first-design.md).")
    a("")
    a("Numbers are warehouse counts only. **No network fetch** in this report; "
      "**robots.txt and bot blocks are not bypassed.**")
    a("")
    a("## Snapshot")
    a("")
    a(f"| Metric | Count |")
    a(f"|---|---:|")
    a(f"| Site-linked jurisdictions | {data['site_jid_count']} |")
    a(f"| Mention jurisdictions (`data_center_meeting_mention`) | {data['mention_jid_count']} |")
    a(f"| Mention jurisdictions also in #460 survey | {data['mention_surveyed']} |")
    a(f"| Mention jurisdictions **unsurveyed** | {data['mention_unsurveyed']} |")
    a(f"| DC videos in unsurveyed mention jids | {data['mention_unsurveyed_videos']} |")
    a(f"| Agenda docs in site-belt jids | {data['agenda_doc_total_site']} |")
    a(f"| `data_center_agenda_item` rows (national) | {data['dc_agenda_items']} |")
    a(f"| Agenda docs with `doc_date` ≥ today (national) | {data['upcoming_agenda_docs']} |")
    a("")
    a("Upcoming agendas **do** become rows when ingested (same as past agendas).")
    a("")
    a("## Site-belt classification")
    a("")
    a("| Classification | Governments |")
    a("|---|---:|")
    for k in (
        "has_agenda",
        "blocked",
        "unreachable",
        "reader_needed",
        "no_document_platform",
    ):
        a(f"| `{k}` | {data['class_counts'].get(k, 0)} |")
    a("")
    a("## Per platform")
    a("")
    a("### Site belt")
    a("")
    a("| Platform | Site-belt governments | DC videos in those governments | Media | We read docs today |")
    a("|---|---:|---:|---|---|")
    for plat, govs, vids in data["site_platform"]:
        media = PLATFORM_MEDIA.get(plat, "—")
        read = "yes" if plat in PLATFORMS_ALREADY_READ else (
            "n/a (video)" if plat in VIDEO_PLATFORMS or plat == NONE_PLATFORM else "no"
        )
        if plat == "granicus":
            read = "no (robots_disallowed on pages)"
        a(f"| `{plat}` | {govs} | {vids} | {media} | {read} |")
    a("")
    a("### Mention jurisdictions (survey overlap only for platform)")
    a("")
    a(
        f"Only **{data['mention_surveyed']}** of **{data['mention_jid_count']}** mention "
        f"jurisdictions appear in `bronze_jurisdiction_meeting_source`. The other "
        f"**{data['mention_unsurveyed']}** (about **{data['mention_unsurveyed_videos']}** "
        f"DC videos) have **no surveyed platform** yet — Stage 2 (#637)."
    )
    a("")
    a("| Platform | Mention jurisdictions (surveyed) | DC videos in those jurisdictions |")
    a("|---|---:|---:|")
    for plat, govs, vids in data["mention_platform"]:
        a(f"| `{plat}` | {govs} | {vids} |")
    a(f"| *(unsurveyed)* | {data['mention_unsurveyed']} | {data['mention_unsurveyed_videos']} |")
    a("")
    a("Reader priority for the site belt should follow document platforms we do not "
      "read yet, weighted by governments **and** DC videos in the tables above.")
    a("")
    a("## Blocked / robots")
    a("")
    a("### Website `blocked` (site belt)")
    a("")
    a(
        "`bronze.bronze_jurisdiction_meeting_source` stores `website_status` but **not** "
        "the HTTP status code or reason string. The #460 write-up recorded **28× HTTP 403** "
        "and **1× HTTP 429** (Bexar County TX) among blocked governments. Per-government "
        "codes were not loaded into bronze — follow-up "
        "[#638](https://github.com/getcommunityone/open-navigator/issues/638). "
        "**Do not route around these blocks.**"
    )
    a("")
    a("| Government | State | `jurisdiction_id` | Platforms found | Notes |")
    a("|---|---|---|---|---|")
    for g in sorted(data["blocked_rows"], key=lambda x: (x.state_code, x.name)):
        plats = ", ".join(g.platforms) or "—"
        a(f"| {g.name} | {g.state_code} | `{g.jurisdiction_id}` | {plats} | {g.notes} |")
    a("")
    a("### Platform portals `robots_disallowed`")
    a("")
    a("| `jurisdiction_id` | Platform | Portal | Detail |")
    a("|---|---|---|---|")
    for jid, platform, status, detail, portal, portal_url in data["portals_robots"]:
        a(f"| `{jid or '—'}` | `{platform}` | `{portal}` | {detail or '—'} |")
    if not data["portals_robots"]:
        a("| — | — | — | none |")
    a("")
    a("## Per government (site belt)")
    a("")
    a(
        "`meetings_known` = YouTube rows with `event_date` in that jurisdiction’s "
        "YouTube min–max date range. `meetings_with_agenda` = those with a same-day "
        "agenda in `event_meeting_document`. DC videos = distinct "
        "`data_center_meeting_mention.video_id`."
    )
    a("")
    a(
        "| Government | ST | Class | Website | Platforms | Agenda docs | "
        "Meetings w/ agenda | Meetings known | YT date range | DC videos |"
    )
    a("|---|---|---|---|---|---:|---:|---:|---|---:|")
    for g in sorted(data["gov_rows"], key=lambda x: (x.state_code, x.name)):
        dr = (
            f"{g.transcript_date_min} … {g.transcript_date_max}"
            if g.transcript_date_min
            else "—"
        )
        plats = ", ".join(g.platforms) or "—"
        a(
            f"| {g.name} | {g.state_code} | `{g.classification}` | {g.website_status} | "
            f"{plats} | {g.agenda_docs} | {g.meetings_with_agenda} | {g.meetings_known} | "
            f"{dr} | {g.dc_videos} |"
        )
    a("")
    a("## How to regenerate")
    a("")
    a("```bash")
    a("python -m scrapers.discovery.data_center_agenda_scoreboard \\")
    a("  --out web_docs/docs/development/data-center-agenda-scoreboard.md")
    a("```")
    a("")
    return "\n".join(lines) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out",
        type=Path,
        default=Path("web_docs/docs/development/data-center-agenda-scoreboard.md"),
        help="markdown report path",
    )
    args = p.parse_args(argv)
    conn = _connect()
    try:
        data = build_scoreboard(conn)
    finally:
        conn.close()
    text = render_markdown(data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    logger.success(
        "Wrote {} ({} site-belt governments; classes={})",
        args.out,
        len(data["gov_rows"]),
        data["class_counts"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
