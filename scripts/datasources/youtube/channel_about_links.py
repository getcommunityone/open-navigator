"""
Fetch featured external links and channel metadata from a YouTube channel About tab.

YouTube embeds link rows in the page ``ytInitialData`` JSON under
``channelExternalLinkViewModel`` (title + url). The official Data API does not
expose this list reliably, so we parse the public About HTML.

Also extracts channel title, description, subscriber / video / lifetime view counts when
present in ``ytInitialData``. Description is often under
``metadata.channelMetadataRenderer.description`` (plain string); older layouts
used ``channelAboutFullMetadataRenderer.description`` (runs).

Also extracts plain URLs embedded in the channel **description** (e.g. ``http://…``,
``www.…``) and appends them to ``links`` after featured About links (deduped by URL).

Usage::

    python scripts/datasources/youtube/channel_about_links.py --channel-id UCxxxx

    python scripts/datasources/youtube/channel_about_links.py --where-null --limit 50

    python scripts/datasources/youtube/channel_about_links.py --refetch-all
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, replace
from typing import Any, Dict, Iterator, List, Optional, Tuple

import httpx
from dotenv import load_dotenv
from loguru import logger
import psycopg2

load_dotenv()

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
ABOUT_URL = "https://www.youtube.com/channel/{channel_id}/about"


@dataclass
class ChannelAboutSnapshot:
    """Parsed channel /about page: featured links plus optional metadata."""

    links: List[Dict[str, str]]
    channel_title: Optional[str] = None
    channel_description: Optional[str] = None
    channel_keywords: Optional[str] = None  # yt channelMetadataRenderer.keywords; inference only
    channel_type: str = "unknown"
    subscriber_count: Optional[int] = None
    video_count: Optional[int] = None
    view_count: Optional[int] = None


def _coerce_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s or None
    if isinstance(value, dict):
        for key in ("simpleText", "content", "text"):
            if key in value:
                return _coerce_text(value.get(key))
        runs = value.get("runs")
        if isinstance(runs, list):
            parts = []
            for r in runs:
                if isinstance(r, dict) and r.get("text"):
                    parts.append(str(r["text"]))
            s = "".join(parts).strip()
            return s or None
    return None


def extract_yt_initial_data(html: str) -> Optional[Dict[str, Any]]:
    marker = "var ytInitialData = "
    idx = html.find(marker)
    if idx == -1:
        return None
    start = html.find("{", idx)
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(html)):
        c = html[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                blob = html[start : i + 1]
                try:
                    return json.loads(blob)
                except json.JSONDecodeError as e:
                    logger.warning("ytInitialData JSON decode failed: {}", e)
                    return None
    return None


def normalize_external_url(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return s
    lower = s.lower()
    if lower.startswith(("http://", "https://")):
        return s
    if lower.startswith("//"):
        return "https:" + s
    return "https://" + s


def _strip_url_trailing_punct(url: str) -> str:
    return re.sub(r"""[),.;:'">\]}]+$""", "", (url or "").strip())


def _links_from_description_text(description: Optional[str]) -> List[Dict[str, str]]:
    """Extract http(s) and www.* URLs from free-text description; same shape as featured links."""
    if not description:
        return []
    from urllib.parse import urlparse

    out: List[Dict[str, str]] = []
    seen: set[str] = set()

    def add_raw(raw: str) -> None:
        u = _strip_url_trailing_punct(raw.strip())
        if not u or len(u) < 4:
            return
        if re.match(r"(?i)^https?://", u):
            norm = normalize_external_url(u)
        elif re.match(r"(?i)^www\.", u):
            norm = normalize_external_url(u)
        else:
            return
        key = norm.lower().rstrip("/")
        if key in seen:
            return
        seen.add(key)
        try:
            host = (urlparse(norm).hostname or "").lower() or norm
        except ValueError:
            host = norm
        out.append({"title": host, "url": norm})

    for m in re.finditer(r"https?://[^\s<>()\[\]\"']+", description, re.I):
        add_raw(m.group(0))
    for m in re.finditer(r"(?<![@\w/])www\.[^\s<>()\[\]\"']+", description, re.I):
        add_raw(m.group(0))
    return out


def _merge_link_lists(featured: List[Dict[str, str]], extra: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Featured About links first; append description URLs not already present (case-insensitive URL)."""
    seen: set[str] = set()
    merged: List[Dict[str, str]] = []
    for row in featured:
        u = normalize_external_url((row.get("url") or "").strip())
        if not u:
            continue
        key = u.lower().rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        merged.append({"title": row.get("title") or "", "url": u})
    for row in extra:
        u = normalize_external_url((row.get("url") or "").strip())
        if not u:
            continue
        key = u.lower().rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        merged.append({"title": row.get("title") or "", "url": u})
    return merged
def iter_channel_external_link_view_models(obj: Any) -> List[Dict[str, str]]:
    """DFS: collect channelExternalLinkViewModel link + title."""
    out: List[Dict[str, str]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "channelExternalLinkViewModel" in node:
                m = node["channelExternalLinkViewModel"]
                if not isinstance(m, dict):
                    return
                link_obj = m.get("link") or {}
                raw_url = _coerce_text(link_obj.get("content") if isinstance(link_obj, dict) else None)
                title = _coerce_text(m.get("title"))
                if raw_url:
                    out.append(
                        {
                            "title": title or "",
                            "url": normalize_external_url(raw_url),
                        }
                    )
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(obj)
    return out


def _walk_dicts(node: Any) -> Iterator[Dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk_dicts(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_dicts(v)


def parse_compact_count(label: Optional[str]) -> Optional[int]:
    """
    Parse YouTube-style count labels, e.g. ``1.2M subscribers``, ``12,345 videos``, ``3.4B views``.
    Returns None for hidden or unparseable values.
    """
    if not label:
        return None
    s = str(label).strip()
    if not s:
        return None
    low = s.lower()
    if "hidden" in low:
        return None
    s = re.sub(r"(?i)\s*(subscribers?|videos?|views?)\s*$", "", s).strip()
    s = s.replace(",", "")
    m = re.match(r"^([\d.]+)\s*([kKmMbB])?", s, re.I)
    if not m:
        return None
    num_s, suf = m.group(1), (m.group(2) or "").upper()
    try:
        n = float(num_s)
    except ValueError:
        return None
    mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(suf, 1)
    return int(n * mult)


def infer_channel_type_from_about(
    title: Optional[str],
    description: Optional[str],
    keywords: Optional[str],
) -> str:
    """
    Rough government channel class from About title, description, and optional
    ``channelMetadataRenderer.keywords``. Order matches ``load_youtube_events_to_postgres``
    / ``load_youtube_channels_bronze`` keyword lists, with stronger **school** signals first
    so titles like "County Public Schools" do not become **county**.
    """
    parts: List[str] = []
    for t in (title, description, keywords):
        if t and str(t).strip():
            parts.append(str(t).strip())
    if not parts:
        return "unknown"
    blob = " ".join(parts).lower()

    school_strong = (
        "school district",
        "independent school district",
        "unified school district",
        "community unit school district",
        "public schools",
        " board of education",
        "school board",
        "charter school",
        "intermediate school district",
    )
    if any(m in blob for m in school_strong):
        return "school"
    if re.search(r"\b(isd|cusd|susd|pusd|lausd|fusd|csd|usd)\b", blob):
        return "school"

    gov_muni = (
        "city of ",
        "town of ",
        "village of ",
        "borough of ",
        "municipality of ",
        "municipal government",
    )
    if any(m in blob for m in gov_muni):
        return "municipal"
    if any(word in blob for word in ("city", "town", "village", "municipal")):
        return "municipal"
    if "county" in blob:
        return "county"
    if any(word in blob for word in ("state", "commonwealth")):
        return "state"
    if any(word in blob for word in ("school", "district", "education")):
        return "school"
    return "unknown"


def _first_about_renderer(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for d in _walk_dicts(data):
        r = d.get("channelAboutFullMetadataRenderer")
        if isinstance(r, dict):
            return r
    return None


def _first_channel_metadata_renderer(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for d in _walk_dicts(data):
        r = d.get("channelMetadataRenderer")
        if isinstance(r, dict):
            return r
    return None


def _walk_dicts_with_path(node: Any, path: str = "") -> Iterator[Tuple[str, Dict[str, Any]]]:
    if isinstance(node, dict):
        yield path, node
        for k, v in node.items():
            seg = f"{path}/{k}" if path else str(k)
            yield from _walk_dicts_with_path(v, seg)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            seg = f"{path}[{i}]"
            yield from _walk_dicts_with_path(v, seg)


def _fallback_channel_view_count_from_yt(data: Dict[str, Any]) -> Optional[int]:
    """
    Total views are often under ``aboutChannelRenderer`` / engagement panel JSON, not
    ``channelAboutFullMetadataRenderer``. Collect ``viewCountText`` values and prefer
    paths that look channel-level; ignore featured-video snippets on the About layout.
    """
    hits: List[Tuple[str, int]] = []
    for pth, d in _walk_dicts_with_path(data):
        if "viewCountText" not in d:
            continue
        label = _coerce_text(d.get("viewCountText"))
        if not label or "view" not in label.lower():
            continue
        n = parse_compact_count(label)
        if n is None:
            continue
        hits.append((pth, n))
    if not hits:
        return None

    def _path_is_video_snippet(p: str) -> bool:
        pl = p.lower()
        return any(
            x in pl
            for x in (
                "channelvideoplayer",
                "compactvideorenderer",
                "videorenderer",
                "lockupviewmodel",
            )
        )

    preferred = [
        h
        for h in hits
        if not _path_is_video_snippet(h[0])
        and (
            "aboutchannel" in h[0].lower()
            or "channelaboutfullmetadata" in h[0].lower()
        )
    ]
    pick = preferred if preferred else [h for h in hits if not _path_is_video_snippet(h[0])]
    pick = pick if pick else hits
    if len(pick) == 1:
        return pick[0][1]
    return max(h[1] for h in pick)


def _first_channel_header_stats_row(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Locate a dict with subscriber + video counts (legacy channel header / tabbed header).
    Older JSON used ``videosCountText``; some layouts use ``videoCountText`` next to subscribers.
    """
    for d in _walk_dicts(data):
        if "subscriberCountText" not in d:
            continue
        if "videosCountText" in d or "videoCountText" in d:
            return d
    return None


def _first_about_channel_view_model(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """About-tab engagement panel: counts are plain strings on ``aboutChannelViewModel``."""
    for d in _walk_dicts(data):
        vm = d.get("aboutChannelViewModel")
        if isinstance(vm, dict) and (
            vm.get("subscriberCountText") is not None
            or vm.get("videoCountText") is not None
            or vm.get("videosCountText") is not None
        ):
            return vm
    return None


def _extract_about_metadata_from_yt(data: Dict[str, Any]) -> ChannelAboutSnapshot:
    links = iter_channel_external_link_view_models(data)
    title: Optional[str] = None
    description: Optional[str] = None
    channel_keywords: Optional[str] = None
    subs: Optional[int] = None
    videos: Optional[int] = None
    views: Optional[int] = None

    cm = _first_channel_metadata_renderer(data)
    if cm:
        t = cm.get("title")
        if isinstance(t, str):
            title = t.strip() or None
        else:
            title = _coerce_text(t) or title
        k = cm.get("keywords")
        if isinstance(k, str) and k.strip():
            channel_keywords = k.strip()
        elif k is not None:
            channel_keywords = _coerce_text(k) or channel_keywords

    about = _first_about_renderer(data)
    if about:
        description = _coerce_text(about.get("description")) or description
        views = parse_compact_count(_coerce_text(about.get("viewCountText"))) or views

    # Many channels no longer ship channelAboutFullMetadataRenderer in initial ytInitialData;
    # description often lives on metadata.channelMetadataRenderer.description (plain string).
    if cm and not description:
        d = cm.get("description")
        if isinstance(d, str) and d.strip():
            description = d.strip()
        else:
            description = _coerce_text(d) or description

    if not description:
        mf = data.get("microformat")
        if isinstance(mf, dict):
            mdr = mf.get("microformatDataRenderer")
            if isinstance(mdr, dict):
                d2 = mdr.get("description")
                if isinstance(d2, str) and d2.strip():
                    description = d2.strip()

    stats = _first_channel_header_stats_row(data)
    if stats:
        subs = parse_compact_count(_coerce_text(stats.get("subscriberCountText"))) or subs
        vlabel = stats.get("videosCountText") or stats.get("videoCountText")
        videos = parse_compact_count(_coerce_text(vlabel)) or videos

    # New About layout: subscriberCountText / videoCountText as plain strings (not same dict as header).
    acvm = _first_about_channel_view_model(data)
    if acvm:
        subs = parse_compact_count(_coerce_text(acvm.get("subscriberCountText"))) or subs
        videos = (
            parse_compact_count(_coerce_text(acvm.get("videoCountText")))
            or parse_compact_count(_coerce_text(acvm.get("videosCountText")))
            or videos
        )
        views = parse_compact_count(_coerce_text(acvm.get("viewCountText"))) or views
        if not description:
            dvm = acvm.get("description")
            if isinstance(dvm, str) and dvm.strip():
                description = dvm.strip()
            else:
                description = _coerce_text(acvm.get("description")) or description

    if views is None:
        views = _fallback_channel_view_count_from_yt(data) or views

    return ChannelAboutSnapshot(
        links=links,
        channel_title=title,
        channel_description=description,
        channel_keywords=channel_keywords,
        subscriber_count=subs,
        video_count=videos,
        view_count=views,
    )


def _apply_regex_html_fallback(html: str, snap: ChannelAboutSnapshot) -> None:
    """Fill missing fields using loose regex on raw HTML (YouTube changes JSON shape often)."""
    if snap.subscriber_count is None:
        # Plain string (aboutChannelViewModel): "subscriberCountText":"4.5M subscribers"
        m = re.search(r'"subscriberCountText"\s*:\s*"([^"]+)"', html)
        if m:
            snap.subscriber_count = parse_compact_count(m.group(1))
        if snap.subscriber_count is None:
            m = re.search(
                r'"subscriberCountText".*?"(?:simpleText|text)"\s*:\s*"([^"]+)"',
                html,
                re.DOTALL,
            )
            if m:
                snap.subscriber_count = parse_compact_count(m.group(1))
    if snap.video_count is None:
        # Plain string (aboutChannelViewModel): "videoCountText":"418 videos"
        m = re.search(r'"videoCountText"\s*:\s*"([^"]+)"', html)
        if m:
            snap.video_count = parse_compact_count(m.group(1))
        if snap.video_count is None:
            m = re.search(r'"videosCountText"[^}]*?"text"\s*:\s*"([\d,]+)"', html, re.DOTALL)
            if m:
                snap.video_count = parse_compact_count(m.group(1) + " videos")
    if snap.view_count is None:
        # Prefer plain JSON string: "viewCountText": "12,345 views" (aboutChannelRenderer / panel).
        m = re.search(r'"viewCountText"\s*:\s*"([^"]+)"', html)
        if m:
            snap.view_count = parse_compact_count(m.group(1))
        if snap.view_count is None:
            m = re.search(
                r'"viewCountText"\s*:\s*\{[^}]{0,400}?"(?:simpleText|text)"\s*:\s*"([^"]+)"',
                html,
                re.DOTALL,
            )
            if m:
                snap.view_count = parse_compact_count(m.group(1))
    if snap.channel_title is None:
        m = re.search(r'"channelMetadataRenderer"[^}]*?"title"\s*:\s*"([^"]+)"', html, re.DOTALL)
        if m:
            snap.channel_title = m.group(1)


def parse_channel_about_page(html: str) -> ChannelAboutSnapshot:
    data = extract_yt_initial_data(html)
    if not data:
        snap = ChannelAboutSnapshot(links=[])
        _apply_regex_html_fallback(html, snap)
    else:
        snap = _extract_about_metadata_from_yt(data)
        _apply_regex_html_fallback(html, snap)
    ct = infer_channel_type_from_about(
        snap.channel_title,
        snap.channel_description,
        snap.channel_keywords,
    )
    return replace(
        snap,
        links=_merge_link_lists(snap.links, _links_from_description_text(snap.channel_description)),
        channel_type=ct,
    )


def parse_about_page_html(html: str) -> List[Dict[str, str]]:
    """Return outbound links: featured About-tab links plus URLs parsed from the description."""
    return parse_channel_about_page(html).links


def fetch_channel_about_html(channel_id: str, *, timeout_s: float = 30.0) -> str:
    cid = (channel_id or "").strip()
    if not cid or not re.match(r"^[A-Za-z0-9_-]{10,}$", cid):
        raise ValueError(f"invalid channel_id: {channel_id!r}")
    url = ABOUT_URL.format(channel_id=cid)
    headers = {"User-Agent": DEFAULT_UA, "Accept-Language": "en-US,en;q=0.9"}
    with httpx.Client(timeout=timeout_s, follow_redirects=True, headers=headers) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def fetch_channel_about_bundle(channel_id: str, *, timeout_s: float = 30.0) -> ChannelAboutSnapshot:
    html = fetch_channel_about_html(channel_id, timeout_s=timeout_s)
    return parse_channel_about_page(html)


def fetch_channel_about_links(channel_id: str, *, timeout_s: float = 30.0) -> List[Dict[str, str]]:
    return fetch_channel_about_bundle(channel_id, timeout_s=timeout_s).links


def ensure_bronze_events_channels_link_columns(conn) -> None:
    """Add About-tab scrape columns if missing (idempotent)."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            ALTER TABLE bronze.bronze_events_channels
                ADD COLUMN IF NOT EXISTS channel_external_links JSONB;
            """
        )
        cur.execute(
            """
            ALTER TABLE bronze.bronze_events_channels
                ADD COLUMN IF NOT EXISTS channel_external_links_fetched_at TIMESTAMPTZ;
            """
        )
        cur.execute(
            """
            ALTER TABLE bronze.bronze_events_channels
                ADD COLUMN IF NOT EXISTS channel_description TEXT;
            """
        )
        cur.execute(
            """
            ALTER TABLE bronze.bronze_events_channels
                ADD COLUMN IF NOT EXISTS view_count BIGINT;
            """
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def _truncate(s: Optional[str], max_len: int) -> Optional[str]:
    if s is None:
        return None
    t = s.strip()
    if not t:
        return None
    return t if len(t) <= max_len else t[:max_len]


def upsert_channel_about_scrape(
    conn,
    channel_id: str,
    snap: ChannelAboutSnapshot,
    *,
    channel_url: Optional[str] = None,
) -> None:
    """Insert or update bronze row with About links + optional channel metadata."""
    cid = (channel_id or "").strip()
    curl = (channel_url or "").strip() or f"https://www.youtube.com/channel/{cid}"
    links_json = json.dumps(snap.links)
    title = _truncate(snap.channel_title, 500)
    desc = snap.channel_description
    subs = snap.subscriber_count
    vids = snap.video_count
    views = snap.view_count
    ctype = (snap.channel_type or "unknown").strip() or "unknown"
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO bronze.bronze_events_channels (
                channel_id,
                channel_url,
                channel_title,
                channel_description,
                channel_type,
                subscriber_count,
                video_count,
                view_count,
                in_localview,
                in_jurisdictions_details,
                channel_external_links,
                channel_external_links_fetched_at,
                last_updated
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                FALSE, FALSE,
                %s::jsonb,
                NOW(),
                CURRENT_TIMESTAMP
            )
            ON CONFLICT (channel_id) DO UPDATE SET
                channel_external_links = EXCLUDED.channel_external_links,
                channel_external_links_fetched_at = EXCLUDED.channel_external_links_fetched_at,
                last_updated = CURRENT_TIMESTAMP,
                channel_url = CASE
                    WHEN NULLIF(BTRIM(bronze.bronze_events_channels.channel_url), '') IS NOT NULL
                    THEN bronze.bronze_events_channels.channel_url
                    ELSE EXCLUDED.channel_url
                END,
                channel_title = COALESCE(EXCLUDED.channel_title, bronze.bronze_events_channels.channel_title),
                channel_description = COALESCE(
                    EXCLUDED.channel_description, bronze.bronze_events_channels.channel_description
                ),
                channel_type = CASE
                    WHEN NULLIF(EXCLUDED.channel_type, 'unknown') IS NOT NULL
                    THEN EXCLUDED.channel_type
                    ELSE bronze.bronze_events_channels.channel_type
                END,
                subscriber_count = COALESCE(EXCLUDED.subscriber_count, bronze.bronze_events_channels.subscriber_count),
                video_count = COALESCE(EXCLUDED.video_count, bronze.bronze_events_channels.video_count),
                view_count = COALESCE(EXCLUDED.view_count, bronze.bronze_events_channels.view_count)
            """,
            (cid, curl, title, desc, ctype, subs, vids, views, links_json),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def _database_url() -> str:
    return os.getenv("NEON_DATABASE_URL_DEV", "postgresql://postgres:password@localhost:5433/open_navigator")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Fetch YouTube channel About links (ytInitialData).")
    p.add_argument("--channel-id", action="append", dest="channel_ids", default=[], help="Channel id (repeatable)")
    p.add_argument(
        "--where-null",
        action="store_true",
        help="Rows in bronze.bronze_events_channels with channel_external_links_fetched_at IS NULL",
    )
    p.add_argument(
        "--from-bronze-youtube",
        action="store_true",
        help="Distinct channel_id from bronze.bronze_events_youtube not yet fetched (joins channels table)",
    )
    p.add_argument(
        "--refetch-all",
        action="store_true",
        help="Re-scrape every channel_id in bronze.bronze_events_channels (ignores fetched_at)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max channels from DB selectors (--where-null, --from-bronze-youtube, --refetch-all); 0 = no limit",
    )
    p.add_argument("--sleep", type=float, default=1.25, help="Seconds between HTTP requests")
    p.add_argument("--dry-run", action="store_true", help="Fetch and print JSON only; do not write DB")
    p.add_argument("--database-url", default=None, help="Postgres URL (default NEON_DATABASE_URL_DEV)")
    args = p.parse_args(argv)

    ids: List[str] = list(args.channel_ids or [])
    db_url = args.database_url or _database_url()

    if args.refetch_all or args.where_null or args.from_bronze_youtube:
        conn = psycopg2.connect(db_url)
        try:
            ensure_bronze_events_channels_link_columns(conn)
            cur = conn.cursor()
            lim = ""
            params: Tuple[Any, ...] = ()
            if args.limit and args.limit > 0:
                lim = " LIMIT %s"
                params = (args.limit,)
            if args.refetch_all:
                cur.execute(
                    f"""
                    SELECT channel_id
                    FROM bronze.bronze_events_channels
                    WHERE channel_id IS NOT NULL
                      AND BTRIM(channel_id) != ''
                    ORDER BY channel_id
                    {lim}
                    """,
                    params,
                )
                rows = [r[0] for r in cur.fetchall() if r[0]]
                ids.extend(rows)
                logger.info("--refetch-all added {} channel_id(s)", len(rows))
            else:
                if args.where_null:
                    cur.execute(
                        f"""
                        SELECT channel_id
                        FROM bronze.bronze_events_channels
                        WHERE channel_id IS NOT NULL
                          AND BTRIM(channel_id) != ''
                          AND channel_external_links_fetched_at IS NULL
                        ORDER BY channel_id
                        {lim}
                        """,
                        params,
                    )
                    rows = [r[0] for r in cur.fetchall() if r[0]]
                    ids.extend(rows)
                    logger.info("--where-null added {} channel_id(s)", len(rows))
                if args.from_bronze_youtube:
                    cur.execute(
                        f"""
                        SELECT DISTINCT y.channel_id
                        FROM bronze.bronze_events_youtube y
                        LEFT JOIN bronze.bronze_events_channels c
                            ON c.channel_id = y.channel_id
                        WHERE y.channel_id IS NOT NULL
                          AND BTRIM(y.channel_id) != ''
                          AND (c.channel_external_links_fetched_at IS NULL)
                        ORDER BY 1
                        {lim}
                        """,
                        params,
                    )
                    rows = [r[0] for r in cur.fetchall() if r[0]]
                    ids.extend(rows)
                    logger.info("--from-bronze-youtube added {} channel_id(s)", len(rows))
            cur.close()
        finally:
            conn.close()

    ids = [i.strip() for i in ids if i and str(i).strip()]
    if not ids:
        logger.error(
            "No channel ids: use --channel-id, --where-null, --from-bronze-youtube, or --refetch-all"
        )
        return 2

    seen = set()
    unique_ids = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            unique_ids.append(i)

    if args.dry_run:
        for cid in unique_ids:
            snap = fetch_channel_about_bundle(cid)
            row = {"channel_id": cid, **asdict(snap)}
            print(json.dumps(row, indent=2, ensure_ascii=False))
            time.sleep(args.sleep)
        return 0

    conn = psycopg2.connect(db_url)
    try:
        ensure_bronze_events_channels_link_columns(conn)
        for cid in unique_ids:
            try:
                snap = fetch_channel_about_bundle(cid)
                upsert_channel_about_scrape(conn, cid, snap)
                logger.success(
                    "{} -> {} link(s); type={}; title={:.60}; subs={}; videos={}; views={}",
                    cid,
                    len(snap.links),
                    snap.channel_type,
                    (snap.channel_title or "")[:60],
                    snap.subscriber_count,
                    snap.video_count,
                    snap.view_count,
                )
            except Exception as e:
                logger.exception("failed {}: {}", cid, e)
            time.sleep(args.sleep)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
