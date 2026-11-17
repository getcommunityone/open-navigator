"""Find the YouTube channels that city websites actually link to.

The first homepage scrape stored no links for any city: every
``payload.social_media`` list is empty, and ``youtube_channel_url`` on
``bronze.bronze_jurisdictions_municipalities_scraped`` mostly holds handle guesses
(``youtube_channel_selection_method = 'pattern_match'``, for example ``@SeligmanAL``)
that the channel verification gate rejects.

This revisits each city's ``homepage_url`` with ``YouTubeChannelDiscovery``: links
and embeds on the homepage, then same-site meeting and video pages, then site
search. Each channel found is added to ``payload.youtube_channels`` with
``discovery_method = 'website_scrape'``. When the row's primary channel is empty, a
pattern guess or a search hit (``REPLACEABLE_METHODS``), the first link found
becomes the primary (``youtube_channel_selection_method = 'website_scrape'``). A
channel chosen any other way (an earlier homepage link, a hand pick) is never
replaced. No YouTube request is made, so the YouTube Data API quota and YouTube's
bot checks don't apply, and the scan runs without the VPN: city websites may still
be retried on the home connection. If a page fetch ever does go to a YouTube host,
it needs the VPN (``scrapers.youtube.vpn_guard``); with the VPN off the run stops
with exit code 5 (#488).

Re-verifying handle guesses (#535). A row whose primary is a ``pattern_match`` guess
(or an earlier ``pattern_match_unverified``) gets one of four verdicts, saved in
``payload.homepage_rescan_verdict`` and counted in the run summary:

* ``confirmed``: the city site links the guessed channel. The method becomes
  ``website_scrape``, so the crawl plan picks it up.
* ``replaced``: the site links a different channel. That channel becomes the
  primary (``website_scrape``).
* ``unverified``: the site loaded but links no channel, or links only channels
  whose handle names another government (``channel_government_mismatch``, #527).
  The method becomes ``pattern_match_unverified``; the URL is kept for review, and
  the crawl never uses it (``load_youtube_events_to_postgres`` skips it).
* ``unreadable``: the homepage could not be fetched. Nothing changes, so a later
  run tries again.

``--mark-no-website`` marks guesses on rows with no website at all as unverified
(reason ``no_website``) without fetching anything: there is no site to confirm them.

Dry run by default::

    python -m scrapers.youtube.rescan_homepage_channels --states AL --limit 50
    python -m scrapers.youtube.rescan_homepage_channels --states AL --limit 50 --apply
    python -m scrapers.youtube.rescan_homepage_channels --apply --concurrency 8
    python -m scrapers.youtube.rescan_homepage_channels --source websites \
        --methods pattern_match --rescan --limit 200 --apply
    python -m scrapers.youtube.rescan_homepage_channels --mark-no-website --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Sequence

from loguru import logger

from scrapers.discovery.channel_government_mismatch import title_names_other_government
from scrapers.youtube.pattern_match_gate import PATTERN_MATCH_UNVERIFIED_METHOD
from scrapers.youtube.vpn_guard import exit_if_vpn_off

TABLE = "bronze.bronze_jurisdictions_municipalities_scraped"
# Scraped table per jurisdiction type. School districts' table has no channel
# columns, so their links are kept in ``payload`` only.
TABLES = {
    "municipality": TABLE,
    "county": "bronze.bronze_jurisdictions_counties_scraped",
    "school_district": "bronze.bronze_jurisdictions_school_districts_scraped",
}
CHANNEL_COLUMN_TABLES = frozenset({TABLES["municipality"], TABLES["county"]})
WEBSITES = "intermediate.int_jurisdiction_websites"
METHOD = "website_scrape"  # the name youtube_primary_channel ranks highest
CONFIDENCE = 0.9
# A primary chosen by one of these may be replaced by a homepage link: guesses and
# search hits (4 of 4 Alabama search picks were wrong on November 16, 2026).
REPLACEABLE_METHODS = frozenset({"", "pattern_match", "domain_search", "youtube_api"})
# Primaries that are handle guesses: each gets a verdict (#535).
GUESS_METHODS = frozenset({"pattern_match", PATTERN_MATCH_UNVERIFIED_METHOD})
CONFIRMED, REPLACED, UNVERIFIED, UNREADABLE = (
    "confirmed",
    "replaced",
    "unverified",
    "unreadable",
)


@dataclass
class RescanResult:
    key: str
    homepage_url: str
    channels: list[str] = field(default_factory=list)
    error: str | None = None
    # "" when the homepage loaded; else why not (fetch_failed, blocked:<reason>).
    homepage_error: str = ""


@dataclass(frozen=True)
class GuessVerdict:
    """What re-verification decided for a guessed primary channel."""

    status: str  # confirmed | replaced | unverified | unreadable
    primary_url: str | None = None
    reason: str = ""


def government_mismatch(
    url: str, *, jurisdiction_name: str | None, jurisdiction_type: str, state_code: str
) -> str | None:
    """Why a site-linked channel's @handle names another government (#527), else None.

    Only the handle is read: no YouTube page is fetched. Without a jurisdiction
    name there is nothing to compare against, so nothing is rejected."""
    if not (jurisdiction_name or "").strip():
        return None
    return title_names_other_government(
        "",
        jurisdiction_name=jurisdiction_name or "",
        jurisdiction_type=jurisdiction_type,
        state_code=state_code,
        channel_url=url,
    )


def verify_guess(
    guess_url: str | None,
    guess_channel_id: str | None,
    channels: Sequence[str],
    *,
    homepage_error: str = "",
    jurisdiction_name: str | None = None,
    jurisdiction_type: str = "municipality",
    state_code: str = "",
) -> GuessVerdict:
    """Decide a guessed channel against the channels the city's own site links."""
    accepted: list[str] = []
    rejected: list[str] = []
    for url in channels:
        why = government_mismatch(
            url,
            jurisdiction_name=jurisdiction_name,
            jurisdiction_type=jurisdiction_type,
            state_code=state_code,
        )
        if why:
            rejected.append(f"{why}:{url}")
        else:
            accepted.append(url)
    guess_key = _key(guess_url)
    guess_id = (guess_channel_id or "").strip()
    for url in accepted:
        if (guess_key and _key(url) == guess_key) or (
            guess_id.startswith("UC") and _channel_id(url) == guess_id
        ):
            return GuessVerdict(CONFIRMED, guess_url, "site_links_guess")
    if accepted:
        return GuessVerdict(REPLACED, accepted[0], "site_links_other_channel")
    if rejected:
        return GuessVerdict(
            UNVERIFIED, None, "site_links_other_government:" + rejected[0]
        )
    if homepage_error:
        return GuessVerdict(UNREADABLE, None, homepage_error)
    return GuessVerdict(UNVERIFIED, None, "no_site_link")


def merge_channels(
    payload: dict[str, Any] | None, channels: Sequence[str], *, now: str
) -> tuple[dict[str, Any], int]:
    """Add each channel URL to ``payload['youtube_channels']`` as a homepage link.

    A URL already listed is relabelled as a homepage link, since the site itself
    links to it. Returns the new payload and how many URLs were new."""
    out = dict(payload or {})
    entries = [
        dict(e) for e in (out.get("youtube_channels") or []) if isinstance(e, dict)
    ]
    by_url = {_key(e.get("channel_url")): e for e in entries if e.get("channel_url")}
    added = 0
    for url in channels:
        key = _key(url)
        if not key:
            continue
        if key in by_url:
            by_url[key]["discovery_method"] = METHOD
            by_url[key]["confidence"] = max(
                float(by_url[key].get("confidence") or 0), CONFIDENCE
            )
            continue
        entry = {
            "channel_url": url,
            "channel_id": _channel_id(url),
            "discovery_method": METHOD,
            "confidence": CONFIDENCE,
            "discovered_at": now,
        }
        entries.append(entry)
        by_url[key] = entry
        added += 1
    out["youtube_channels"] = entries
    social = dict(out.get("social_media") or {})
    social["youtube"] = sorted({*(social.get("youtube") or []), *channels})
    out["social_media"] = social
    return out, added


def choose_primary(
    current_url: str | None, current_method: str | None, channels: Sequence[str]
) -> str | None:
    """The new primary channel URL, or ``None`` to keep the current one."""
    if not channels:
        return None
    if (current_method or "").strip().lower() not in REPLACEABLE_METHODS and (
        current_url or ""
    ).strip():
        return None
    return channels[0]


def _key(url: Any) -> str:
    return str(url or "").strip().rstrip("/").lower()


def _channel_id(url: str) -> str | None:
    marker = "/channel/"
    if marker in url:
        cid = url.split(marker, 1)[1].split("/", 1)[0].split("?", 1)[0]
        return cid if cid.startswith("UC") else None
    return None


def normalize_homepage(url: str | None) -> str | None:
    """A fetchable homepage URL: scheme added when the source stored a bare domain."""
    u = (url or "").strip()
    if not u:
        return None
    return (
        u
        if u.lower().startswith(("http://", "https://"))
        else f"https://{u.lstrip('/')}"
    )


def select_sql(
    states: Sequence[str],
    *,
    include_rescanned: bool,
    jtype: str = "municipality",
    source: str = "scraped",
    methods: Sequence[str] = (),
) -> tuple[str, list[Any]]:
    """Rows to scan for one jurisdiction type.

    ``source="scraped"``: the homepage the scraped table saved.
    ``source="websites"``: every jurisdiction with a website in
    ``int_jurisdiction_websites`` (one per jurisdiction, ``.gov`` first), including
    those whose scraped row has no homepage; the homepage is filled in on write.
    ``methods``: only rows whose current ``youtube_channel_selection_method`` is one
    of these (for example ``pattern_match``, #535).
    """
    table = TABLES[jtype]
    yt_cols = (
        "s.youtube_channel_url, s.youtube_channel_selection_method, s.youtube_channel_id"
        if table in CHANNEL_COLUMN_TABLES
        else "NULL::text AS youtube_channel_url, NULL::text AS youtube_channel_selection_method, "
        "NULL::text AS youtube_channel_id"
    )
    where: list[str] = []
    params: list[Any] = [jtype]
    if source == "websites":
        homepage = "COALESCE(s.homepage_final_url, s.homepage_url, w.website_url)"
        from_sql = (
            f"FROM {table} s "
            "JOIN intermediate.int_jurisdictions j ON j.geoid = s.geoid AND j.jurisdiction_type::text = %s "
            f"JOIN LATERAL (SELECT ws.website_url FROM {WEBSITES} ws "
            "WHERE ws.jurisdiction_id = j.jurisdiction_id AND BTRIM(COALESCE(ws.website_url, '')) <> '' "
            "ORDER BY (ws.domain_name ILIKE '%%.gov') DESC, ws.website_url LIMIT 1) w ON TRUE"
        )
    elif source == "scraped":
        homepage = "COALESCE(s.homepage_final_url, s.homepage_url)"
        from_sql = (
            f"FROM {table} s LEFT JOIN intermediate.int_jurisdictions j "
            "ON j.geoid = s.geoid AND j.jurisdiction_type::text = %s"
        )
        where.append("BTRIM(COALESCE(s.homepage_url, '')) <> ''")
    else:
        raise ValueError(f"unknown source {source!r}")
    if states:
        where.append("s.usps = ANY(%s)")
        params.append([st.upper() for st in states])
    if methods:
        if table not in CHANNEL_COLUMN_TABLES:
            raise ValueError(f"{table} has no channel columns to filter on")
        where.append("COALESCE(s.youtube_channel_selection_method, '') = ANY(%s)")
        params.append(list(methods))
    if not include_rescanned:
        where.append("NOT (COALESCE(s.payload, '{}'::jsonb) ? 'homepage_rescan_at')")
    where_sql = f"WHERE {' AND '.join(where)} " if where else ""
    sql = (
        f"SELECT DISTINCT ON (s.geoid) s.geoid, s.usps, {homepage} AS homepage_url, "
        f"(BTRIM(COALESCE(s.homepage_url, '')) = '') AS fill_homepage, s.payload, "
        f"j.name AS jurisdiction_name, {yt_cols} "
        f"{from_sql} {where_sql}ORDER BY s.geoid LIMIT %s"
    )
    return sql, params


async def scan_all(
    rows: list[dict[str, Any]], *, concurrency: int, timeout: float
) -> list[RescanResult]:
    from scrapers.youtube.vpn_guard import VpnRequiredError
    from scrapers.youtube.youtube_channel_discovery import YouTubeChannelDiscovery

    sem = asyncio.Semaphore(max(1, concurrency))
    results: list[RescanResult] = []
    async with YouTubeChannelDiscovery(youtube_api_key=None) as discovery:

        async def one(i: int, row: dict[str, Any]) -> None:
            res = RescanResult(key=row["key"], homepage_url=row["homepage_url"])
            async with sem:
                try:
                    found, res.homepage_error = await asyncio.wait_for(
                        discovery.scrape_website_with_status(res.homepage_url),
                        timeout,
                    )
                    res.channels = list(dict.fromkeys(c for c in found if c))
                except VpnRequiredError:
                    raise  # a YouTube fetch without the VPN stops the run (#488)
                except Exception as exc:  # noqa: BLE001 - one broken site must not stop the scan
                    res.error = f"{type(exc).__name__}: {exc}"[:200]
            results.append(res)
            if res.channels:
                logger.info(
                    "[{}/{}] {} {} -> {}",
                    i,
                    len(rows),
                    row["usps"],
                    res.homepage_url,
                    res.channels,
                )

        await asyncio.gather(*(one(i, r) for i, r in enumerate(rows, 1)))
    return results


def _jtype(row: dict[str, Any]) -> str:
    return str(row.get("key") or "municipality|").split("|", 1)[0]


def verdict_for(row: dict[str, Any], res: RescanResult) -> GuessVerdict | None:
    """The verdict for a row whose primary is a guess; ``None`` for any other row."""
    method = (row.get("youtube_channel_selection_method") or "").strip().lower()
    if row.get("table", TABLE) not in CHANNEL_COLUMN_TABLES or method not in GUESS_METHODS:
        return None
    if not (row.get("youtube_channel_url") or "").strip():
        return None
    return verify_guess(
        row["youtube_channel_url"],
        row.get("youtube_channel_id"),
        res.channels,
        homepage_error=res.error or res.homepage_error,
        jurisdiction_name=row.get("jurisdiction_name"),
        jurisdiction_type=_jtype(row),
        state_code=row.get("usps") or "",
    )


def write_results(
    conn: Any, rows: dict[str, dict[str, Any]], results: list[RescanResult]
) -> dict[str, int]:
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    counts = {
        "rows_with_links": 0,
        "new_links": 0,
        "primary_set": 0,
        "homepages_filled": 0,
        CONFIRMED: 0,
        REPLACED: 0,
        UNVERIFIED: 0,
        UNREADABLE: 0,
    }
    with conn.cursor() as cur:
        for res in results:
            row = rows[res.key]
            table = row["table"]
            payload, added = merge_channels(row["payload"], res.channels, now=now)
            payload["homepage_rescan_at"] = now
            if res.error:
                payload["homepage_rescan_error"] = res.error
            else:
                payload.pop("homepage_rescan_error", None)
            sets = ["payload = %s"]
            values: list[Any] = [json.dumps(payload)]
            if row.get("fill_homepage") and row["homepage_url"]:
                sets.append("homepage_url = %s")
                values.append(row["homepage_url"])
                counts["homepages_filled"] += 1
            if res.channels:
                counts["rows_with_links"] += 1
                counts["new_links"] += added
            primary = None
            method = (row.get("youtube_channel_selection_method") or "").strip().lower()
            jtype = _jtype(row)
            verdict = verdict_for(row, res)
            if verdict:
                counts[verdict.status] += 1
                payload["homepage_rescan_verdict"] = {
                    "status": verdict.status,
                    "reason": verdict.reason,
                    "guess_url": row["youtube_channel_url"],
                    "checked_at": now,
                }
                if verdict.status == CONFIRMED:
                    sets += [
                        "youtube_channel_selection_method = %s",
                        "youtube_channel_selection_confidence = %s",
                    ]
                    values += [METHOD, CONFIDENCE]
                elif verdict.status == REPLACED:
                    primary = verdict.primary_url
                elif verdict.status == UNVERIFIED and method != PATTERN_MATCH_UNVERIFIED_METHOD:
                    sets.append("youtube_channel_selection_method = %s")
                    values.append(PATTERN_MATCH_UNVERIFIED_METHOD)
                values[0] = json.dumps(payload)
            elif table in CHANNEL_COLUMN_TABLES:
                linked = [
                    url
                    for url in res.channels
                    if not government_mismatch(
                        url,
                        jurisdiction_name=row.get("jurisdiction_name"),
                        jurisdiction_type=jtype,
                        state_code=row.get("usps") or "",
                    )
                ]
                primary = choose_primary(
                    row["youtube_channel_url"],
                    row["youtube_channel_selection_method"],
                    linked,
                )
            if primary:
                counts["primary_set"] += 1
                sets += [
                    "youtube_channel_url = %s",
                    "youtube_channel_id = %s",
                    "youtube_channel_selection_method = %s",
                    "youtube_channel_selection_confidence = %s",
                ]
                values += [primary, _channel_id(primary), METHOD, CONFIDENCE]
            cur.execute(
                f"UPDATE {table} SET {', '.join(sets)} WHERE geoid = %s",
                [*values, row["geoid"]],
            )
    conn.commit()
    return counts


def mark_no_website_sql(
    table: str, jtype: str, states: Sequence[str], *, apply: bool
) -> tuple[str, list[Any]]:
    """Guesses on rows with no website anywhere: count them, or mark them unverified.

    No site exists to confirm such a guess, so it is unverified by definition
    (reason ``no_website``). The URL stays for review."""
    where = (
        "s.youtube_channel_selection_method = 'pattern_match' "
        "AND BTRIM(COALESCE(s.youtube_channel_url, '')) <> '' "
        "AND BTRIM(COALESCE(s.homepage_url, '')) = '' "
        "AND BTRIM(COALESCE(s.homepage_final_url, '')) = '' "
        "AND NOT EXISTS (SELECT 1 FROM intermediate.int_jurisdictions j "
        f"JOIN {WEBSITES} ws ON ws.jurisdiction_id = j.jurisdiction_id "
        "AND BTRIM(COALESCE(ws.website_url, '')) <> '' "
        "WHERE j.geoid = s.geoid AND j.jurisdiction_type::text = %s)"
    )
    params: list[Any] = [jtype]
    if states:
        where += " AND s.usps = ANY(%s)"
        params.append([st.upper() for st in states])
    if not apply:
        return f"SELECT COUNT(*) FROM {table} s WHERE {where}", params
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    sql = (
        f"UPDATE {table} s SET youtube_channel_selection_method = %s, "
        "payload = COALESCE(s.payload, '{}'::jsonb) || jsonb_build_object("
        "'homepage_rescan_verdict', jsonb_build_object('status', %s, 'reason', 'no_website', "
        "'guess_url', s.youtube_channel_url, 'checked_at', %s::text)) "
        f"WHERE {where}"
    )
    return sql, [PATTERN_MATCH_UNVERIFIED_METHOD, UNVERIFIED, now, *params]


def _database_url(explicit: str) -> str:
    import os

    from dotenv import load_dotenv

    load_dotenv()
    url = (
        explicit
        or os.getenv("OPEN_NAVIGATOR_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or ""
    ).strip()
    if url:
        return url
    return f"postgresql://postgres:{os.getenv('POSTGRES_PASSWORD') or 'password'}@localhost:5433/open_navigator"


@exit_if_vpn_off
def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Find the YouTube channels that jurisdiction websites link to."
    )
    p.add_argument(
        "--states", default="", help="Comma-separated USPS codes (default: all)"
    )
    p.add_argument(
        "--types",
        default="municipality",
        help=f"Comma-separated jurisdiction types: {', '.join(TABLES)} (default: municipality)",
    )
    p.add_argument(
        "--source",
        choices=("scraped", "websites"),
        default="scraped",
        help="scraped: homepages the scraped tables saved (default); websites: every "
        "jurisdiction with a website in int_jurisdiction_websites",
    )
    p.add_argument("--limit", type=int, default=100000, help="Most rows per type")
    p.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="Websites fetched at once (default 8)",
    )
    p.add_argument(
        "--timeout", type=float, default=90.0, help="Seconds per website (default 90)"
    )
    p.add_argument(
        "--rescan", action="store_true", help="Also revisit rows already rescanned"
    )
    p.add_argument(
        "--apply", action="store_true", help="Write results (default: dry run)"
    )
    p.add_argument(
        "--batch", type=int, default=200, help="Rows per saved batch (default 200)"
    )
    p.add_argument(
        "--methods",
        default="",
        help="Comma-separated youtube_channel_selection_method values to scan, e.g. "
        "pattern_match (default: any). Guessed primaries get a verdict (#535).",
    )
    p.add_argument(
        "--mark-no-website",
        action="store_true",
        help="Only mark pattern_match guesses on rows with no website as unverified "
        "(no fetching), then exit",
    )
    p.add_argument("--database-url", default="")
    args = p.parse_args(argv)

    import psycopg2
    from psycopg2.extras import RealDictCursor

    states = [st.strip() for st in args.states.split(",") if st.strip()]
    types = [t.strip() for t in args.types.split(",") if t.strip()]
    unknown = [t for t in types if t not in TABLES]
    if unknown:
        p.error(f"unknown type(s): {', '.join(unknown)}")
    methods = [m.strip().lower() for m in args.methods.split(",") if m.strip()]

    conn = psycopg2.connect(_database_url(args.database_url))
    try:
        if args.mark_no_website:
            for jtype in types:
                table = TABLES[jtype]
                if table not in CHANNEL_COLUMN_TABLES:
                    continue
                sql, params = mark_no_website_sql(table, jtype, states, apply=args.apply)
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    n = cur.rowcount if args.apply else cur.fetchone()[0]
                conn.commit()
                logger.success(
                    "{}: {:,} guess(es) with no website {}",
                    jtype,
                    n,
                    "marked unverified" if args.apply else "would be marked unverified (dry run)",
                )
            return 0

        rows: dict[str, dict[str, Any]] = {}
        for jtype in types:
            sql, params = select_sql(
                states,
                include_rescanned=args.rescan,
                jtype=jtype,
                source=args.source,
                methods=methods,
            )
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, [*params, args.limit])
                fetched = cur.fetchall()
            for r in fetched:
                row = dict(r)
                row["homepage_url"] = normalize_homepage(row["homepage_url"])
                if not row["homepage_url"]:
                    continue
                row["table"] = TABLES[jtype]
                row["key"] = f"{jtype}|{row['geoid']}"
                rows[row["key"]] = row
            logger.info("{}: {:,} website(s) to scan", jtype, len(fetched))
        logger.info(
            "{:,} website(s) in total ({})",
            len(rows),
            "apply" if args.apply else "dry run",
        )

        batch = max(1, args.batch)
        ordered = list(rows.values())
        totals = {
            "scanned": 0,
            "found": 0,
            "errors": 0,
            "rows_with_links": 0,
            "new_links": 0,
            "primary_set": 0,
            "homepages_filled": 0,
            CONFIRMED: 0,
            REPLACED: 0,
            UNVERIFIED: 0,
            UNREADABLE: 0,
        }
        for start in range(0, len(ordered), batch):
            chunk = ordered[start : start + batch]
            results = asyncio.run(
                scan_all(chunk, concurrency=args.concurrency, timeout=args.timeout)
            )
            totals["scanned"] += len(results)
            totals["found"] += sum(1 for res in results if res.channels)
            totals["errors"] += sum(1 for res in results if res.error)
            if args.apply:
                for key, value in write_results(conn, rows, results).items():
                    totals[key] += value
            else:
                for res in results:
                    verdict = verdict_for(rows[res.key], res)
                    if verdict:
                        totals[verdict.status] += 1
            logger.info(
                "Progress {scanned:,}/{total:,}: {found:,} with YouTube links, {errors:,} errors; "
                "guesses confirmed {confirmed:,}, replaced {replaced:,}, unverified "
                "{unverified:,}, unreadable {unreadable:,}",
                total=len(ordered),
                **totals,
            )
        if args.apply:
            logger.success(
                "Wrote {rows_with_links:,} rows with links ({new_links:,} new links); primary set on "
                "{primary_set:,}; homepages filled on {homepages_filled:,}; guesses confirmed "
                "{confirmed:,}, replaced {replaced:,}, unverified {unverified:,}, unreadable "
                "{unreadable:,}",
                **totals,
            )
        else:
            logger.success("Dry run: nothing written. Re-run with --apply to save.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
