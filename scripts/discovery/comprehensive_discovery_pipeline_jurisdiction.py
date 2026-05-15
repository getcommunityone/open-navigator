"""
Meetings / minutes scraper (separate from ``ComprehensiveDiscoveryPipeline``).

Goals:
- Start from a jurisdiction homepage (or ``intermediate.int_jurisdiction_websites``).
- Prefer **site search** when present, detected from the **homepage HTML** (no blind probes):
  WordPress ``/?s=…`` only when WP markers exist; **Granicus OpenCivic** ``Content-search?…(keyword=)``
  templates when linked; **Revize / ASP** portals from nav — see ``extract_site_search_portal_urls``,
  ``html_suggests_wordpress_site``, ``opencivic_content_search_query_variants``.
- Apply **vendor-style heuristics** (Legistar, Granicus, CivicClerk, …) in
  ``meetings_platform_heuristics`` — same spirit as City-Bureau city-scrapers, without Scrapy.
- Follow agenda / minutes / meeting links from the homepage and search results.
- Optionally seed the crawl from **XML sitemaps** (``/sitemap.xml``, ``robots.txt`` ``Sitemap:``,
  WordPress ``wp-sitemap.xml``, …): meeting-ish ``<loc>`` URLs are enqueued so pages that are not
  linked in HTML can still be fetched. Sitemap HTTP fetches use the same **Playwright** fallback as
  page HTML when ``httpx`` sees ``403``/TLS errors (raw response bytes, valid XML). Disable with
  ``SCRAPED_MEETINGS_SITEMAP=false``. Raw
  responses are stored under ``_sitemaps/raw/`` with ``sitemap_inventory.json`` (bundle metadata)
  and ``sitemap_rows.ndjson`` (one flat JSON object per line for database ingest). Disable those
  writes with ``SCRAPED_MEETINGS_SITEMAP_PERSIST=false`` (URLs are still enqueued when sitemaps are on).
- Follow **linked** meeting-archive URLs on other hosts when the path looks like a commission/board
  archive (e.g. ``/commission-meetings/``); after landing, treat same host as ``page_url`` for PDFs
  (see :func:`meetings_platform_heuristics.is_linked_local_meeting_microsite`).
- Handle URLs with fragments (e.g. ``.../monthly-meetings/#toggle-id-2``) by fetching the base URL
  and still collecting same-page anchors.
- Collect **YouTube** video and channel links from crawled HTML (anchors, embeds, ``data-src``);
  stored in ``_manifest.json`` under ``youtube`` (not downloaded). After the crawl, each **video**
  URL is checked against YouTube **oEmbed** (title / channel name) and scored for meeting-like
  language (agenda, council, commission, webcast, …). Meeting-related **search keywords** (including
  ``youtube``, ``video``, ``webcast``, ``live``) are only sent to templates we recognized.
- Collect **other** meeting / stream platforms (Vimeo, Facebook video, Twitch, Granicus, Zoom,
  Teams, Google Meet, Wistia, Brightcove, ``.m3u8`` HLS, …) into ``other_video_streams`` in the
  manifest (URLs are recorded; most are not downloaded). **SuiteOne** (``*.suiteonemedia.com``): after any SuiteOne
  HTML fetch, the crawl also enqueues ``https://{host}/?embed=1`` (full meeting index), not only when
  the jurisdiction homepage is on that host. JWPlayer inline ``var src`` and S3
  ``suiteone.*.videofiles`` ``.mp4`` URLs are captured into ``other_video_streams``. **SuiteOne video
  defaults:** MP4s are downloaded (``SCRAPED_MEETINGS_DOWNLOAD_SUITEONE_MP4`` defaults on; set
  ``false`` to skip). **Opus:** ``SCRAPED_MEETINGS_DOWNLOAD_MP4_OPUS`` defaults **on**; when ``ffmpeg``
  is on ``PATH``, audio is transcoded to **Opus**. **Cleanup:** ``SCRAPED_MEETINGS_DELETE_MP4_AFTER_OPUS``
  defaults **on** so the MP4 is removed after a successful Opus encode (set ``false`` to keep both).
  A sweep at the start/end of the video phase also deletes stale ``*_suiteone.mp4`` files when a
  sibling Opus exists (from earlier runs). Opus must be at least ``SCRAPED_MEETINGS_MIN_OPUS_BYTES_FOR_MP4_DELETE``
  bytes (default 102400) before the MP4 is removed.
  ``*.asset.json`` records source URL and paths. **Agendas:** SuiteOne
  ``/event/GetAgendaFile/…`` and ``/event/GetMinutesFile/…`` links (no ``.pdf`` suffix) are downloaded
  as PDFs like other meeting documents.
- **PDF URLs** written to ``_manifest.json`` ``pdfs[].url`` are **path-normalized** (e.g. spaces
  percent-encoded as ``%20``) so manifests and downstream loaders match RFC-safe URLs used for GET.

- Download PDFs (and optional HTML snapshots of key pages) under:

    ``{root}/{state}/{jurisdiction_type}/{jurisdiction_id}/{year}/``

Each fetched page is also written under ``_crawl_html/page_*.html``. When
``SCRAPED_MEETINGS_HTML_READABLE_TXT`` is true (default), a sibling ``page_*.readable.txt`` is
written: scripts/styles removed and visible text flattened for reading in any editor.

Default ``root`` is the repo cache **``data/cache/scraped_meetings``** (same ``data/cache`` family
as wikidata JSON). Override with env ``SCRAPED_MEETINGS_ROOT`` (e.g. a Google Drive mount) or
``--output-root``. ``.env`` is loaded first.

TLS: set ``SCRAPED_MEETINGS_HTTP_VERIFY=false`` only if you must (corporate MITM / broken CA store).
When verification fails, the scraper may still fetch the same URL via **Playwright** (Chromium’s
trust store), logging ``meetings_playwright_fallback_ok_after_httpx_tls_error``.

CAPTCHA / anti-bot: successful HTTP 200 responses that look like Cloudflare hCaptcha/reCAPTCHA
interstitials (and a few other WAFs) are treated as fetch failures with reason ``captcha:…`` and
log event ``meetings_fetch_captcha_or_bot_wall``. When ``SCRAPED_MEETINGS_PLAYWRIGHT_FALLBACK`` is
true (default), the scraper retries the same URL with **headless Chromium (Playwright)** after
``httpx`` gets ``401``/``403``/``429``/``202`` or a captcha-like ``200`` body. Install browsers once:
``playwright install chromium``. Set ``SCRAPED_MEETINGS_PLAYWRIGHT_FALLBACK=false`` to skip.
Concurrency is capped by ``SCRAPED_MEETINGS_PLAYWRIGHT_MAX_CONCURRENT`` (default ``2``).
On WSL/Ubuntu, if Chromium fails to start, run ``sudo .venv/bin/python -m playwright install-deps``
or set ``SCRAPED_MEETINGS_PLAYWRIGHT_CHROMIUM_EXECUTABLE``. If Playwright returns
``playwright_http_403`` (Akamai / bot rules), try ``SCRAPED_MEETINGS_PLAYWRIGHT_CHANNEL=chrome`` with
Google Chrome installed in WSL, ``SCRAPED_MEETINGS_PLAYWRIGHT_HEADLESS=false`` when a display is
available, or run outside WSL. ``SCRAPED_MEETINGS_PLAYWRIGHT_STEALTH=false`` disables
``playwright-stealth``. Also try a different network or an alternate ``website_url`` in
``int_jurisdiction_websites``.

Timeouts: ``--timeout`` applies to **connect** and **read** (and write/pool). Optional
``SCRAPED_MEETINGS_FETCH_RETRIES`` (default ``1``) adds backoff retries after ``ConnectTimeout`` /
``ReadTimeout`` only.

Homepage fallback: when ``SCRAPED_MEETINGS_HOME_FALLBACK`` is true (default), ``scrape`` loads every
distinct ``website_url`` for the jurisdiction from ``int_jurisdiction_websites`` in source-priority
order (GSA → USCM → NCES directory → NACO), probes each until one returns HTML with at least
``SCRAPED_MEETINGS_HOME_MIN_HTML_CHARS`` characters (default ``800``), and crawls that URL. If every
probe fails, the first-priority URL is still used (same as before). Set ``SCRAPED_MEETINGS_HOME_FALLBACK=false``
to only use the URL passed on the CLI / from the batch row.

Contact hints: when ``SCRAPED_MEETINGS_CONTACT_EXTRACT`` is true (default), each fetched HTML page is
scanned for ``mailto:`` / ``tel:`` links and common email / US phone patterns. Results are merged
into ``_manifest.json`` under ``extracted_contacts`` (deduplicated lists plus optional ``by_page``).
This is best-effort crawl data, not authoritative directory information.

Examples (Yuma County CO):
- Search: https://yumacounty.net/?s=meetings
- Page: https://yumacounty.net/monthly-meetings/
- Fragment: https://yumacounty.net/monthly-meetings/#toggle-id-2

Run::

    .venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_meetings \\
        --state CO --geoid 08125 --type county --url https://yumacounty.net/

    .venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_meetings \\
        --state CO --geoid 08125 --type county --from-db

    # Parallel batch (many sites, long timeouts)
    .venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_meetings \\
        --batch-from-db --state AL --type county --concurrency 8 --timeout 120

    .venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_meetings \\
        --state AL --type county --geoids 01001,01003,01009 --from-db --concurrency 6 --timeout 120

    # Rerun counties whose cached manifest is failed (0 pages) or shallow (few pages; see --shallow-max-pages)
    .venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_meetings \\
        --state AL --type county --from-db --retry-failed-shallow --concurrency 6 --timeout 120
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote, parse_qs, unquote, urlparse, urlunparse

import httpx
from loguru import logger

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.discovery.jurisdiction_discovery_pipeline import (
    INT_JURISDICTION_WEBSITES_TABLE,
    WEBSITE_SOURCE_PRIORITY_ORDER_SQL,
    jurisdiction_pk_from_geoid,
    resolve_database_url,
)
from scripts.utils.gdrive_paths import (
    resolve_scraped_meetings_output_root,
    scraped_meetings_root_resolution_note,
)
from scripts.utils.http_url_normalize import normalize_http_url_path_encoding as _normalize_http_url_path_encoding
from scripts.discovery.contact_extract_from_html import (
    extract_contacts_from_page,
    merge_contact_manifest_rows,
)
from scripts.discovery.meetings_platform_heuristics import (
    classify_document,
    detect_meeting_stacks,
    extract_meeting_urls,
    extract_opencivic_content_search_portals,
    extract_other_video_stream_refs,
    extract_site_search_portal_urls,
    extract_youtube_refs,
    html_suggests_wordpress_site,
    merge_stack_hints,
    opencivic_content_search_query_variants,
    score_youtube_meeting_relevance,
    site_search_portal_variants,
    youtube_url_for_oembed,
)
from scripts.discovery.meetings_sitemap_discovery import (
    SitemapPersistConfig,
    discover_meeting_candidate_urls_from_sitemaps,
)
from scripts.discovery.meetings_playwright_fetch import (
    fetch_html_via_playwright,
    httpx_status_should_try_playwright,
    playwright_fallback_enabled,
)

try:
    import psycopg2
except ModuleNotFoundError:  # pragma: no cover
    psycopg2 = None  # type: ignore[misc,assignment]

MEETING_HINTS = re.compile(
    r"(meetings?|minutes?|proceedings|action\s*minutes|agenda|calendar|board|commission|council|hearing|session|video|zoom|/event/|\bmedia\b)",
    re.I,
)
PDF_EXT = re.compile(r"\.pdf(\?|$)", re.I)
YEAR_IN_PATH = re.compile(r"(20\d{2})")


def _load_repo_dotenv() -> None:
    """Load ``<repo>/.env`` so ``SCRAPED_MEETINGS_ROOT`` and DB URLs apply to ``python -m ...``."""
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(_root / ".env")


def default_scraped_meetings_root() -> Path:
    _load_repo_dotenv()
    p = resolve_scraped_meetings_output_root()
    try:
        resolved = p.resolve()
    except OSError:
        resolved = p.expanduser()
    logger.info(
        "Meetings write root → {} | {}",
        resolved,
        scraped_meetings_root_resolution_note(),
    )
    return p


def _mkdir_from_existing_ancestor(target: Path) -> None:
    """
    Create ``target`` by only appending segments under the **deepest path that already exists**.

    ``Path.mkdir(parents=True)`` can try to create ``/mnt/g/My Drive`` itself, which raises
    ``PermissionError`` when Google Drive is not mounted in WSL or ``My Drive`` is missing under
    ``/mnt/g`` even though ``/mnt/g`` exists.
    """
    target = target.expanduser()
    if target.exists():
        if not os.access(target, os.W_OK):
            raise PermissionError(f"Meetings output exists but is not writable: {target}")
        return
    tail: List[str] = []
    cur = target
    while not cur.exists():
        tail.append(cur.name)
        parent = cur.parent
        if parent == cur:
            raise FileNotFoundError(
                f"Cannot create meetings output {target}: no existing directory on this path. "
                "Check SCRAPED_MEETINGS_ROOT or that the repo parent is writable (default uses data/cache/)."
            )
        cur = parent
    anchor = cur
    # Do not use ``os.access(anchor, W_OK)`` here: WSL often reports ``/mnt/g`` as non-writable even
    # when creating ``.../My Drive/...`` is valid once Google Drive is mounted. Try ``mkdir`` and
    # surface a clear error if it fails.
    step = anchor
    for part in reversed(tail):
        step = step / part
        try:
            step.mkdir(exist_ok=True)
        except (PermissionError, OSError) as exc:
            hint = ""
            if str(step).startswith("/mnt/g") or "/mnt/g/" in str(target):
                hint = (
                    " Default output is repo ``data/cache/scraped_meetings``. This path is under "
                    "``/mnt/g`` — set ``SCRAPED_MEETINGS_ROOT`` to a writable Drive folder or fix the "
                    "WSL mount so ``My Drive`` exists."
                )
            raise RuntimeError(
                f"Cannot create directory {step} while preparing meetings output {target}.{hint}"
            ) from exc


def _strip_fragment(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ""))


def _meetings_log_url(url: str, *, maxlen: int = 160) -> str:
    u = (url or "").strip()
    if len(u) <= maxlen:
        return u
    return u[: max(0, maxlen - 3)] + "..."


def _fs_safe_segment(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', "_", (s or "").strip())[:200] or "unknown"


def _meeting_pdf_disk_filename(pdf_url: str) -> str:
    """Stable unique on-disk name; SuiteOne agendas often use ``/Agenda`` without a ``.pdf`` suffix."""
    p = urlparse(pdf_url)
    tail = Path(p.path).name or "document.pdf"
    if tail.lower().endswith(".pdf"):
        return _fs_safe_segment(tail)
    stem = Path(tail).stem or "document"
    h = hashlib.sha256(pdf_url.encode("utf-8", errors="replace")).hexdigest()[:14]
    return _fs_safe_segment(f"{stem}_{h}.pdf")


def _http_response_is_pdf(resp: httpx.Response) -> bool:
    """True if the body looks like a PDF (many ``.pdf`` URLs return HTML without ``Referer`` / cookies)."""
    data = resp.content or b""
    if data.startswith(b"%PDF"):
        return True
    ct = (resp.headers.get("content-type") or "").lower()
    return "application/pdf" in ct and len(data) > 0


def _pdf_download_url_candidates(pdf_url: str) -> List[str]:
    """
    Return URLs to try for the same logical document.

    Autauga County (Revize/IIS) links ``/Documents/...`` and ``/Images/...`` but those requests
    redirect to HTML; the file is served under ``/Sites/Autauga_County/...``. Try that variant
    first when applicable.
    """
    base = (pdf_url or "").strip()
    if not base:
        return []
    alts: List[str] = []
    try:
        p = urlparse(base)
        if p.scheme not in ("http", "https") or not p.netloc:
            return [base]
        host = p.netloc.lower().split(":")[0]
        if host not in ("www.autaugaco.org", "autaugaco.org"):
            return [base]
        path = p.path or ""
        if path.startswith("/Documents/") or path.startswith("/Images/"):
            alt = urlunparse(
                (p.scheme, p.netloc, "/Sites/Autauga_County" + path, p.params, p.query, p.fragment)
            )
            if alt != base:
                alts.append(alt)
    except Exception:
        return [base]
    seen: Set[str] = set()
    out: List[str] = []
    for u in alts + [base]:
        if u not in seen:
            seen.add(u)
            out.append(_normalize_http_url_path_encoding(u))
    return out


async def _fetch_pdf_with_referers(
    client: httpx.AsyncClient,
    pdf_url: str,
    referers: List[str],
) -> tuple[Optional[httpx.Response], str]:
    """
    GET a PDF URL with ``Referer`` hints (listing page, then homepage). Returns ``(response, "")``
    when ``_http_response_is_pdf``, else ``(None, diagnostic)``.
    """
    detail = ""
    for fetch_u in _pdf_download_url_candidates(pdf_url):
        for ref in referers:
            rref = _strip_fragment(ref).strip()
            if not rref:
                continue
            try:
                pr = await client.get(
                    fetch_u,
                    follow_redirects=True,
                    headers={"Referer": rref},
                )
            except Exception as exc:
                detail = f"{fetch_u!r}:request:{exc!r}"
                continue
            if pr.status_code != 200:
                detail = f"{fetch_u!r}:http_{pr.status_code}"
                continue
            if not pr.content:
                detail = f"{fetch_u!r}:empty_body"
                continue
            if _http_response_is_pdf(pr):
                return pr, ""
            ct = pr.headers.get("content-type", "")
            prefix = (pr.content or b"")[:80]
            detail = f"{fetch_u!r}:non_pdf ct={ct!r} prefix={prefix!r}"
    return None, detail or "no_referer_matched"


def _jurisdiction_type_from_id(jurisdiction_id: str) -> str:
    if "_" in jurisdiction_id:
        return jurisdiction_id.split("_", 1)[0]
    return "unknown"


def _infer_year(url: str, fallback: int) -> int:
    """
    Pick a calendar year from the URL for output folder names.

    Regex ``finditer`` does not overlap, so ``01202026`` (Jan 20, 2026) only matched ``2020``.
    Prefer an **overlapping** scan on the decoded filename stem, then fall back to the last
    ``20xx`` in the full URL (``%2001`` in encoded paths can look like year 2001 — unquote first).
    """
    path = unquote(urlparse(url).path or "")
    stem = Path(path).stem
    found: List[Tuple[int, int]] = []
    for i in range(0, max(0, len(stem) - 3)):
        if stem[i : i + 2] != "20" or i + 4 > len(stem):
            continue
        if not stem[i + 2 : i + 4].isdigit():
            continue
        y = int(stem[i : i + 4])
        if 1990 <= y <= 2100:
            found.append((i, y))
    if found:
        return found[-1][1]
    decoded = unquote(url)
    years: List[int] = []
    for m in YEAR_IN_PATH.finditer(decoded):
        try:
            y = int(m.group(1))
            if 1990 <= y <= 2100:
                years.append(y)
        except ValueError:
            continue
    if years:
        return years[-1]
    return fallback


def _load_homepage_candidates_from_db(jurisdiction_id: str) -> List[str]:
    """
    All distinct homepage URLs for ``jurisdiction_id``, ordered by ``website_source`` priority
    (same order as batch ``load_meeting_scrape_jobs_for_state`` / ``DISTINCT ON``).
    """
    if psycopg2 is None:
        raise RuntimeError("psycopg2 required for --from-db")
    pri = WEBSITE_SOURCE_PRIORITY_ORDER_SQL
    db_url = resolve_database_url()
    out: List[str] = []
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT u FROM (
                    SELECT trim(website_url) AS u,
                           MIN({pri}) AS src_rank,
                           MIN(website_record_key) AS wrk
                    FROM {INT_JURISDICTION_WEBSITES_TABLE}
                    WHERE jurisdiction_id = %s
                      AND website_url IS NOT NULL
                      AND btrim(website_url) <> ''
                    GROUP BY trim(website_url)
                ) sub
                ORDER BY src_rank, wrk, u
                """,
                (jurisdiction_id,),
            )
            for row in cur.fetchall():
                s = str(row[0] or "").strip()
                if s:
                    out.append(s)
    return out


def _load_homepage_from_db(jurisdiction_id: str) -> Optional[str]:
    cands = _load_homepage_candidates_from_db(jurisdiction_id)
    return cands[0] if cands else None


_JURISDICTION_ID_RE = re.compile(
    r"^(?P<jtype>county|municipality|state|township|school_district)_(?P<geoid>.+)$",
    re.I,
)


def _prefer_https_homepage() -> bool:
    return (os.getenv("SCRAPED_MEETINGS_PREFER_HTTPS", "true").strip().lower() not in ("0", "false", "no", "off"))


def _meetings_home_fallback_enabled() -> bool:
    v = (os.getenv("SCRAPED_MEETINGS_HOME_FALLBACK") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _meetings_home_min_html_chars() -> int:
    raw = (os.getenv("SCRAPED_MEETINGS_HOME_MIN_HTML_CHARS") or "800").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 800


def _meetings_home_url_is_actionable(hp: str) -> bool:
    u = (hp or "").strip()
    if not u:
        return False
    try:
        p = urlparse(u)
        return bool(p.scheme in ("http", "https") and p.netloc)
    except ValueError:
        return False


def _canonical_homepage_url(url: str) -> str:
    u = (url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        u = "https://" + u.lstrip("/")
    if _prefer_https_homepage() and u.lower().startswith("http://"):
        u = "https://" + u[7:]
    return u


def load_meeting_scrape_jobs_for_state(
    state: str,
    jtype_filter: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Load ``(state, geoid, jtype, url, jurisdiction_id)`` jobs from ``int_jurisdiction_websites``.

    ``jtype_filter`` matches the ``jurisdiction_id`` prefix (``county``, ``municipality``, …).
    Pass ``None`` or ``\"all\"`` (caller) to include every supported type.
    """
    if psycopg2 is None:
        raise RuntimeError("psycopg2 required for batch DB load")
    st = (state or "").strip().upper()
    if len(st) != 2:
        return []
    want: Optional[str] = None
    if jtype_filter and jtype_filter.strip().lower() not in ("all", ""):
        want = jtype_filter.strip().lower()
        if want in ("city", "place"):
            want = "municipality"
        if want in ("school", "schools"):
            want = "school_district"
    url = resolve_database_url()
    sql = f"""
        SELECT DISTINCT ON (jurisdiction_id)
            jurisdiction_id,
            trim(website_url) AS website_url
        FROM {INT_JURISDICTION_WEBSITES_TABLE}
        WHERE jurisdiction_id IS NOT NULL
          AND UPPER(TRIM(state_code)) = %s
          AND website_url IS NOT NULL
          AND btrim(website_url) <> ''
        ORDER BY jurisdiction_id,
            ({WEBSITE_SOURCE_PRIORITY_ORDER_SQL}),
            website_record_key
    """
    jobs: List[Dict[str, str]] = []
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (st,))
            for jid_raw, wurl_raw in cur.fetchall():
                jid = str(jid_raw or "").strip()
                wurl = str(wurl_raw or "").strip()
                m = _JURISDICTION_ID_RE.match(jid)
                if not m:
                    continue
                jt = m.group("jtype").lower()
                geoid = m.group("geoid").strip()
                if want and jt != want:
                    continue
                jobs.append(
                    {
                        "state": st,
                        "geoid": geoid,
                        "jtype": jt,
                        "url": wurl,
                        "jurisdiction_id": jid,
                    }
                )
    logger.info("Loaded {} meeting scrape job(s) for state={} filter={}", len(jobs), st, want or "all")
    return jobs


def load_meeting_scrape_jobs_for_geoids(
    state: str,
    jtype: str,
    geoids_csv: str,
) -> List[Dict[str, str]]:
    """Resolve ``--geoids`` with ``_load_homepage_from_db`` per GEOID."""
    st = (state or "").strip().upper()
    jobs: List[Dict[str, str]] = []
    for part in geoids_csv.split(","):
        g = part.strip()
        if not g:
            continue
        jid = jurisdiction_pk_from_geoid(g, jtype)
        if not jid:
            logger.warning("Skipping invalid geoid/type: {} / {}", g, jtype)
            continue
        wurl = _load_homepage_from_db(jid) or ""
        if not wurl:
            logger.warning("No website_url in DB for jurisdiction_id={}", jid)
            continue
        m = _JURISDICTION_ID_RE.match(jid)
        jt = m.group("jtype").lower() if m else (jtype or "municipality").lower()
        geoid_part = m.group("geoid").strip() if m else g
        jobs.append(
            {
                "state": st,
                "geoid": geoid_part,
                "jtype": jt,
                "url": wurl,
                "jurisdiction_id": jid,
            }
        )
    return jobs


def _manifest_page_count(path: Path) -> int:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return len(d.get("pages_fetched") or [])
    except Exception:
        return -1


def collect_retry_geoids_from_scraped_manifests(
    *,
    state: str,
    jtype: str,
    scraped_root: Path,
    shallow_max_pages: int,
    retry_modes: Set[str],
) -> List[str]:
    """
    GEOIDs whose manifest under ``scraped_root`` qualifies for retry: **failed** (0 HTML pages
    fetched) or **shallow** (``1 <= pages < shallow_max_pages``). Unreadable or missing manifests
    are skipped.
    """
    st = (state or "").strip().upper()
    jt = (jtype or "").strip().lower()
    if not jt or jt == "all":
        raise ValueError("collect_retry_geoids_from_scraped_manifests requires a concrete jtype (e.g. county)")
    cap = max(2, int(shallow_max_pages))
    base = scraped_root / _fs_safe_segment(st) / _fs_safe_segment(jt)
    prefix = f"{jt}_"
    found: Set[str] = set()
    if not base.is_dir():
        return []
    for mf in sorted(base.glob(f"{jt}_*/_manifest.json")):
        n = _manifest_page_count(mf)
        if n < 0:
            continue
        folder = mf.parent.name
        if not folder.startswith(prefix):
            continue
        geoid = folder[len(prefix) :]
        if not geoid:
            continue
        if "failed" in retry_modes and n == 0:
            found.add(geoid)
        if "shallow" in retry_modes and 0 < n < cap:
            found.add(geoid)

    def _sort_key(g: str) -> Tuple[int, Any]:
        return (0, int(g)) if g.isdigit() else (1, g)

    return sorted(found, key=_sort_key)


def _site_root_url(url: str) -> str:
    """``scheme://host/`` only — WordPress ``?s=`` search lives at site root, not under deep paths."""
    u = (url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        u = "https://" + u.lstrip("/")
    p = urlparse(u)
    if not p.scheme or not p.netloc:
        raise ValueError(f"Bad URL: {url!r}")
    return f"{p.scheme}://{p.netloc}/"


def _search_url_candidates(homepage: str) -> List[str]:
    """WordPress ``/?s=`` and a few common query variants (always against site root)."""
    origin = _site_root_url(homepage).rstrip("/")
    queries = [
        "meetings",
        "minutes",
        "agenda",
        "board",
        "council",
        "commission",
        "youtube",
        "video",
        "webcast",
        "live",
    ]
    out: List[str] = []
    for q in queries:
        out.append(f"{origin}/?s={q}")
    out.append(f"{origin}/?s=meeting+minutes")
    return list(dict.fromkeys(out))


def _is_wordpress_site_search_probe(url: str) -> bool:
    """Root ``/?s=…`` probes used only when the homepage looks like WordPress."""
    try:
        p = urlparse(url)
        if (p.path or "").rstrip("/") not in ("", "/"):
            return False
        qs = parse_qs(p.query)
        return "s" in qs and bool(qs["s"])
    except Exception:
        return False


def _is_opencivic_content_search_probe(url: str) -> bool:
    low = (url or "").lower()
    return "content-search" in low and ("keyword" in low or "dlv_" in low)


def _is_probable_site_search_probe(url: str) -> bool:
    return _is_wordpress_site_search_probe(url) or _is_opencivic_content_search_probe(url)


def _discover_site_search_seed_urls(html: str, homepage: str) -> List[str]:
    """
    After the homepage HTML loads, enqueue only search URLs that match the detected stack:
    WordPress ``/?s=`` when WP markers exist; Granicus/OpenCivic ``Content-search`` templates
    when those links/forms appear.
    """
    hp_strip = _strip_fragment(homepage)
    out: List[str] = []
    if html_suggests_wordpress_site(html):
        out.extend(_search_url_candidates(homepage))
    for tmpl in extract_opencivic_content_search_portals(html, hp_strip, homepage):
        out.extend(opencivic_content_search_query_variants(tmpl))
    return list(dict.fromkeys(out))


def _host_key_for_home_match(netloc: str) -> str:
    h = (netloc or "").lower().split(":")[0]
    return h[4:] if h.startswith("www.") else h


def _is_homepage_document_url(fetch_url: str, homepage: str) -> bool:
    """
    True when ``fetch_url`` is the same document as canonical ``homepage`` (ignoring fragment).

    Allows ``http`` vs ``https`` differences after redirects; ``www`` is ignored for host match.
    """
    a, b = urlparse(fetch_url), urlparse(_strip_fragment(homepage))
    if _host_key_for_home_match(a.netloc) != _host_key_for_home_match(b.netloc):
        return False
    return (a.path or "").rstrip("/") == (b.path or "").rstrip("/")


def suiteonemedia_embed_index_url(page_or_home_url: str) -> Optional[str]:
    """
    SuiteOne exposes a full meeting index at ``/?embed=1`` on the same host.

    Call with any ``https://*.suiteonemedia.com/…`` URL (homepage, ``Web/Home.aspx``, ``/event/…``)
    so embed is enqueued even when the crawl started from a city marketing domain.
    """
    if not (page_or_home_url or "").strip():
        return None
    u = _strip_fragment(page_or_home_url.strip())
    try:
        p = urlparse(u)
    except Exception:
        return None
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    host = _host_key_for_home_match(p.netloc)
    if not host.endswith(".suiteonemedia.com"):
        return None
    return f"{p.scheme}://{p.netloc}/?embed=1"


def _meetings_download_mp4_opus_enabled() -> bool:
    """
    Default **on** when unset. Opus is only produced when ``ffmpeg`` exists at runtime.

    Set ``SCRAPED_MEETINGS_DOWNLOAD_MP4_OPUS=false`` to keep MP4-only (no transcoding).
    """
    v = (os.getenv("SCRAPED_MEETINGS_DOWNLOAD_MP4_OPUS") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _meetings_save_suiteone_mp4_to_disk() -> bool:
    """Default ``true`` (unset). Set ``SCRAPED_MEETINGS_DOWNLOAD_SUITEONE_MP4=false`` to skip MP4 GETs."""
    v = (os.getenv("SCRAPED_MEETINGS_DOWNLOAD_SUITEONE_MP4") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _meetings_download_suiteone_video_assets() -> bool:
    """Save SuiteOne MP4s and/or transcode to Opus depending on env (see module docstring)."""
    return _meetings_save_suiteone_mp4_to_disk() or _meetings_download_mp4_opus_enabled()


def _meetings_max_video_mp4_bytes() -> int:
    try:
        return max(10_000_000, int(os.getenv("SCRAPED_MEETINGS_MAX_MP4_BYTES") or str(2_147_483_648)))
    except ValueError:
        return 2_147_483_648


def _meetings_delete_mp4_after_opus() -> bool:
    """Default **on** when unset. Set ``SCRAPED_MEETINGS_DELETE_MP4_AFTER_OPUS=false`` to retain MP4 after Opus."""
    v = (os.getenv("SCRAPED_MEETINGS_DELETE_MP4_AFTER_OPUS") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _meetings_min_opus_bytes_for_mp4_cleanup() -> int:
    """Do not delete the source MP4 unless the Opus file is at least this large (avoids partial encodes)."""
    try:
        return max(1_024, int(os.getenv("SCRAPED_MEETINGS_MIN_OPUS_BYTES_FOR_MP4_DELETE") or "102400"))
    except ValueError:
        return 102_400


def _update_suiteone_asset_json_after_mp4_delete(meta_path: Path) -> None:
    """Clear ``mp4_relative_path`` in the sidecar after the MP4 file was removed."""
    if not meta_path.is_file():
        return
    try:
        sidecar = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(sidecar, dict):
        return
    sidecar["mp4_relative_path"] = None
    sidecar["mp4_deleted_after_opus"] = True
    try:
        meta_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("meetings_mp4_sidecar_update_failed path={} err={}", meta_path.name, exc)


def _prune_suiteone_mp4s_with_opus(video_dir: Path) -> int:
    """
    Remove ``*_suiteone.mp4`` files when a sibling ``*_suiteone.opus`` exists (current + prior runs).

    Used after each transcode and once at the end of the video phase. Honors
    ``SCRAPED_MEETINGS_DELETE_MP4_AFTER_OPUS`` (default on).
    """
    if not _meetings_delete_mp4_after_opus():
        return 0
    if not video_dir.is_dir():
        return 0
    min_opus = _meetings_min_opus_bytes_for_mp4_cleanup()
    removed = 0
    for mp4_path in sorted(video_dir.glob("*_suiteone.mp4")):
        stem = mp4_path.stem
        opus_path = video_dir / f"{stem}.opus"
        meta_path = video_dir / f"{stem}.asset.json"
        if not opus_path.is_file():
            continue
        try:
            if opus_path.stat().st_size < min_opus:
                logger.warning(
                    "meetings_mp4_prune_skip_small_opus mp4={} opus_bytes={} min={}",
                    mp4_path.name,
                    opus_path.stat().st_size,
                    min_opus,
                )
                continue
        except OSError:
            continue
        try:
            mp4_path.unlink(missing_ok=True)
            _update_suiteone_asset_json_after_mp4_delete(meta_path)
            removed += 1
            logger.info("meetings_mp4_pruned path={} opus={}", mp4_path.name, opus_path.name)
        except OSError as exc:
            logger.warning("meetings_mp4_prune_failed path={} err={}", mp4_path.name, exc)
    return removed


def _is_suiteone_style_mp4_asset(url: str, platform: str = "", found_via: str = "") -> bool:
    """Narrow MP4 download/transcode to SuiteOne S3/JWPlayer-surfaced URLs (not arbitrary ``.mp4``)."""
    low = (url or "").lower()
    if not low.startswith("http") or ".mp4" not in low:
        return False
    if platform == "suiteone_s3_mp4":
        return True
    if "suiteone" in low and "amazonaws.com" in low and "videofiles" in low:
        return True
    fv = (found_via or "").lower()
    if fv.startswith("jwplayer_") or fv.startswith("suiteone_"):
        return True
    return False


async def _download_suiteone_mp4_transcode_opus(
    client: httpx.AsyncClient,
    *,
    mp4_url: str,
    referer: str,
    discovered_on: str,
    found_via: str,
    platform: str,
    video_dir: Path,
    max_bytes: int,
) -> Dict[str, Any]:
    """
    Download one SuiteOne-style MP4 under ``_video_assets/``.

    Opus transcoding runs when :func:`_meetings_download_mp4_opus_enabled` (default on) **and**
    ``ffmpeg`` is on ``PATH``. Otherwise the MP4 is kept and ``*.asset.json`` records
    ``opus_relative_path`` as ``null``. When Opus succeeds and :func:`_meetings_delete_mp4_after_opus`
    is true (default), the MP4 file is removed after encoding.
    """
    want_opus = _meetings_download_mp4_opus_enabled() and bool(shutil.which("ffmpeg"))
    video_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(mp4_url.encode("utf-8", errors="replace")).hexdigest()[:20]
    stem = f"{h}_suiteone"
    mp4_path = video_dir / f"{stem}.mp4"
    opus_path = video_dir / f"{stem}.opus"
    meta_path = video_dir / f"{stem}.asset.json"
    ref = (referer or discovered_on or "").strip() or mp4_url
    headers = {"Referer": ref, "User-Agent": _DEFAULT_UA}
    short_mp4 = _meetings_log_url(mp4_url, maxlen=140)
    try:
        async with client.stream("GET", mp4_url, headers=headers, follow_redirects=True) as resp:
            if resp.status_code != 200:
                return {
                    "error": f"mp4_http_{resp.status_code}",
                    "source_mp4_url": mp4_url,
                }
            clen = (resp.headers.get("content-length") or "").strip()
            logger.info(
                "meetings_mp4_download_start url={} content_length={} max_mb={:.0f} referer={}",
                short_mp4,
                clen or "?",
                max_bytes / 1_000_000,
                _meetings_log_url(ref, maxlen=100),
            )
            ct = (resp.headers.get("content-type") or "").lower()
            if "video" not in ct and "octet-stream" not in ct and "binary" not in ct:
                # Many CDNs still use application/octet-stream for MP4.
                if "mp4" not in mp4_url.lower():
                    return {"error": f"mp4_unexpected_content_type:{ct}", "source_mp4_url": mp4_url}
            received = 0
            last_log_t = time.monotonic()
            last_log_bytes = 0
            with mp4_path.open("wb") as f:
                async for chunk in resp.aiter_bytes():
                    received += len(chunk)
                    if received > max_bytes:
                        try:
                            mp4_path.unlink(missing_ok=True)
                        except OSError:
                            pass
                        return {"error": "mp4_too_large", "source_mp4_url": mp4_url, "max_bytes": max_bytes}
                    f.write(chunk)
                    now = time.monotonic()
                    if received - last_log_bytes >= 50_000_000 or now - last_log_t >= 30.0:
                        logger.info(
                            "meetings_mp4_download_progress url={} downloaded_mb={:.1f}",
                            short_mp4,
                            received / 1_000_000,
                        )
                        last_log_t = now
                        last_log_bytes = received
            logger.info(
                "meetings_mp4_download_done url={} total_mb={:.2f}",
                short_mp4,
                received / 1_000_000,
            )
    except Exception as exc:
        try:
            mp4_path.unlink(missing_ok=True)
        except OSError:
            pass
        return {"error": f"mp4_download:{exc!r}", "source_mp4_url": mp4_url}

    def _ffmpeg() -> None:
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(mp4_path),
                "-vn",
                "-c:a",
                "libopus",
                "-b:a",
                "96k",
                str(opus_path),
            ],
            check=True,
            capture_output=True,
            timeout=7200,
        )

    rel_video = "_video_assets"
    mp4_rel = f"{rel_video}/{mp4_path.name}"
    opus_rel: Optional[str] = None

    if want_opus:
        logger.info("meetings_mp4_transcode_start path={}", mp4_path.name)
        try:
            await asyncio.to_thread(_ffmpeg)
            opus_rel = f"{rel_video}/{opus_path.name}"
            logger.info("meetings_mp4_transcode_done opus_path={}", opus_path.name)
        except subprocess.CalledProcessError as exc:
            try:
                opus_path.unlink(missing_ok=True)
            except OSError:
                pass
            return {
                "error": f"ffmpeg_failed:{(exc.stderr or b'').decode('utf-8', errors='replace')[:500]}",
                "source_mp4_url": mp4_url,
                "mp4_relative_path": mp4_rel,
            }
        except Exception as exc:
            try:
                opus_path.unlink(missing_ok=True)
            except OSError:
                pass
            return {"error": f"ffmpeg:{exc!r}", "source_mp4_url": mp4_url, "mp4_relative_path": mp4_rel}

    sidecar = {
        "schema_version": 1,
        "source_mp4_url": mp4_url,
        "discovered_on_page_url": discovered_on,
        "found_via": found_via,
        "platform": platform,
        "http_referer_used": ref,
        "opus_relative_path": opus_rel,
        "mp4_relative_path": mp4_rel,
        "transcoded_to_opus": bool(opus_rel),
    }
    try:
        meta_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    except OSError as exc:
        return {"error": f"asset_json_write:{exc}", "source_mp4_url": mp4_url, "opus_relative_path": opus_rel}

    mp4_kept_rel: Optional[str] = mp4_rel
    if want_opus and _meetings_delete_mp4_after_opus() and opus_rel:
        if opus_path.is_file() and opus_path.stat().st_size >= _meetings_min_opus_bytes_for_mp4_cleanup():
            try:
                mp4_path.unlink(missing_ok=True)
                sidecar["mp4_relative_path"] = None
                sidecar["mp4_deleted_after_opus"] = True
                meta_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
                mp4_kept_rel = None
                logger.info("meetings_mp4_deleted_after_opus mp4={} opus={}", mp4_path.name, opus_path.name)
            except OSError as exc:
                logger.warning(
                    "meetings_mp4_delete_after_opus_failed mp4={} err={} "
                    "(set SCRAPED_MEETINGS_DELETE_MP4_AFTER_OPUS=false to keep MP4s)",
                    mp4_path.name,
                    exc,
                )
        else:
            logger.warning(
                "meetings_mp4_kept_after_opus opus_too_small mp4={} opus_bytes={}",
                mp4_path.name,
                opus_path.stat().st_size if opus_path.is_file() else 0,
            )
    elif want_opus and opus_rel and not _meetings_delete_mp4_after_opus():
        logger.debug(
            "meetings_mp4_retained SCRAPED_MEETINGS_DELETE_MP4_AFTER_OPUS=false mp4={}",
            mp4_path.name,
        )

    return {
        "source_mp4_url": mp4_url,
        "discovered_on": discovered_on,
        "found_via": found_via,
        "platform": platform,
        "opus_relative_path": opus_rel,
        "mp4_relative_path": mp4_kept_rel,
        "sidecar_relative_path": f"{rel_video}/{meta_path.name}",
    }


@dataclass
class MeetingsScrapeResult:
    jurisdiction_id: str
    state: str
    homepage_url: str
    root_dir: Path
    detected_stacks: List[str] = field(default_factory=list)
    pages_fetched: List[str] = field(default_factory=list)
    pdfs_downloaded: List[Dict[str, Any]] = field(default_factory=list)
    youtube: List[Dict[str, Any]] = field(default_factory=list)
    other_video_streams: List[Dict[str, Any]] = field(default_factory=list)
    video_assets: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    homepage_url_candidates: List[str] = field(default_factory=list)
    homepage_probe_failures: List[str] = field(default_factory=list)
    extracted_contacts: Dict[str, Any] = field(default_factory=dict)


_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36 OpenNavigatorMeetings/1.0"
)


def _http_verify() -> bool:
    v = (os.getenv("SCRAPED_MEETINGS_HTTP_VERIFY") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _meetings_readable_snapshot_txt_enabled() -> bool:
    v = (os.getenv("SCRAPED_MEETINGS_HTML_READABLE_TXT") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _html_to_readable_plaintext(html: str, source_url: str, *, max_chars: int = 600_000) -> str:
    """Strip markup noise for a human-readable sidecar next to ``page_*.html``."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "template", "iframe"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    body = "\n".join(lines)
    if len(body) > max_chars:
        body = body[:max_chars] + "\n\n...[truncated]..."
    return f"Source: {source_url}\n{'=' * 72}\n\n{body}"


def _httpx_error_suggests_tls_or_cert_failure(exc: BaseException) -> bool:
    """
    True when ``httpx`` failed before a usable response, likely TLS / CA verification.

    Common on WSL without merged Windows CAs, or corporate TLS inspection. Chromium often still
    verifies successfully, so :func:`fetch_html_via_playwright` can be tried as a fallback.
    """
    blob = f"{type(exc).__name__} {exc!r}".lower()
    return any(
        s in blob
        for s in (
            "certificate_verify_failed",
            "cert_verify",
            "ssl:",
            "tlsv1",
            "tls alert",
            "handshake failure",
            "unable to get local issuer certificate",
            "unable to get issuer certificate",
            "self signed certificate",
        )
    )


def _fetch_retries() -> int:
    """Extra attempts after a timeout (``SCRAPED_MEETINGS_FETCH_RETRIES``, default 1)."""
    try:
        n = int((os.getenv("SCRAPED_MEETINGS_FETCH_RETRIES") or "1").strip())
    except ValueError:
        n = 1
    return max(0, min(n, 5))


def _non_html_body_reason(content: bytes, content_type_header: str) -> Optional[str]:
    """
    If an HTTP 200 body is clearly not HTML (image/PDF/etc.), return a short diagnostic token.

    Servers sometimes mis-label bodies or pages enqueue ``.jpg`` URLs; feeding binary to BeautifulSoup
    can raise ``AssertionError`` from the stdlib HTML parser.
    """
    ct = (content_type_header or "").lower().split(";")[0].strip()
    if ct.startswith("image/") and ct != "image/svg+xml":
        return f"content_type:{ct}"
    if ct in ("application/pdf", "application/x-pdf"):
        return f"content_type:{ct}"
    if ct.startswith(("video/", "audio/")):
        return f"content_type:{ct}"
    head = content[:32] if content else b""
    if head.startswith(b"\xff\xd8\xff"):
        return "magic_jpeg"
    if head.startswith(b"%PDF"):
        return "magic_pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "magic_png"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "magic_gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "magic_webp"
    if head.startswith(b"BM") and len(content) > 20:
        return "magic_bmp"
    return None


def _captcha_or_bot_wall_reason(html: str, headers: Any) -> Optional[str]:
    """
    If the HTTP 200 body looks like a bot / CAPTCHA interstitial (not a normal HTML site),
    return a short reason token for logging and ``(None, "captcha:…")`` from the fetch layer.

    Heuristics are conservative on **large** pages so we do not flag normal sites that embed a
    small reCAPTCHA/hCaptcha widget in the footer.
    """
    if not html or not isinstance(html, str):
        return None
    n = len(html)
    low = html.lower()
    head = low[:120000]

    # Cloudflare JS / managed challenge (common small-body case)
    if "__cf_chl" in head or "/cdn-cgi/challenge-platform/" in head or "cf-chl-seq" in head:
        return "cloudflare_js_challenge"
    if "checking your browser before accessing" in head:
        return "cloudflare_interstitial"
    if "just a moment" in head and (
        "cloudflare" in head or "cf-ray" in head or "challenges.cloudflare.com" in head
    ):
        return "cloudflare_just_a_moment"
    try:
        srv = (headers.get("server") or "").lower() if headers is not None else ""
    except Exception:
        srv = ""
    if srv == "cloudflare" and n < 8000 and ("challenge" in head or "ray id" in head):
        return "cloudflare_challenge_short_html"

    # Incapsula / Imperva
    if "incapsula incident id" in head or "_incapsula_resource_" in head:
        return "incapsula_block"
    if "request unsuccessful: incapsula incident" in head:
        return "incapsula_block"

    # Google interstitial
    if "detected unusual traffic" in head and "google" in head:
        return "google_unusual_traffic"

    # DataDome / geo captcha delivery (usually short pages)
    if n < 12000 and "geo.captcha-delivery.com" in head:
        return "geo_captcha_delivery"

    # PerimeterX / HUMAN
    if "perimeterx" in head or "_pxcaptcha" in head or "px-captcha" in head:
        return "perimeterx_challenge"

    # Embedded CAPTCHA providers as **primary** content (small interstitial-sized bodies only)
    if n < 25000:
        if "verify you are human" in head or "verify you're human" in head:
            return "human_verification_phrase"
        if "are you a robot" in head or "i'm not a robot" in head:
            return "robot_check_phrase"
        if "hcaptcha.com" in head and ("hcaptcha" in head or "verify" in head):
            return "hcaptcha_interstitial"
        if "arkoselabs" in head or "funcaptcha" in head:
            return "arkoselabs_funcaptcha"
        if "google.com/recaptcha" in head and ("sorry" in head or "unusual traffic" in head):
            return "recaptcha_google_wall"

    return None


def _meetings_contact_extract_enabled() -> bool:
    v = (os.getenv("SCRAPED_MEETINGS_CONTACT_EXTRACT") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


class ComprehensiveDiscoveryPipelineMeetings:
    """
    Scrape meeting-related pages and download PDFs under the resolved output root (default
    ``data/cache/scraped_meetings`` in the repo unless ``SCRAPED_MEETINGS_ROOT`` / ``--output-root``).

    ``max_pdfs`` caps **PDF GETs only**; the HTML crawl (navigation, ``other_video_streams``, …)
    continues until ``max_pages`` so vendor pages with MP4s are still reached after many agendas.
    """

    def __init__(
        self,
        *,
        output_root: Optional[Path] = None,
        max_pages: int = 40,
        max_pdfs: int = 80,
        max_video_downloads: int = 24,
        timeout_s: float = 120.0,
    ):
        self.output_root = Path(output_root) if output_root else default_scraped_meetings_root()
        self.max_pages = max_pages
        self.max_pdfs = max_pdfs
        self.max_video_downloads = max(0, int(max_video_downloads))
        self.timeout_s = timeout_s

    def _jurisdiction_base_dir(self, state: str, jurisdiction_id: str) -> Path:
        jt = _jurisdiction_type_from_id(jurisdiction_id)
        return (
            self.output_root
            / _fs_safe_segment(state.upper())
            / _fs_safe_segment(jt)
            / _fs_safe_segment(jurisdiction_id)
        )

    def _target_dir(self, state: str, jurisdiction_id: str, year: int) -> Path:
        return self._jurisdiction_base_dir(state, jurisdiction_id) / str(year)

    async def _fetch_page_once(self, client: httpx.AsyncClient, url: str) -> tuple[Optional[str], str, str]:
        """Single GET attempt (no retries). May fall back to headless Chromium (Playwright).

        On success returns ``(html, "", response_url)`` where ``response_url`` is the final URL
        after HTTP redirects (used to resolve relative links on cross-host redirects).
        """
        timeout_ms = int(max(15_000, min(180_000, float(self.timeout_s) * 1000)))
        try:
            r = await client.get(url, follow_redirects=True)
            if r.status_code != 200:
                reason = f"http_status_{r.status_code}"
                if httpx_status_should_try_playwright(r.status_code):
                    phtml, perr, pfinal = await fetch_html_via_playwright(
                        url, timeout_ms=timeout_ms, user_agent=_DEFAULT_UA
                    )
                    if phtml:
                        logger.info(
                            f"meetings_playwright_fallback_ok url={url!r} httpx_status={r.status_code} "
                            f"(plain HTTP failed; Playwright returned HTML)",
                        )
                        return phtml, "", pfinal
                    miss_msg = (
                        f"meetings_playwright_fallback_miss url={url!r} httpx_status={r.status_code} detail={perr!r}"
                    )
                    if r.status_code in (401, 403):
                        logger.warning(miss_msg)
                    else:
                        logger.debug(miss_msg)
                logfn = (
                    logger.debug
                    if _is_probable_site_search_probe(url) and 400 <= r.status_code < 500
                    else logger.warning
                )
                logfn(
                    "meetings_fetch_non_ok url={url!r} status={status} location={loc!r}",
                    url=url,
                    status=r.status_code,
                    loc=(r.headers.get("location") or ""),
                )
                return None, reason, url
            raw = r.content or b""
            nh = _non_html_body_reason(raw, r.headers.get("content-type") or "")
            if nh:
                logger.debug(
                    "meetings_fetch_non_html_body url={url!r} reason={reason}",
                    url=url,
                    reason=nh,
                )
                return None, f"non_html:{nh}", str(r.url)
            text = r.text
            captcha_hint = _captcha_or_bot_wall_reason(text, r.headers)
            if captcha_hint:
                phtml, perr, pfinal = await fetch_html_via_playwright(
                    url, timeout_ms=timeout_ms, user_agent=_DEFAULT_UA
                )
                if phtml:
                    logger.info(
                        f"meetings_playwright_fallback_ok_after_captcha_signal url={url!r} signal={captcha_hint}",
                    )
                    return phtml, "", pfinal
                logger.warning(
                    f"meetings_playwright_fallback_miss_after_captcha_signal url={url!r} signal={captcha_hint} detail={perr!r}",
                )
                logfn = logger.debug if _is_probable_site_search_probe(url) else logger.warning
                logfn(
                    "meetings_fetch_captcha_or_bot_wall url={url!r} signal={signal} html_chars={html_chars}",
                    url=url,
                    signal=captcha_hint,
                    html_chars=len(text),
                )
                return None, f"captcha:{captcha_hint}", str(r.url)
            return text, "", str(r.url)
        except httpx.TimeoutException as exc:
            reason = f"timeout:{type(exc).__name__}"
            logfn = logger.debug if _is_probable_site_search_probe(url) else logger.warning
            logfn(
                "meetings_fetch_failed url={url!r} {detail}",
                url=url,
                detail=f"{reason} ({exc!r})",
            )
            return None, reason, url
        except httpx.RequestError as exc:
            if playwright_fallback_enabled() and _httpx_error_suggests_tls_or_cert_failure(exc):
                phtml, perr, pfinal = await fetch_html_via_playwright(
                    url, timeout_ms=timeout_ms, user_agent=_DEFAULT_UA
                )
                if phtml:
                    logger.info(
                        f"meetings_playwright_fallback_ok_after_httpx_tls_error url={url!r} "
                        f"(httpx TLS/CA failed; Playwright returned HTML). httpx_exc={exc!r}",
                    )
                    return phtml, "", pfinal
                logger.debug(
                    f"meetings_playwright_fallback_miss_after_httpx_tls_error url={url!r} detail={perr!r}",
                )
            reason = f"request_error:{type(exc).__name__}"
            logfn = logger.debug if _is_probable_site_search_probe(url) else logger.warning
            logfn(
                "meetings_fetch_failed url={url!r} {detail}",
                url=url,
                detail=f"{reason} ({exc!r})",
            )
            return None, reason, url
        except Exception as exc:
            reason = f"unexpected:{type(exc).__name__}"
            et = type(exc).__name__
            er = repr(exc)
            logfn = logger.debug if _is_probable_site_search_probe(url) else logger.warning
            logfn(f"meetings_fetch_failed url={url!r} type={et} detail={er}")
            return None, reason, url

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> tuple[Optional[str], str, str]:
        """
        GET ``url``; on success return ``(html, "", response_url)``, else ``(None, reason, last_tried_url)``.

        Retries once (configurable) only when the failure reason starts with ``timeout:`` —
        helps flaky WSL / slow TLS handshakes (``ConnectTimeout`` vs ``ReadTimeout``).
        """
        extra = _fetch_retries()
        last_reason = "unknown"
        last_resp_url = url
        for attempt in range(extra + 1):
            html, last_reason, last_resp_url = await self._fetch_page_once(client, url)
            if html is not None:
                return html, "", last_resp_url
            if attempt < extra and (last_reason or "").startswith("timeout:"):
                delay = 0.75 * (attempt + 1)
                # Pre-format message: Loguru applies str.format() to the template; ``{url!r}`` + kwargs
                # raised KeyError: 'url' in some environments when mixed with positional-style logging.
                logger.info(
                    f"meetings_fetch_retry_after_timeout url={url!r} attempt={attempt + 2}/{extra + 1} sleep_s={delay}",
                )
                await asyncio.sleep(delay)
                continue
            break
        return None, last_reason, last_resp_url

    def _extract_nav_urls(self, html: str, page_url: str, homepage: str) -> List[str]:
        nav, _pdfs = extract_meeting_urls(html, page_url, homepage, generic_hint=MEETING_HINTS)
        return nav

    def _extract_pdf_pairs(self, html: str, page_url: str, homepage: str) -> List[Tuple[str, str]]:
        _nav, pairs = extract_meeting_urls(html, page_url, homepage, generic_hint=MEETING_HINTS)
        seen: Set[str] = set()
        out: List[Tuple[str, str]] = []
        for url, anchor in pairs:
            if url in seen:
                continue
            seen.add(url)
            out.append((url, anchor))
        return out

    async def _enrich_youtube_rows(
        self,
        client: httpx.AsyncClient,
        rows: List[Dict[str, Any]],
        *,
        homepage_url: str,
    ) -> None:
        """
        For each discovered YouTube **video**, call YouTube oEmbed and score title / author for
        meeting-like wording. Channels and playlists are skipped (no stable oEmbed video).
        """
        if not rows:
            return
        try:
            hp_host = urlparse(homepage_url).netloc.lower().split(":")[0]
        except Exception:
            hp_host = ""
        sem = asyncio.Semaphore(6)

        async def one(row: Dict[str, Any]) -> None:
            async with sem:
                raw_u = (row.get("url") or "").strip()
                sub = youtube_url_for_oembed(raw_u)
                if not sub:
                    row["meeting_relevance"] = "skipped_non_video_url"
                    row["youtube_metadata"] = {"note": "channel_playlist_or_unsupported_shape"}
                    return
                oe = f"https://www.youtube.com/oembed?url={quote(sub, safe='')}&format=json"
                try:
                    r = await client.get(
                        oe,
                        headers={"Accept": "application/json"},
                    )
                except Exception as exc:
                    row["meeting_relevance"] = "unknown_oembed_request_error"
                    row["youtube_metadata"] = {"error": repr(exc), "oembed_url": sub}
                    return
                if r.status_code != 200:
                    row["meeting_relevance"] = "unknown_oembed_http"
                    row["youtube_metadata"] = {
                        "http_status": r.status_code,
                        "oembed_url": sub,
                    }
                    return
                try:
                    data = r.json()
                except Exception as exc:
                    row["meeting_relevance"] = "unknown_oembed_json"
                    row["youtube_metadata"] = {"error": repr(exc), "oembed_url": sub}
                    return
                title = (data.get("title") or "").strip()
                author = (data.get("author_name") or "").strip()
                label, score, signals = score_youtube_meeting_relevance(
                    title,
                    author,
                    homepage_host=hp_host,
                )
                row["meeting_relevance"] = label
                row["meeting_relevance_score"] = round(score, 3)
                row["meeting_relevance_signals"] = signals
                row["youtube_metadata"] = {
                    "oembed_watch_url": sub,
                    "title": title,
                    "author_name": author,
                    "thumbnail_url": (data.get("thumbnail_url") or "").strip(),
                    "provider_name": (data.get("provider_name") or "").strip(),
                }

        await asyncio.gather(*(one(r) for r in rows))
        rank = {
            "likely_meeting": 0,
            "possible_meeting": 1,
            "weak_signal": 2,
            "unclear": 3,
            "unknown": 3,
            "skipped_non_video_url": 4,
            "unknown_oembed_request_error": 5,
            "unknown_oembed_http": 5,
            "unknown_oembed_json": 5,
            "unlikely_meeting": 6,
        }

        def _sort_key(row: Dict[str, Any]) -> Tuple[int, str]:
            rel = row.get("meeting_relevance") or "unknown"
            return (rank.get(rel, 7), row.get("url") or "")

        rows.sort(key=_sort_key)

    async def _select_working_homepage(
        self,
        client: httpx.AsyncClient,
        jurisdiction_id: str,
        passed_url: str,
    ) -> Tuple[str, List[str], List[str]]:
        """
        Pick a homepage to crawl: ordered DB candidates (when fallback is on), each probed until
        one returns enough HTML; otherwise first candidate or the passed URL only.
        """
        failures: List[str] = []
        passed_canon = _canonical_homepage_url(passed_url or "")

        if not _meetings_home_fallback_enabled():
            if _meetings_home_url_is_actionable(passed_canon):
                return passed_canon, [passed_canon], failures
            return "", [], (["no_actionable_homepage_url"] if not (passed_url or "").strip() else ["invalid_homepage_url"])

        rows: List[str] = []
        try:
            if psycopg2 is not None:
                rows = _load_homepage_candidates_from_db(jurisdiction_id)
        except Exception as exc:
            logger.warning(
                "meetings_homepage_candidates_db_failed jurisdiction_id={} detail={}",
                jurisdiction_id,
                repr(exc),
            )

        if not rows and (passed_url or "").strip():
            rows = [passed_url.strip()]

        uniq: List[str] = []
        seen: Set[str] = set()
        for raw in rows:
            cu = _canonical_homepage_url(raw)
            if not _meetings_home_url_is_actionable(cu):
                continue
            key = _strip_fragment(cu)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(cu)

        if not uniq and _meetings_home_url_is_actionable(passed_canon):
            uniq = [passed_canon]

        if not uniq:
            return "", [], ["no_homepage_candidates"]

        min_chars = _meetings_home_min_html_chars()
        for i, u in enumerate(uniq):
            fu = _strip_fragment(u)
            html, err, _resp_u = await self._fetch_page(client, fu)
            n = len(html or "")
            if html is not None and n >= min_chars:
                chosen = _canonical_homepage_url(u)
                logger.info(
                    "meetings_homepage_selected jurisdiction_id={} url={} idx={}/{} html_chars={}",
                    jurisdiction_id,
                    fu,
                    i + 1,
                    len(uniq),
                    n,
                )
                return chosen, uniq, failures
            failures.append(f"{fu}:{err or f'short_body_chars_{n}'}")

        chosen = uniq[0]
        logger.warning(
            "meetings_homepage_probe_all_below_threshold jurisdiction_id={} using_first={} n_candidates={}",
            jurisdiction_id,
            _strip_fragment(chosen),
            len(uniq),
        )
        failures.append("_using_first_candidate_after_failed_probes")
        return chosen, uniq, failures

    async def scrape(
        self,
        *,
        state: str,
        geoid: str,
        jtype: str,
        homepage_url: str,
        skip_output_root_mkdir: bool = False,
    ) -> MeetingsScrapeResult:
        st = (state or "").strip().upper()
        jid = jurisdiction_pk_from_geoid(geoid, jtype)
        if not jid:
            raise ValueError("Could not derive jurisdiction_id from geoid/type")

        initial_hp = _canonical_homepage_url(homepage_url or "")
        logger.info(
            "meetings_scrape_start jurisdiction={} geoid={} state={} homepage={}",
            jid,
            geoid,
            st,
            (initial_hp[:160] + "...") if len(initial_hp) > 160 else initial_hp,
        )

        year_now = datetime.now(timezone.utc).year
        stack_hints: List[str] = []
        result = MeetingsScrapeResult(
            jurisdiction_id=jid,
            state=st,
            homepage_url=initial_hp,
            root_dir=self.output_root,
        )

        if not skip_output_root_mkdir:
            _mkdir_from_existing_ancestor(self.output_root)

        visited: Set[str] = set()
        queued: Set[str] = set()
        to_visit: List[str] = []
        pdfs_seen: Set[str] = set()
        youtube_seen: Set[str] = set()
        other_stream_seen: Set[str] = set()
        pdf_count = 0
        search_seeded = False
        contact_page_rows: List[Dict[str, Any]] = []
        sitemap_summary: Optional[Dict[str, Any]] = None

        def _enqueue(u: str) -> None:
            nu = _strip_fragment(u)
            if nu in queued:
                return
            queued.add(nu)
            to_visit.append(u)

        headers = {
            "User-Agent": _DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        # One ``--timeout`` value for connect + read + write + pool (avoids ConnectTimeout while
        # read is still 120s — we previously capped connect at 25s).
        t = max(5.0, float(self.timeout_s))
        timeout = httpx.Timeout(t)

        base_dir = self._jurisdiction_base_dir(st, jid)
        snap_dir = base_dir / "_crawl_html"
        snap_dir.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
            verify=_http_verify(),
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        ) as client:

            hp, home_cands, home_probe_failures = await self._select_working_homepage(
                client, jid, homepage_url or ""
            )
            result.homepage_url = hp
            result.homepage_url_candidates = home_cands
            result.homepage_probe_failures = home_probe_failures

            # Homepage first; WordPress / OpenCivic search URLs are added only after HTML detection
            # (avoids ``/?s=webcast`` noise on Revize, Granicus, static sites, …).
            if _meetings_home_url_is_actionable(hp):
                _enqueue(hp)
                emb = suiteonemedia_embed_index_url(hp)
                if emb:
                    _enqueue(emb)
                try:
                    sitemap_dir = base_dir / "_sitemaps"
                    sm_res = await discover_meeting_candidate_urls_from_sitemaps(
                        client,
                        hp,
                        persist=SitemapPersistConfig(
                            output_dir=sitemap_dir,
                            jurisdiction_base_dir=base_dir,
                            jurisdiction_id=jid,
                            state=st,
                            geoid=(geoid or "").strip(),
                            jurisdiction_type=jtype,
                            homepage_url=hp,
                        ),
                        playwright_timeout_ms=int(
                            max(15_000, min(180_000, float(self.timeout_s) * 1000))
                        ),
                        playwright_user_agent=_DEFAULT_UA,
                    )
                    for su in sm_res.enqueue_urls:
                        _enqueue(su)
                    if sm_res.enqueue_urls:
                        logger.info(
                            "meetings_sitemap_enqueued jurisdiction={} n={}",
                            jid,
                            len(sm_res.enqueue_urls),
                        )
                    for pe in sm_res.persist_errors:
                        result.errors.append(f"sitemap_persist:{pe}")
                    if (
                        sm_res.inventory_rel_path
                        or sm_res.ndjson_rel_path
                        or sm_res.persist_errors
                    ):
                        sitemap_summary = {
                            "schema_version": 1,
                            "inventory_json": sm_res.inventory_rel_path,
                            "rows_ndjson": sm_res.ndjson_rel_path,
                            "documents_recorded": sm_res.documents_recorded,
                            "ndjson_row_count": sm_res.ndjson_row_count,
                            "meeting_candidate_enqueue_count": len(sm_res.enqueue_urls),
                            "persist_errors": sm_res.persist_errors,
                        }
                except Exception as exc:
                    logger.warning(
                        "meetings_sitemap_seed_failed jurisdiction={} err={!r}",
                        jid,
                        exc,
                    )
                    result.errors.append(f"sitemap_seed:{exc!r}")
            else:
                result.errors.append("no_usable_homepage_url")

            while to_visit and len(visited) < self.max_pages:
                url = to_visit.pop(0)
                fetch_url = _strip_fragment(url)
                if fetch_url in visited:
                    continue
                visited.add(fetch_url)
                logger.info(
                    "meetings_crawl_fetch_start jurisdiction={} visited={}/{} queue_remaining={} "
                    "pdfs_saved={}/{} url={}",
                    jid,
                    len(visited),
                    self.max_pages,
                    len(to_visit),
                    pdf_count,
                    self.max_pdfs,
                    _meetings_log_url(fetch_url),
                )
                html, fetch_err, response_url = await self._fetch_page(client, fetch_url)
                page_ctx = (response_url or "").strip() or fetch_url
                if not html:
                    if _is_probable_site_search_probe(fetch_url):
                        logger.debug(
                            "meetings_search_probe_skip url={url!r} reason={reason!r}",
                            url=fetch_url,
                            reason=fetch_err,
                        )
                    else:
                        result.errors.append(f"no_html:{fetch_url}:{fetch_err or 'unknown'}")
                    continue
                logger.info(
                    "meetings_crawl_fetch_ok jurisdiction={} url={} html_chars={}",
                    jid,
                    _meetings_log_url(page_ctx),
                    len(html or ""),
                )
                result.pages_fetched.append(fetch_url)
                emb_idx = suiteonemedia_embed_index_url(page_ctx)
                if emb_idx:
                    _enqueue(emb_idx)

                if _meetings_contact_extract_enabled():
                    chunk = extract_contacts_from_page(html, page_ctx)
                    if chunk.get("emails") or chunk.get("phones"):
                        contact_page_rows.append(chunk)

                if not search_seeded and _is_homepage_document_url(fetch_url, hp):
                    search_seeded = True
                    for su in _discover_site_search_seed_urls(html, hp):
                        _enqueue(su)
                stack_hints = merge_stack_hints(stack_hints, detect_meeting_stacks(html, page_ctx))
                result.detected_stacks = list(stack_hints)

                # Revize / ASP “Site Search” portals (not WordPress ``/?s=``); try a few GET query variants.
                for portal in extract_site_search_portal_urls(html, page_ctx, hp):
                    for variant in site_search_portal_variants(portal):
                        _enqueue(variant)

                for yt in extract_youtube_refs(html, page_ctx):
                    yu = yt.get("url") or ""
                    if not yu or yu in youtube_seen:
                        continue
                    youtube_seen.add(yu)
                    row = {
                        "url": yu,
                        "link_type": yt.get("link_type", "other"),
                        "found_via": yt.get("found_via", ""),
                        "discovered_on": page_ctx,
                    }
                    result.youtube.append(row)

                for vs in extract_other_video_stream_refs(html, page_ctx):
                    vu = vs.get("url") or ""
                    if not vu or vu in other_stream_seen:
                        continue
                    other_stream_seen.add(vu)
                    result.other_video_streams.append(
                        {
                            "url": vu,
                            "platform": vs.get("platform", "unknown"),
                            "found_via": vs.get("found_via", ""),
                            "discovered_on": page_ctx,
                        }
                    )

                # HTML snapshots for audit (outside ``{year}/`` so PDF folders stay clean)
                safe_name = re.sub(r"[^\w.-]+", "_", urlparse(fetch_url).path)[:120] or "index"
                snap_path = snap_dir / f"page_{safe_name}.html"
                try:
                    snap_path.write_text(html[:2_000_000], encoding="utf-8", errors="replace")
                except OSError as exc:
                    result.errors.append(f"snapshot_write:{snap_path}:{exc}")
                if _meetings_readable_snapshot_txt_enabled():
                    txt_path = snap_path.with_name(f"{snap_path.stem}.readable.txt")
                    try:
                        txt_path.write_text(
                            _html_to_readable_plaintext(html, page_ctx),
                            encoding="utf-8",
                            errors="replace",
                        )
                    except OSError as exc:
                        result.errors.append(f"snapshot_readable_write:{txt_path}:{exc}")
                    except Exception as exc:
                        result.errors.append(f"snapshot_readable_build:{txt_path}:{exc!r}")

                if pdf_count < self.max_pdfs:
                    for pdf_raw, anchor_text in self._extract_pdf_pairs(html, page_ctx, hp):
                        pdf = _normalize_http_url_path_encoding(pdf_raw)
                        if pdf in pdfs_seen:
                            continue
                        pdfs_seen.add(pdf)
                        y = _infer_year(pdf, year_now)
                        dest_dir = self._target_dir(st, jid, y)
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        fname = _meeting_pdf_disk_filename(pdf)
                        dest = dest_dir / fname
                        try:
                            pr, why = await _fetch_pdf_with_referers(
                                client, pdf, referers=[page_ctx, fetch_url, hp]
                            )
                            if pr is not None:
                                dest.write_bytes(pr.content)
                                result.pdfs_downloaded.append(
                                    {
                                        "url": pdf,
                                        "path": str(dest),
                                        # Calendar year as string in JSON (avoids int in manifests / TS strict JSON).
                                        "year": str(y),
                                        "bytes": len(pr.content),
                                        "doc_type": classify_document(pdf, anchor_text),
                                        "anchor_text": (anchor_text or "")[:500],
                                    }
                                )
                                pdf_count += 1
                            else:
                                result.errors.append(f"pdf_rejected_not_pdf:{pdf}:{why}")
                                try:
                                    if dest.is_file():
                                        peek = dest.read_bytes()[:5]
                                        if not peek.startswith(b"%PDF"):
                                            dest.unlink(missing_ok=True)
                                except OSError:
                                    pass
                        except OSError as exc:
                            result.errors.append(f"pdf_write:{pdf}:{exc}")
                        except Exception as exc:
                            result.errors.append(f"pdf_dl:{pdf}:{exc}")

                        if pdf_count >= self.max_pdfs:
                            break

                # Enqueue linked meeting pages (not yet visited)
                for link in self._extract_nav_urls(html, page_ctx, hp):
                    if PDF_EXT.search(link):
                        continue
                    nu = _strip_fragment(link)
                    if nu not in visited:
                        _enqueue(link)

            await self._enrich_youtube_rows(client, result.youtube, homepage_url=hp)

            if _meetings_download_suiteone_video_assets() and self.max_video_downloads > 0:
                n_elig = sum(
                    1
                    for row in result.other_video_streams
                    if _is_suiteone_style_mp4_asset(
                        (row.get("url") or "").strip(),
                        platform=(row.get("platform") or "").strip(),
                        found_via=(row.get("found_via") or "").strip(),
                    )
                )
                logger.info(
                    "meetings_video_phase_start jurisdiction={} other_streams_total={} "
                    "suiteone_mp4_candidates={} max_downloads={}",
                    jid,
                    len(result.other_video_streams),
                    n_elig,
                    self.max_video_downloads,
                )
                video_dir = base_dir / "_video_assets"
                delete_mp4 = _meetings_delete_mp4_after_opus()
                logger.info(
                    "meetings_video_phase_config delete_mp4_after_opus={} ffmpeg={}",
                    delete_mp4,
                    bool(shutil.which("ffmpeg")),
                )
                n_pruned = _prune_suiteone_mp4s_with_opus(video_dir)
                if n_pruned:
                    logger.info(
                        "meetings_video_phase_pruned_stale_mp4 jurisdiction={} removed={}",
                        jid,
                        n_pruned,
                    )
                seen_mp4: Set[str] = set()
                max_b = _meetings_max_video_mp4_bytes()
                for row in result.other_video_streams:
                    if len(result.video_assets) >= self.max_video_downloads:
                        break
                    u = (row.get("url") or "").strip()
                    if not u or u in seen_mp4:
                        continue
                    seen_mp4.add(u)
                    plat = (row.get("platform") or "").strip()
                    fv = (row.get("found_via") or "").strip()
                    if not _is_suiteone_style_mp4_asset(u, platform=plat, found_via=fv):
                        continue
                    discovered_on = (row.get("discovered_on") or hp or "").strip()
                    rec = await _download_suiteone_mp4_transcode_opus(
                        client,
                        mp4_url=u,
                        referer=discovered_on,
                        discovered_on=discovered_on,
                        found_via=fv,
                        platform=plat,
                        video_dir=video_dir,
                        max_bytes=max_b,
                    )
                    result.video_assets.append(rec)
                    if rec.get("error"):
                        result.errors.append(f"video_asset:{u[:120]}:{rec['error']}")
                    else:
                        logger.info(
                            "meetings_video_asset_saved jurisdiction={} mp4_rel={} opus={}",
                            jid,
                            rec.get("mp4_relative_path") or "",
                            bool(rec.get("opus_relative_path")),
                        )
                n_pruned_after = _prune_suiteone_mp4s_with_opus(video_dir)
                logger.info(
                    "meetings_video_phase_done jurisdiction={} video_assets_rows={} mp4_pruned_after={}",
                    jid,
                    len(result.video_assets),
                    n_pruned_after,
                )

            result.extracted_contacts = (
                merge_contact_manifest_rows(contact_page_rows)
                if _meetings_contact_extract_enabled()
                else {}
            )

        manifest_path = base_dir / "_manifest.json"
        try:
            manifest_path.write_text(
                json.dumps(
                    {
                        "jurisdiction_id": jid,
                        "state": st,
                        "homepage_url": hp,
                        "homepage_url_candidates": result.homepage_url_candidates,
                        "homepage_probe_failures": result.homepage_probe_failures,
                        "output_root": str(self.output_root.resolve()),
                        "output_resolution": scraped_meetings_root_resolution_note(),
                        "detected_stacks": result.detected_stacks,
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "pages_fetched": result.pages_fetched,
                        "pdfs": result.pdfs_downloaded,
                        "youtube": result.youtube,
                        "other_video_streams": result.other_video_streams,
                        "video_assets": result.video_assets,
                        "errors": result.errors,
                        "extracted_contacts": result.extracted_contacts,
                        "sitemaps": sitemap_summary,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            result.errors.append(f"manifest:{exc}")

        return result


async def run_meetings_batch(
    pipe: ComprehensiveDiscoveryPipelineMeetings,
    jobs: List[Dict[str, str]],
    *,
    concurrency: int,
) -> List[MeetingsScrapeResult]:
    """
    Run many ``scrape`` calls concurrently with a semaphore (bounded parallelism).

    Each job dict: ``state``, ``geoid``, ``jtype``, ``url``, ``jurisdiction_id``.
    """
    if not jobs:
        return []
    _mkdir_from_existing_ancestor(pipe.output_root)
    sem = asyncio.Semaphore(max(1, concurrency))
    logger.info(
        "meetings_batch_start jobs={} concurrency={} "
        "(quiet until each jurisdiction finishes; first log may take several minutes)",
        len(jobs),
        concurrency,
    )

    async def one(job: Dict[str, str]) -> MeetingsScrapeResult:
        jid = job["jurisdiction_id"]
        async with sem:
            try:
                r = await pipe.scrape(
                    state=job["state"],
                    geoid=job["geoid"],
                    jtype=job["jtype"],
                    homepage_url=job["url"],
                    skip_output_root_mkdir=True,
                )
                logger.info(
                    "meetings_done jurisdiction={} pages={} pdfs={} youtube={} other_streams={} video_assets={} err_lines={}",
                    jid,
                    len(r.pages_fetched),
                    len(r.pdfs_downloaded),
                    len(r.youtube),
                    len(r.other_video_streams),
                    len(r.video_assets),
                    len(r.errors),
                )
                return r
            except Exception as exc:
                logger.exception("meetings_scrape_crash jurisdiction={}", jid)
                return MeetingsScrapeResult(
                    jurisdiction_id=jid,
                    state=job["state"],
                    homepage_url=job.get("url", ""),
                    root_dir=pipe.output_root,
                    youtube=[],
                    other_video_streams=[],
                    video_assets=[],
                    errors=[f"exception:{exc!r}"],
                    extracted_contacts={},
                )

    return list(await asyncio.gather(*(one(j) for j in jobs)))


def main() -> None:
    _load_repo_dotenv()
    parser = argparse.ArgumentParser(
        description="Scrape meeting minutes; default output <repo>/data/cache/scraped_meetings (env SCRAPED_MEETINGS_ROOT overrides).",
    )
    parser.add_argument("--state", required=True, help="USPS, e.g. CO")
    parser.add_argument(
        "--geoid",
        default="",
        help="Single Census GEOID (omit when using --geoids or --batch-from-db)",
    )
    parser.add_argument(
        "--geoids",
        default="",
        help="Comma-separated GEOIDs (requires --from-db); multiple jobs run in parallel (see --concurrency)",
    )
    parser.add_argument(
        "--batch-from-db",
        action="store_true",
        help=f"Scrape every row in {INT_JURISDICTION_WEBSITES_TABLE} for --state (optional --type filter)",
    )
    parser.add_argument(
        "--retry-failed-shallow",
        action="store_true",
        help=(
            "Rescrape jurisdictions whose cached _manifest.json is failed (0 pages) or shallow "
            "(1..N-1 pages; N from --shallow-max-pages). Scans --output-root or default "
            "SCRAPED_MEETINGS_ROOT. Requires --from-db. Not compatible with --geoid, --geoids, or "
            "--batch-from-db."
        ),
    )
    parser.add_argument(
        "--retry-mode",
        default="failed,shallow",
        help="With --retry-failed-shallow: comma list: failed, shallow (default: both)",
    )
    parser.add_argument(
        "--shallow-max-pages",
        type=int,
        default=6,
        help=(
            "With --retry-failed-shallow: treat as shallow when 1 <= len(pages_fetched) < this "
            "(default 6 → shallow is 1–5 pages)"
        ),
    )
    parser.add_argument(
        "--type",
        default="county",
        help="jurisdiction type, or 'all' with --batch-from-db to include every id prefix in that state",
    )
    parser.add_argument("--url", help="Homepage URL (single --geoid only; if omitted, use --from-db)")
    parser.add_argument(
        "--from-db",
        action="store_true",
        help=f"Load website_url from {INT_JURISDICTION_WEBSITES_TABLE} using derived jurisdiction_id",
    )
    parser.add_argument("--output-root", type=str, default="", help="Override SCRAPED_MEETINGS_ROOT")
    parser.add_argument("--max-pages", type=int, default=40)
    parser.add_argument("--max-pdfs", type=int, default=80, help="Max PDF downloads per jurisdiction")
    parser.add_argument(
        "--max-video-downloads",
        type=int,
        default=None,
        help=(
            "Max SuiteOne-style MP4 downloads (and Opus transcodes) per jurisdiction "
            "(default 24, or SCRAPED_MEETINGS_MAX_VIDEO_DOWNLOADS from env)."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="HTTP timeout per request for connect, read, write, and pool (seconds; same value for all)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="Max concurrent jurisdictions for multi-job runs (--geoids, --batch-from-db, --retry-failed-shallow)",
    )
    args = parser.parse_args()

    state = (args.state or "").strip().upper()
    jobs: List[Dict[str, str]] = []

    if args.batch_from_db and args.retry_failed_shallow:
        raise SystemExit("Choose only one of --batch-from-db or --retry-failed-shallow")

    if args.batch_from_db:
        jf: Optional[str] = None if (args.type or "").strip().lower() == "all" else args.type
        jobs = load_meeting_scrape_jobs_for_state(state, jf)
    elif args.retry_failed_shallow:
        if not args.from_db:
            raise SystemExit("--retry-failed-shallow requires --from-db")
        if (args.geoids or "").strip() or (args.geoid or "").strip():
            raise SystemExit("--retry-failed-shallow cannot be combined with --geoid or --geoids")
        if (args.type or "").strip().lower() in ("all", ""):
            raise SystemExit("--retry-failed-shallow requires a concrete --type (e.g. county), not 'all'")
        scraped_root = Path(args.output_root).expanduser() if args.output_root else default_scraped_meetings_root()
        retry_modes = {m.strip().lower() for m in (args.retry_mode or "").split(",") if m.strip()}
        geoids = collect_retry_geoids_from_scraped_manifests(
            state=state,
            jtype=args.type,
            scraped_root=scraped_root,
            shallow_max_pages=args.shallow_max_pages,
            retry_modes=retry_modes,
        )
        logger.info(
            "meetings_retry_manifest_targets state={} type={} n_geoids={} retry_modes={} shallow_max_pages={} root={}",
            state,
            args.type,
            len(geoids),
            ",".join(sorted(retry_modes)) or "(none)",
            args.shallow_max_pages,
            scraped_root,
        )
        if not geoids:
            rel = scraped_root / _fs_safe_segment(state) / _fs_safe_segment(args.type)
            raise SystemExit(
                f"No failed/shallow manifests found under {rel} for --retry-mode={args.retry_mode!r}. "
                "Run a normal scrape first, or adjust --shallow-max-pages / paths."
            )
        jobs = load_meeting_scrape_jobs_for_geoids(state, args.type, ",".join(geoids))
    elif (args.geoids or "").strip():
        if not args.from_db:
            raise SystemExit("--geoids requires --from-db to resolve website_url from the warehouse")
        jobs = load_meeting_scrape_jobs_for_geoids(state, args.type, args.geoids)
    elif (args.geoid or "").strip():
        jid = jurisdiction_pk_from_geoid(args.geoid, args.type)
        if not jid:
            raise SystemExit("Invalid geoid/type for jurisdiction_id")
        if args.from_db:
            url = _load_homepage_from_db(jid) or ""
        else:
            url = (args.url or "").strip()
        if not url:
            raise SystemExit("Provide --url or --from-db with a matching int_jurisdiction_websites row")
        jobs = [
            {
                "state": state,
                "geoid": (args.geoid or "").strip(),
                "jtype": args.type,
                "url": url,
                "jurisdiction_id": jid,
            }
        ]
    else:
        raise SystemExit("Provide --geoid, --geoids, --batch-from-db, or --retry-failed-shallow")

    if not jobs:
        if (args.geoids or "").strip() and args.from_db:
            raise SystemExit(
                "No scrape jobs to run: every --geoids entry was skipped (invalid GEOID) or had no "
                "website_url in int_jurisdiction_websites. Check DATABASE_URL, dbt seed, and GEOIDs "
                "(5-digit county FIPS, e.g. 01001)."
            )
        raise SystemExit("No scrape jobs to run (empty list).")

    logger.info(
        "meetings_cli_ready jobs={} state={} mode={}",
        len(jobs),
        state,
        "batch-from-db"
        if args.batch_from_db
        else (
            "retry-failed-shallow"
            if args.retry_failed_shallow
            else ("geoids" if (args.geoids or "").strip() else "single-geoid")
        ),
    )

    root = Path(args.output_root).expanduser() if args.output_root else None
    if args.max_video_downloads is not None:
        max_video_downloads = max(0, int(args.max_video_downloads))
    else:
        try:
            max_video_downloads = max(
                0, int(os.getenv("SCRAPED_MEETINGS_MAX_VIDEO_DOWNLOADS") or "24")
            )
        except (TypeError, ValueError):
            max_video_downloads = 24
    pipe = ComprehensiveDiscoveryPipelineMeetings(
        output_root=root,
        max_pages=args.max_pages,
        max_pdfs=args.max_pdfs,
        max_video_downloads=max_video_downloads,
        timeout_s=args.timeout,
    )
    logger.info(
        "meetings_limits max_pages={} max_pdfs={} max_video_downloads={}",
        pipe.max_pages,
        pipe.max_pdfs,
        pipe.max_video_downloads,
    )

    if len(jobs) == 1:
        j0 = jobs[0]
        out = asyncio.run(
            pipe.scrape(
                state=j0["state"],
                geoid=j0["geoid"],
                jtype=j0["jtype"],
                homepage_url=j0["url"],
            )
        )
        try:
            root_disp = str(pipe.output_root.resolve())
        except OSError:
            root_disp = str(pipe.output_root.expanduser())
        sample_pdf = out.pdfs_downloaded[0]["path"] if out.pdfs_downloaded else "(no pdfs)"
        logger.success(
            "Done {} — pages={}, pdfs={}, youtube={}, other_streams={}, video_assets={}, errors={} | root={} | sample_pdf={}",
            out.jurisdiction_id,
            len(out.pages_fetched),
            len(out.pdfs_downloaded),
            len(out.youtube),
            len(out.other_video_streams),
            len(out.video_assets),
            len(out.errors),
            root_disp,
            sample_pdf,
        )
    else:
        results = asyncio.run(run_meetings_batch(pipe, jobs, concurrency=args.concurrency))
        n_crash = sum(
            1 for r in results if any(str(e).startswith("exception:") for e in r.errors)
        )
        pages = sum(len(r.pages_fetched) for r in results)
        pdfs = sum(len(r.pdfs_downloaded) for r in results)
        try:
            batch_root = str(pipe.output_root.resolve())
        except OSError:
            batch_root = str(pipe.output_root.expanduser())
        logger.success(
            "Batch done jobs={} scrape_crashes={} total_pages={} total_pdfs={} | root={}",
            len(results),
            n_crash,
            pages,
            pdfs,
            batch_root,
        )


if __name__ == "__main__":
    main()
