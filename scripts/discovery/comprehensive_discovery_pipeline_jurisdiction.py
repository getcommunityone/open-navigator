"""
Jurisdiction crawl: meetings/minutes plus optional board/council/contact-directory extraction (separate from ``ComprehensiveDiscoveryPipeline``).

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
  Teams, Google Meet, Wistia, Brightcove, ``.m3u8`` HLS, **GoMeet** (``gomeet.com`` recording links), …)
  into ``other_video_streams`` in the
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
  ``/event/GetAgendaFile/…`` and   ``/event/GetMinutesFile/…`` links (no ``.pdf`` suffix) are downloaded
  as PDFs like other meeting documents.
- **Simbli / eBoard Solutions** (``*.eboardsolutions.com``): agendas and minutes often ship as **HTML**
  ASP.NET pages. Matching ``<a href>`` targets are opened in Chromium and saved with **Playwright**
  ``page.pdf()`` (Letter, print backgrounds). Toggle with ``SCRAPED_MEETINGS_SIMBLI_HTML_TO_PDF``
  (default on). Caps output size with ``SCRAPED_MEETINGS_HTML_PRINT_MAX_BYTES`` (default 35MB).
  ``SB_MeetingListing.aspx`` shells over plain HTTP trigger an automatic Playwright refetch once HTML is
  shorter than ``SCRAPED_MEETINGS_SIMBLI_LISTING_MIN_HTML_CHARS`` (default ``8000``); row actions that
  use ``ViewMeeting`` / ``ViewMinutes`` onclick handlers are turned into ``ViewMeeting.aspx?S=&MID=``
  crawl seeds, queued **ahead of** generic site navigation in **listing order** (top rows first).
  **Pagination:** grids often expose only **50 meetings** in the initial HTML — use
  larger ``--max-pages`` / resume, and ensure the listing is scrolled or paged in-browser if you need
  the full archive in one pass (future enhancement).
- **PDF URLs** written to ``_manifest.json`` ``pdfs[].url`` are **path-normalized** (e.g. spaces
  percent-encoded as ``%20``) so manifests and downstream loaders match RFC-safe URLs used for GET.
- **AWS S3** (``*.amazonaws.com``, e.g. ``s3.us-west-2.amazonaws.com/...``): meeting ``.pdf`` / ``.docx``
  / ``.mp3`` / ``.m4a`` / other extensions matched by ``meetings_platform_heuristics.MEETING_DOWNLOAD_EXT`` on the
  listing page are downloaded (not whole-bucket HTML crawls). **Audio:** ``.mp3`` / ``.m4a`` / ``.wav`` are
  transcoded to **Opus** (``.opus``) with ``ffmpeg`` when ``SCRAPED_MEETINGS_MP3_TO_OPUS`` is true (default);
  the original file is removed when ``SCRAPED_MEETINGS_DELETE_MP3_AFTER_OPUS`` is true (default). Minimum
  output size uses ``SCRAPED_MEETINGS_MIN_OPUS_BYTES_FOR_MP4_DELETE`` (same threshold as SuiteOne MP4→Opus).

- **Office → PDF:** When ``libreoffice`` or ``soffice`` is on ``PATH`` and ``SCRAPED_MEETINGS_OFFICE_TO_PDF`` is
  true (default; alias ``SCRAPED_MEETINGS_DOCX_TO_PDF``), downloaded ``.docx`` / ``.doc`` files are converted to
  ``.pdf`` next to the same basename, the Office file is deleted, and ``_manifest.json`` rows reference the PDF
  (with ``converted_from_suffix``). Disable with ``SCRAPED_MEETINGS_OFFICE_TO_PDF=false`` to keep Word on disk.

- **PDF → PNG (vision / Gemma):** After each meeting ``.pdf`` is finalized on disk (direct download, Office
  conversion, or Simbli HTML print), optional **page PNGs** are written next to the PDF as
  ``<stem>.page_001.png``, … (via ``pdf2image``; install **poppler-utils** so ``pdftoppm`` is on ``PATH``).
  Scope is controlled by ``SCRAPED_MEETINGS_PDF_TO_PNG``: default ``inventory`` (Tuscaloosa + Big Timber county
  and city cache folders only), ``all`` for every PDF under the meetings root, or ``false`` to disable.
  DPI defaults to ``150``; override with ``SCRAPED_MEETINGS_PDF_TO_PNG_DPI``.

- Download PDFs (and optional HTML snapshots of key pages) under:

    ``{root}/{state}/{jurisdiction_type}/{jurisdiction_id}/{year}/``

  where ``{year}`` is the **meeting calendar year** when :func:`~scripts.discovery.meeting_document_naming.pick_meeting_date`
  can infer a date from anchor text / ``FileName=`` / URL (aligned with readable filenames); otherwise the same URL-only
  ``20xx`` heuristics as before, falling back to the scrape-time calendar year.

  PDF files use readable names when metadata allows: ``YYYY-MM-DD_doc_type_title_snake.pdf``
  (or ``YYYY_…`` when only a calendar year is known). Collisions append a short URL hash.

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

**Built-in directory seeds:** a small map in ``jurisdiction_contact_seed_urls`` prepends known pilot
URLs (e.g. Sweet Grass commissioner bios on ``sgcountymt.gov``, Big Timber mayor/council, Tuscaloosa
County ``county-officials`` and ``commission-agenda-minutes`` on ``tuscco.com``) before ``--contact-seed-urls``. Disable with ``SCRAPED_CONTACT_BUILTIN_SEEDS=false``.

**Structured contacts:** when ``SCRAPED_CONTACT_STRUCTURED_EXTRACT`` is true (default), pages flagged
as directory-like (URL/title/body heuristics) or listed in ``--contact-seed-urls`` are parsed for
schema.org ``Person`` JSON-LD, ``mailto:`` anchors, Bootstrap-style ``div.card`` grids, and
**heading-block** sections (WordPress ``h2``–``h6`` bios with plain-text ``Email:`` / phones). Rows are written to ``_manifest.json`` under
``structured_contacts`` and ``contact_directory_pages``. With ``--persist-contacts-db`` and a
database URL, rows are inserted into ``bronze.bronze_contacts_scraped`` (migration ``035``).

**Profile images:** when ``SCRAPED_CONTACT_PROFILE_IMAGES`` is true (default), directory-flagged pages
also download person photos into ``_contact_images/`` as **PNG** (WebP/JPEG/GIF sources are
converted after download; disable with ``SCRAPED_CONTACT_PROFILE_IMAGES_PNG=false``). Each file is
named from the contact’s **name** in snake_case (see ``contact_profile_images.contact_profile_image_stem_from_name`` and
``download_profile_images``). Rows with no usable name get ``unknown``, then ``unknown_2``, ``unknown_3``, …
Jobs come from JSON-LD ``Person`` ``image``,
portrait-ish ``<img>`` tags (including ``data-src`` / ``srcset``), and WordPress ``figure`` blocks
placed above an official ``h2``–``h6`` title. Nav links from high ``person_adjacent_image_score``
pages are boosted when paths look board/council/officials-like (``SCRAPED_CONTACT_PHOTO_NAV_BOOST_MIN``).

Resume / deeper archives: each run writes ``_crawl_state.json`` (visited URLs, frontier queue,
dedupe sets). Use ``--resume`` with a **larger** ``--max-pages`` — ``max_pages`` is a **total** cap on
distinct HTML fetches across runs (already-visited URLs still count toward the cap). Without a saved
state file, ``--resume`` can bootstrap the frontier from ``_manifest.json`` plus SuiteOne
``/event/?id=…`` links mined from existing ``_crawl_html/page_*.html`` snapshots.
Set ``SCRAPED_MEETINGS_PERSIST_CRAWL_STATE_EACH_PAGE=true`` to rewrite ``_crawl_state.json`` after
every fetched page (slower; helps if the process dies mid-crawl).

Accessibility tooling (**axe**, **Lighthouse**): useful on a **fixed URL list** for audits; they do
not replace HTML/sitemap discovery for meeting archives or SuiteOne embed indexes here.

Examples (Yuma County CO):
- Search: https://yumacounty.net/?s=meetings
- Page: https://yumacounty.net/monthly-meetings/
- Fragment: https://yumacounty.net/monthly-meetings/#toggle-id-2

Run::

    .venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_jurisdiction \\
        --state CO --geoid 08125 --type county --url https://yumacounty.net/

    .venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_jurisdiction \\
        --state CO --geoid 08125 --type county --from-db

    # Tuscaloosa County, AL — meetings + county officials directory; load homepage from warehouse
    .venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_jurisdiction \\
        --state AL --geoid 01125 --type county --from-db \\
        --contact-seed-urls "https://www.tuscco.com/county-officials/" \\
        --max-pages 120 --max-pdfs 60 \\
        --persist-contacts-db

    # Parallel batch (many sites, long timeouts)
    .venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_jurisdiction \\
        --batch-from-db --state AL --type county --concurrency 8 --timeout 120

    .venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_jurisdiction \\
        --state AL --type county --geoids 01001,01003,01009 --from-db --concurrency 6 --timeout 120

    # Rerun counties whose cached manifest is failed (0 pages) or shallow (few pages; see --shallow-max-pages)
    .venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_jurisdiction \\
        --state AL --type county --from-db --retry-failed-shallow --concurrency 6 --timeout 120

    # Continue a prior crawl (raise total page budget; merges with cached manifest)
    .venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_jurisdiction \\
        --state AL --geoid 0177256 --type municipality --from-db --resume \\
        --max-pages 500 --max-pdfs 800 --max-video-downloads 200
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
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote, parse_qs, unquote, urljoin, urlparse, urlunparse

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
    extract_structured_contacts_from_html,
    merge_contact_manifest_rows,
)
from scripts.discovery.contact_directory_heuristics import classify_contact_directory_page
from scripts.discovery.bronze_contacts_scraped_persist import insert_bronze_contacts_scraped
from scripts.discovery.contact_profile_images import (
    download_profile_images,
    extract_profile_image_jobs,
    partition_nav_for_photo_priority,
)
from scripts.discovery.jurisdiction_contact_seed_urls import merged_contact_seed_urls
from scripts.discovery.meeting_document_naming import (
    allocate_unique_pdf_path,
    infer_calendar_folder_year,
    meeting_document_storage_suffix,
)
from scripts.discovery.meetings_platform_heuristics import (
    MEETING_DOWNLOAD_EXT,
    classify_document,
    detect_meeting_stacks,
    extract_meeting_urls,
    extract_opencivic_content_search_portals,
    extract_other_video_stream_refs,
    extract_site_search_portal_urls,
    extract_simbli_agenda_minutes_html_pairs,
    extract_youtube_refs,
    html_suggests_wordpress_site,
    is_simbli_eboard_host,
    is_simbli_meeting_listing_page_url,
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
    print_agenda_html_page_to_pdf_via_playwright,
)

try:
    import psycopg2
except ModuleNotFoundError:  # pragma: no cover
    psycopg2 = None  # type: ignore[misc,assignment]

MEETING_HINTS = re.compile(
    r"(meetings?|minutes?|proceedings|action\s*minutes|agenda|agendas|calendar|board|commission|council|"
    r"hearing|session|video|zoom|/event/|\bmedia\b|prior\s*year|archive|powerdms)",
    re.I,
)


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


MEETINGS_CRAWL_STATE_FILENAME = "_crawl_state.json"
MEETINGS_CRAWL_STATE_SCHEMA_VERSION = 1


def _safe_load_json_dict(path: Path) -> Dict[str, Any]:
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("meetings_json_load_failed path={} err={!r}", path, exc)
    return {}


def _merge_prior_extracted_contacts(prior: Dict[str, Any], fresh: Dict[str, Any]) -> Dict[str, Any]:
    """Merge manifest ``extracted_contacts`` with a new crawl pass (same shape as merge_contact_manifest_rows)."""
    if not prior:
        return fresh
    if not fresh:
        return prior
    pe = set(prior.get("emails") or [])
    pp = set(prior.get("phones") or [])
    fe = set(fresh.get("emails") or [])
    fp = set(fresh.get("phones") or [])
    by_prior = list(prior.get("by_page") or [])
    by_fresh = list(fresh.get("by_page") or [])
    seen_urls: Set[str] = set()
    merged_by: List[Dict[str, Any]] = []
    for row in by_prior + by_fresh:
        if not row:
            continue
        u = _strip_fragment(str(row.get("page_url") or ""))
        if not u or u in seen_urls:
            continue
        seen_urls.add(u)
        merged_by.append(row)
    return {
        "emails": sorted(pe | fe)[:80],
        "phones": sorted(pp | fp)[:50],
        "by_page": merged_by[:56],
    }


def _merge_structured_contact_rows(prior: List[Dict[str, Any]], fresh: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Dedupe structured contact rows across resume passes."""
    seen: Set[Tuple[str, str, str]] = set()
    out: List[Dict[str, Any]] = []
    for row in (prior or []) + (fresh or []):
        if not row:
            continue
        pu = _strip_fragment(str(row.get("source_page_url") or ""))
        em = str(row.get("email") or "").strip().lower()
        nm = str(row.get("person_name") or "").strip().lower()
        key = (pu, em, nm)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out[:800]


def _merge_contact_directory_pages(prior: List[Dict[str, Any]], fresh: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_url: Dict[str, Dict[str, Any]] = {}
    for row in (prior or []) + (fresh or []):
        if not row:
            continue
        u = _strip_fragment(str(row.get("page_url") or ""))
        if u:
            by_url[u] = row
    return list(by_url.values())[:200]


def _merge_contact_profile_images(prior: List[Dict[str, Any]], fresh: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for row in (prior or []) + (fresh or []):
        if not row:
            continue
        key = str(row.get("saved_relative_path") or "") or (
            str(row.get("image_url") or "")
            + "#"
            + str(row.get("saved_filename") or row.get("person_stem") or "")
        )
        if not key.strip("#"):
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out[:1200]


def _expand_contact_seed_url(homepage: str, seed: str) -> str:
    """Resolve a CLI seed (absolute or site-relative) against the working homepage."""
    s = (seed or "").strip()
    if not s:
        return ""
    if s.lower().startswith(("http://", "https://")):
        return _normalize_http_url_path_encoding(s)
    base = (homepage or "").strip().rstrip("/")
    if not base:
        return ""
    joined = urljoin(base + "/", s.lstrip("/"))
    return _normalize_http_url_path_encoding(joined)


def _hydrate_result_from_prior_manifest(result: MeetingsScrapeResult, prior: Dict[str, Any]) -> None:
    if not prior:
        return
    hp = str(prior.get("homepage_url") or "").strip()
    if hp:
        result.homepage_url = hp
    cands = prior.get("homepage_url_candidates")
    if isinstance(cands, list) and cands:
        result.homepage_url_candidates = list(cands)
    failures = prior.get("homepage_probe_failures")
    if isinstance(failures, list) and failures:
        result.homepage_probe_failures = list(failures)
    stacks = prior.get("detected_stacks")
    if isinstance(stacks, list) and stacks:
        result.detected_stacks = list(stacks)
    pages = prior.get("pages_fetched")
    if isinstance(pages, list) and pages:
        result.pages_fetched = list(pages)
    pdfs = prior.get("pdfs")
    if isinstance(pdfs, list) and pdfs:
        result.pdfs_downloaded = list(pdfs)
    yt = prior.get("youtube")
    if isinstance(yt, list) and yt:
        result.youtube = list(yt)
    ovs = prior.get("other_video_streams")
    if isinstance(ovs, list) and ovs:
        result.other_video_streams = list(ovs)
    va = prior.get("video_assets")
    if isinstance(va, list) and va:
        result.video_assets = list(va)
    errs = prior.get("errors")
    if isinstance(errs, list) and errs:
        result.errors = list(errs)
    cdp = prior.get("contact_directory_pages")
    if isinstance(cdp, list) and cdp:
        result.contact_directory_pages = list(cdp)
    sc = prior.get("structured_contacts")
    if isinstance(sc, list) and sc:
        result.structured_contact_rows = list(sc)
    bid = str(prior.get("scrape_batch_id") or "").strip()
    if bid:
        result.scrape_batch_id = bid
    cpi = prior.get("contact_profile_images")
    if isinstance(cpi, list) and cpi:
        result.contact_profile_images = list(cpi)


def _suiteone_https_bases_from_urls(urls: List[str]) -> List[str]:
    bases: Set[str] = set()
    for raw in urls:
        u = (raw or "").strip()
        if not u:
            continue
        try:
            p = urlparse(u)
            host = (p.netloc or "").lower().split(":")[0]
            if not host or "suiteonemedia.com" not in host:
                continue
            bases.add(urlunparse(("https", host, "/", "", "", "")))
        except Exception:
            continue
    return sorted(bases)


def _recover_suiteone_event_urls_from_snapshots(
    snap_dir: Path,
    visited: Set[str],
    *,
    page_urls_for_hosts: List[str],
) -> List[str]:
    """Parse saved ``page_*.html`` snapshots for SuiteOne ``/event/?id=`` links (legacy resume without ``_crawl_state.json``)."""
    from bs4 import BeautifulSoup

    bases = _suiteone_https_bases_from_urls(page_urls_for_hosts)
    found: Set[str] = set()
    if not snap_dir.is_dir():
        return []
    for path in sorted(snap_dir.glob("page_*.html")):
        try:
            html = path.read_text(encoding="utf-8", errors="replace")[:2_500_000]
        except OSError:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("a", href=True):
            href = (tag.get("href") or "").strip()
            if not href or href.startswith("#") or href.lower().startswith("javascript:"):
                continue
            low = href.lower()
            full = ""
            if low.startswith("http://") or low.startswith("https://"):
                full = href.split("#", 1)[0]
            elif low.startswith("/event") and bases:
                for b in bases:
                    cand = urljoin(b, href)
                    if "suiteonemedia.com" in cand.lower():
                        full = cand.split("#", 1)[0]
                        break
            if not full:
                continue
            try:
                pl = urlparse(full)
            except Exception:
                continue
            if "suiteonemedia.com" not in (pl.netloc or "").lower():
                continue
            path_l = (pl.path or "").lower()
            if "/event" not in path_l:
                continue
            q = parse_qs(pl.query or "")
            ids = q.get("id") or []
            if not ids:
                continue
            nu = _strip_fragment(full)
            if nu in visited:
                continue
            found.add(nu)

    def _event_id(u: str) -> int:
        try:
            ids = parse_qs(urlparse(u).query or "").get("id") or []
            return int(ids[0]) if ids else 0
        except (ValueError, TypeError):
            return 0

    return sorted(found, key=_event_id, reverse=True)


def _persist_meetings_crawl_state(
    path: Path,
    *,
    jurisdiction_id: str,
    resolved_homepage_url: str,
    visited: Set[str],
    queued: Set[str],
    to_visit: List[str],
    search_seeded: bool,
    pdf_count: int,
    pdfs_seen: Set[str],
    youtube_seen: Set[str],
    other_stream_seen: Set[str],
    contact_page_rows: List[Dict[str, Any]],
    stack_hints: List[str],
) -> None:
    payload = {
        "schema_version": MEETINGS_CRAWL_STATE_SCHEMA_VERSION,
        "jurisdiction_id": jurisdiction_id,
        "resolved_homepage_url": resolved_homepage_url,
        "visited": sorted(visited),
        "queued": sorted(queued),
        "to_visit": list(to_visit),
        "search_seeded": search_seeded,
        "pdf_count": int(pdf_count),
        "pdfs_seen": sorted(pdfs_seen),
        "youtube_seen": sorted(youtube_seen),
        "other_stream_seen": sorted(other_stream_seen),
        "contact_page_rows": contact_page_rows,
        "stack_hints": list(stack_hints),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("meetings_crawl_state_write_failed path={} err={!r}", path, exc)


def _meetings_crawl_state_each_page_enabled() -> bool:
    return (os.getenv("SCRAPED_MEETINGS_PERSIST_CRAWL_STATE_EACH_PAGE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _meetings_log_url(url: str, *, maxlen: int = 160) -> str:
    u = (url or "").strip()
    if len(u) <= maxlen:
        return u
    return u[: max(0, maxlen - 3)] + "..."


def _fs_safe_segment(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', "_", (s or "").strip())[:200] or "unknown"


def _http_response_is_pdf(resp: httpx.Response) -> bool:
    """True if the body looks like a PDF (many ``.pdf`` URLs return HTML without ``Referer`` / cookies)."""
    data = resp.content or b""
    if data.startswith(b"%PDF"):
        return True
    ct = (resp.headers.get("content-type") or "").lower()
    return "application/pdf" in ct and len(data) > 0


def _http_response_is_acceptable_meeting_download(resp: httpx.Response, doc_url: str) -> bool:
    """
    Validate GET body for meeting documents (PDF, Word, RTF, PowerPoint) including S3 ``.docx`` / ``.pdf``.
    """
    suf = meeting_document_storage_suffix(doc_url)
    data = resp.content or b""
    if not data:
        return False
    ct = (resp.headers.get("content-type") or "").lower()
    if suf == ".pdf":
        return _http_response_is_pdf(resp)
    if suf == ".docx":
        if data.startswith(b"PK\x03\x04"):
            return True
        return "wordprocessingml" in ct
    if suf == ".doc":
        if data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            return True
        return "application/msword" in ct
    if suf == ".rtf":
        head = data.lstrip()[:32].upper()
        return head.startswith(b"{\\RTF") or "application/rtf" in ct or "text/rtf" in ct
    if suf == ".pptx":
        if data.startswith(b"PK\x03\x04"):
            return True
        return "presentationml" in ct or "powerpoint" in ct
    if suf == ".ppt":
        if data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            return True
        return "application/vnd.ms-powerpoint" in ct or "ms-powerpoint" in ct
    if suf in (".mp3", ".m4a", ".wav"):
        if "audio/" in ct:
            return len(data) > 200
        if suf == ".mp3":
            if data.startswith(b"ID3"):
                return len(data) > 200
            return data[:2] in (b"\xff\xfb", b"\xff\xfa", b"\xff\xf3") and len(data) > 200
        if suf == ".m4a":
            return (len(data) > 32 and b"ftyp" in data[4:40]) or "mp4" in ct
        if suf == ".wav":
            return data.startswith(b"RIFF") and b"WAVE" in data[:16]
        return len(data) > 500
    return _http_response_is_pdf(resp)


def _meetings_office_to_pdf_enabled() -> bool:
    v = (
        os.getenv("SCRAPED_MEETINGS_OFFICE_TO_PDF") or os.getenv("SCRAPED_MEETINGS_DOCX_TO_PDF") or "true"
    ).strip().lower()
    return v not in ("0", "false", "no", "off")


def _find_libreoffice_executable() -> Optional[str]:
    for name in ("libreoffice", "soffice"):
        hit = shutil.which(name)
        if hit:
            return hit
    return None


def _convert_office_file_to_pdf_sync(src_office: Path) -> Tuple[Optional[Path], str]:
    """
    Run LibreOffice headless to produce ``<stem>.pdf`` next to ``.docx`` / ``.doc``, then delete the
    office file when conversion succeeds.
    """
    if not src_office.is_file():
        return None, "missing_office_file"
    exe = _find_libreoffice_executable()
    if not exe:
        return None, "libreoffice_not_on_path"
    out_dir = src_office.parent
    try:
        subprocess.run(
            [
                exe,
                "--headless",
                "--nodefault",
                "--nolockcheck",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir.resolve()),
                str(src_office.resolve()),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=240,
        )
    except subprocess.TimeoutExpired:
        return None, "libreoffice_timeout"
    except subprocess.CalledProcessError as exc:
        tail = ((exc.stderr or "") + (exc.stdout or ""))[:400]
        return None, f"libreoffice_rc={exc.returncode}:{tail!r}"
    except OSError as exc:
        return None, f"libreoffice_oserror:{exc!r}"
    pdf_path = src_office.with_suffix(".pdf")
    if not pdf_path.is_file() or pdf_path.stat().st_size < 40:
        return None, "libreoffice_missing_pdf_output"
    try:
        src_office.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("meetings_office_unlink_failed path={} detail={}", src_office, repr(exc))
    return pdf_path, ""


# Tuscaloosa + Big Timber pilot cache trees (matches default Colab Drive sync set).
_MEETINGS_PDF_PNG_INVENTORY_PREFIXES: Tuple[str, ...] = (
    "AL/county/county_01125",
    "MT/county/county_30097",
    "AL/municipality/municipality_0177256",
    "MT/municipality/municipality_3006475",
)


def _meetings_pdf_to_png_mode() -> str:
    """``inventory`` (default), ``all`` under meetings root, or ``off``."""
    v = (os.getenv("SCRAPED_MEETINGS_PDF_TO_PNG") or "inventory").strip().lower()
    if v in ("0", "false", "no", "off"):
        return "off"
    if v == "all":
        return "all"
    return "inventory"


def _meetings_pdf_to_png_dpi() -> int:
    raw = (os.getenv("SCRAPED_MEETINGS_PDF_TO_PNG_DPI") or "150").strip()
    try:
        d = int(raw)
    except ValueError:
        return 150
    return max(36, min(600, d))


def _pdf_path_eligible_for_png_pages(pdf_path: Path, meetings_root: Path, mode: str) -> bool:
    if mode == "off":
        return False
    try:
        root = meetings_root.resolve()
        rel = pdf_path.resolve().relative_to(root)
    except (ValueError, OSError):
        return False
    rel_s = rel.as_posix()
    if mode == "all":
        return True
    for prefix in _MEETINGS_PDF_PNG_INVENTORY_PREFIXES:
        if rel_s == prefix or rel_s.startswith(prefix + "/"):
            return True
    return False


def _write_pdf_sibling_png_pages_sync(pdf_path: Path) -> Tuple[int, str]:
    """
    Rasterize ``pdf_path`` to ``<stem>.page_NNN.png`` siblings (one file per page).

    Returns ``(page_count, error_message)``. ``error_message`` is empty on success (``page_count`` may be 0
    if the PDF has no pages). Requires ``pdf2image`` and poppler (``pdftoppm``).
    """
    if not pdf_path.is_file():
        return 0, "missing_pdf_file"
    try:
        from pdf2image import convert_from_path, pdfinfo_from_path
    except ModuleNotFoundError:
        return 0, "pdf2image_not_installed"
    parent = pdf_path.parent
    stem = pdf_path.stem
    try:
        for old in parent.glob(f"{stem}.page_*.png"):
            try:
                old.unlink(missing_ok=True)
            except OSError:
                pass
        info = pdfinfo_from_path(str(pdf_path))
        n = int(info.get("Pages") or 0)
    except Exception as exc:
        return 0, f"pdfinfo_failed:{exc!r}"
    if n < 1:
        return 0, ""
    dpi = _meetings_pdf_to_png_dpi()
    written = 0
    for i in range(1, n + 1):
        try:
            pages = convert_from_path(
                str(pdf_path),
                dpi=dpi,
                first_page=i,
                last_page=i,
            )
        except Exception as exc:
            return written, f"convert_page_{i}:{exc!r}"
        if not pages:
            return written, f"empty_page_{i}"
        out_png = parent / f"{stem}.page_{i:03d}.png"
        try:
            pages[0].save(out_png, format="PNG")
            written += 1
        except Exception as exc:
            return written, f"save_page_{i}:{exc!r}"
    return written, ""


def _meetings_mp3_to_opus_enabled() -> bool:
    """Default **on**. Set ``SCRAPED_MEETINGS_MP3_TO_OPUS=false`` to keep downloaded ``.mp3`` / ``.m4a`` / ``.wav``."""
    v = (os.getenv("SCRAPED_MEETINGS_MP3_TO_OPUS") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _meetings_delete_mp3_after_opus() -> bool:
    """Default **on**. Set ``SCRAPED_MEETINGS_DELETE_MP3_AFTER_OPUS=false`` to retain the source audio after Opus."""
    v = (os.getenv("SCRAPED_MEETINGS_DELETE_MP3_AFTER_OPUS") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _convert_meeting_audio_to_opus_sync(src_audio: Path, _source_suffix: str) -> Tuple[Optional[Path], str]:
    """
    Transcode meeting audio to ``<stem>.opus`` via ``ffmpeg`` (``libopus``), then delete ``src_audio`` when
    :func:`_meetings_delete_mp3_after_opus` is true and the Opus output passes the minimum size check.
    """
    if not src_audio.is_file():
        return None, "missing_audio_file"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None, "ffmpeg_not_on_path"
    opus_path = src_audio.with_suffix(".opus")
    try:
        opus_path.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(src_audio.resolve()),
                "-vn",
                "-c:a",
                "libopus",
                "-b:a",
                "96k",
                str(opus_path.resolve()),
            ],
            check=True,
            capture_output=True,
            timeout=900,
        )
    except subprocess.TimeoutExpired:
        opus_path.unlink(missing_ok=True)
        return None, "ffmpeg_opus_timeout"
    except subprocess.CalledProcessError as exc:
        err_b = (exc.stderr or b"") + (exc.stdout or b"")
        tail = err_b[:500].decode("utf-8", errors="replace")
        opus_path.unlink(missing_ok=True)
        return None, f"ffmpeg_opus_rc={exc.returncode}:{tail!r}"
    except OSError as exc:
        opus_path.unlink(missing_ok=True)
        return None, f"ffmpeg_opus_oserror:{exc!r}"
    try:
        sz = opus_path.stat().st_size
    except OSError:
        opus_path.unlink(missing_ok=True)
        return None, "opus_stat_failed"
    min_b = _meetings_min_opus_bytes_for_mp4_cleanup()
    if sz < min_b:
        try:
            opus_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None, f"opus_too_small_bytes={sz}"
    if _meetings_delete_mp3_after_opus():
        try:
            src_audio.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("meetings_audio_unlink_failed path={} detail={}", src_audio, repr(exc))
    return opus_path, ""


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
    GET a meeting-document URL with ``Referer`` hints (listing page, then homepage).

    Returns ``(response, "")`` when the body matches the expected type (PDF, ``.docx``, …).
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
            if _http_response_is_acceptable_meeting_download(pr, fetch_u):
                return pr, ""
            ct = pr.headers.get("content-type", "")
            prefix = (pr.content or b"")[:80]
            detail = f"{fetch_u!r}:unexpected_body ct={ct!r} prefix={prefix!r}"
    return None, detail or "no_referer_matched"


def _simbli_agenda_html_to_pdf_enabled() -> bool:
    v = (os.getenv("SCRAPED_MEETINGS_SIMBLI_HTML_TO_PDF") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


async def _print_simbli_agenda_html_to_pdf_bytes(
    url: str,
    referers: List[str],
    *,
    timeout_s: float,
    user_agent: str,
) -> Tuple[Optional[bytes], str]:
    """
    Render a Simbli-style HTML agenda/minutes URL to PDF bytes via Playwright.

    Tries each non-empty Referer (listing page, then homepage); falls back to self-referer.
    """
    timeout_ms = int(max(45_000, min(240_000, float(timeout_s) * 1000)))
    last_why = ""
    any_ref = False
    for ref in referers:
        rref = _strip_fragment(ref).strip()
        if not rref:
            continue
        any_ref = True
        pdf_bytes, why = await print_agenda_html_page_to_pdf_via_playwright(
            url,
            referer=rref,
            timeout_ms=timeout_ms,
            user_agent=user_agent,
        )
        if pdf_bytes:
            return pdf_bytes, ""
        last_why = why
    fallback_ref = _strip_fragment(url).strip() or url
    pdf_bytes, why = await print_agenda_html_page_to_pdf_via_playwright(
        url,
        referer=fallback_ref,
        timeout_ms=timeout_ms,
        user_agent=user_agent,
    )
    if pdf_bytes:
        return pdf_bytes, ""
    return None, why or last_why or ("no_referer_for_html_print" if not any_ref else "html_print_failed")


def _jurisdiction_type_from_id(jurisdiction_id: str) -> str:
    if "_" in jurisdiction_id:
        return jurisdiction_id.split("_", 1)[0]
    return "unknown"


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
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        host = ""
    # Sweet Grass County MT posts commissioner recordings as direct MP4 on wp-content (WordPress).
    if host.endswith("sgcountymt.gov"):
        return True
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
    contact_directory_pages: List[Dict[str, Any]] = field(default_factory=list)
    structured_contact_rows: List[Dict[str, Any]] = field(default_factory=list)
    scrape_batch_id: str = ""
    contact_profile_images: List[Dict[str, Any]] = field(default_factory=list)


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


def _structured_contact_extract_enabled() -> bool:
    v = (os.getenv("SCRAPED_CONTACT_STRUCTURED_EXTRACT") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _contact_profile_images_enabled() -> bool:
    v = (os.getenv("SCRAPED_CONTACT_PROFILE_IMAGES") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _contact_profile_image_max() -> int:
    try:
        return max(1, min(200, int((os.getenv("SCRAPED_CONTACT_PROFILE_IMAGE_MAX") or "48").strip())))
    except ValueError:
        return 48


def _contact_profile_images_save_png() -> bool:
    v = (os.getenv("SCRAPED_CONTACT_PROFILE_IMAGES_PNG") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _person_photo_nav_boost_min() -> int:
    try:
        return max(0, min(40, int((os.getenv("SCRAPED_CONTACT_PHOTO_NAV_BOOST_MIN") or "4").strip())))
    except ValueError:
        return 4


def _simbli_meeting_listing_needs_playwright_html(url: str, html: str) -> bool:
    """
    Simbli ``SB_MeetingListing.aspx`` frequently returns a **small shell** over plain HTTP while the
    meeting grid is populated client-side — the scraper needs Chromium to enumerate rows.

    Threshold configurable via ``SCRAPED_MEETINGS_SIMBLI_LISTING_MIN_HTML_CHARS`` (default ``8000``).
    """
    if not playwright_fallback_enabled():
        return False
    if not is_simbli_eboard_host(url):
        return False
    try:
        pq = (urlparse(url).path + "?" + urlparse(url).query).lower()
    except Exception:
        pq = ""
    if "meetinglisting.aspx" not in pq:
        return False
    try:
        min_chars = int((os.getenv("SCRAPED_MEETINGS_SIMBLI_LISTING_MIN_HTML_CHARS") or "8000").strip())
    except ValueError:
        min_chars = 8000
    blob = (html or "").lower()
    if len(html or "") < min_chars:
        return True
    return "viewmeeting(" not in blob


class ComprehensiveDiscoveryPipelineJurisdiction:
    """
    Scrape meeting-related pages and download PDFs under the resolved output root (default
    ``data/cache/scraped_meetings`` in the repo unless ``SCRAPED_MEETINGS_ROOT`` / ``--output-root``).

    Also flags board/council/officials **directory-style** HTML (heuristics + optional
    ``contact_seed_urls``) and extracts structured person rows into the manifest and optionally
    ``bronze.bronze_contacts_scraped``.

    ``max_pdfs`` caps **PDF GETs only**; the HTML crawl (navigation, ``other_video_streams``, …)
    continues until ``max_pages`` so vendor pages with MP4s are still reached after many agendas.

    With ``resume=True``, loads ``_crawl_state.json`` (frontier queue + ``visited``). ``max_pages`` is a
    **total** ceiling on distinct HTML URLs fetched across runs (already recorded in ``visited``
    still counts). Each completed run writes an updated ``_crawl_state.json``.
    """

    def __init__(
        self,
        *,
        output_root: Optional[Path] = None,
        max_pages: int = 80,
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
            resp_final = str(r.url)
            if _simbli_meeting_listing_needs_playwright_html(url, text):
                phtml, perr, pfinal = await fetch_html_via_playwright(
                    url, timeout_ms=timeout_ms, user_agent=_DEFAULT_UA
                )
                if phtml and len(phtml) > len(text):
                    logger.info(
                        f"meetings_playwright_ok_simbli_meeting_listing url={url!r} "
                        f"httpx_chars={len(text)} playwright_chars={len(phtml)}",
                    )
                    text = phtml
                    resp_final = str(pfinal)
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
                return None, f"captcha:{captcha_hint}", resp_final
            return text, "", resp_final
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

        # Explicit job URL (--url / batch row) beats warehouse order (NACO/GSA may lag the live site).
        if _meetings_home_url_is_actionable(passed_canon):
            pk = _strip_fragment(passed_canon)
            uniq = [u for u in uniq if _strip_fragment(u) != pk]
            uniq.insert(0, passed_canon)

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
        resume: bool = False,
        contact_seed_urls: Optional[List[str]] = None,
        persist_contacts_db: bool = False,
    ) -> MeetingsScrapeResult:
        st = (state or "").strip().upper()
        jid = jurisdiction_pk_from_geoid(geoid, jtype)
        if not jid:
            raise ValueError("Could not derive jurisdiction_id from geoid/type")

        initial_hp = _canonical_homepage_url(homepage_url or "")
        logger.info(
            "meetings_scrape_start jurisdiction={} geoid={} state={} homepage={} resume={}",
            jid,
            geoid,
            st,
            (initial_hp[:160] + "...") if len(initial_hp) > 160 else initial_hp,
            resume,
        )

        year_now = datetime.now(timezone.utc).year
        scrape_batch_id = str(uuid.uuid4())
        result = MeetingsScrapeResult(
            jurisdiction_id=jid,
            state=st,
            homepage_url=initial_hp,
            root_dir=self.output_root,
            scrape_batch_id=scrape_batch_id,
        )

        if not skip_output_root_mkdir:
            _mkdir_from_existing_ancestor(self.output_root)

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
        state_path = base_dir / MEETINGS_CRAWL_STATE_FILENAME
        manifest_disk_path = base_dir / "_manifest.json"
        prior_manifest_for_merge: Dict[str, Any] = {}

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

            visited: Set[str] = set()
            queued: Set[str] = set()
            to_visit: List[str] = []
            pdfs_seen: Set[str] = set()
            youtube_seen: Set[str] = set()
            other_stream_seen: Set[str] = set()
            pdf_count = 0
            search_seeded = False
            contact_page_rows: List[Dict[str, Any]] = []
            stack_hints: List[str] = []
            sitemap_summary: Optional[Dict[str, Any]] = None
            resume_mode: Optional[str] = None
            prior_manifest: Dict[str, Any] = {}

            def _enqueue(u: str) -> None:
                nu = _strip_fragment(u)
                if nu in queued:
                    return
                queued.add(nu)
                to_visit.append(u)

            def _enqueue_many_front(urls: List[str]) -> None:
                """Insert ``urls`` at the front of the frontier, preserving order (first = next fetch)."""
                front: List[str] = []
                for u in urls:
                    nu = _strip_fragment(u)
                    if nu in queued:
                        continue
                    queued.add(nu)
                    front.append(u)
                if front:
                    to_visit[:] = front + to_visit

            if resume:
                prior_manifest = _safe_load_json_dict(manifest_disk_path)
                pj = str(prior_manifest.get("jurisdiction_id") or "").strip()
                manifest_jid_ok = pj == jid
                if pj and pj != jid:
                    logger.warning(
                        "meetings_resume_manifest_jurisdiction_mismatch expected={} got={}",
                        jid,
                        pj,
                    )
                    prior_manifest = {}
                    manifest_jid_ok = False
                elif manifest_jid_ok:
                    prior_manifest_for_merge = prior_manifest
                    _hydrate_result_from_prior_manifest(result, prior_manifest)
                    youtube_seen = {
                        str(r.get("url") or "").strip() for r in result.youtube if r.get("url")
                    }
                    other_stream_seen = {
                        str(r.get("url") or "").strip()
                        for r in result.other_video_streams
                        if r.get("url")
                    }
                    pdfs_seen = {
                        _normalize_http_url_path_encoding(str(r["url"]).strip())
                        for r in result.pdfs_downloaded
                        if r.get("url")
                    }
                    pdf_count = len(result.pdfs_downloaded)
                    stack_hints = list(result.detected_stacks or [])

                if manifest_jid_ok:
                    st_raw = _safe_load_json_dict(state_path)
                    if (
                        int(st_raw.get("schema_version") or 0) == MEETINGS_CRAWL_STATE_SCHEMA_VERSION
                        and str(st_raw.get("jurisdiction_id") or "").strip() == jid
                    ):
                        resume_mode = "state"
                        visited = {str(x) for x in (st_raw.get("visited") or [])}
                        queued = {str(x) for x in (st_raw.get("queued") or [])}
                        to_visit = list(st_raw.get("to_visit") or [])
                        search_seeded = bool(st_raw.get("search_seeded"))
                        pdf_count = max(pdf_count, int(st_raw.get("pdf_count") or 0))
                        pdfs_seen = pdfs_seen | {
                            _normalize_http_url_path_encoding(str(x))
                            for x in (st_raw.get("pdfs_seen") or [])
                            if x
                        }
                        youtube_seen = youtube_seen | {str(x) for x in (st_raw.get("youtube_seen") or []) if x}
                        other_stream_seen = other_stream_seen | {
                            str(x) for x in (st_raw.get("other_stream_seen") or []) if x
                        }
                        rows = st_raw.get("contact_page_rows")
                        contact_page_rows = list(rows) if isinstance(rows, list) else []
                        sh = st_raw.get("stack_hints")
                        if isinstance(sh, list) and sh:
                            stack_hints = list(sh)
                            result.detected_stacks = list(stack_hints)
                        hp_saved = str(st_raw.get("resolved_homepage_url") or "").strip()
                        if hp_saved and not (hp or "").strip():
                            hp = hp_saved
                            result.homepage_url = hp
                        sitemap_summary = prior_manifest.get("sitemaps")
                        logger.info(
                            "meetings_resume_state jurisdiction={} visited={} queue_pending={} pdf_count={}",
                            jid,
                            len(visited),
                            len(to_visit),
                            pdf_count,
                        )
                    elif prior_manifest.get("pages_fetched"):
                        resume_mode = "bootstrap"
                        visited = {
                            _strip_fragment(str(u)) for u in (prior_manifest.get("pages_fetched") or []) if u
                        }
                        queued = set(visited)
                        to_visit = []
                        search_seeded = bool(hp and _strip_fragment(hp) in visited)
                        stack_hints = list(result.detected_stacks or [])
                        bp = prior_manifest.get("extracted_contacts") or {}
                        bprows = bp.get("by_page") if isinstance(bp, dict) else None
                        contact_page_rows = list(bprows) if isinstance(bprows, list) else []
                        recovered = _recover_suiteone_event_urls_from_snapshots(
                            snap_dir,
                            visited,
                            page_urls_for_hosts=list(prior_manifest.get("pages_fetched") or []),
                        )
                        for u in recovered:
                            _enqueue(u)
                        logger.warning(
                            "meetings_resume_bootstrap jurisdiction={} recovered_event_urls={} "
                            "(no valid _crawl_state.json; using manifest + HTML snapshots)",
                            jid,
                            len(recovered),
                        )

            structured_contact_rows_accum = list(result.structured_contact_rows)
            contact_directory_pages = list(result.contact_directory_pages)
            contact_profile_images_accum: List[Dict[str, Any]] = list(result.contact_profile_images)

            should_seed_home_and_sitemap = resume_mode != "state"

            if should_seed_home_and_sitemap and _meetings_home_url_is_actionable(hp):
                # Homepage first; WordPress / OpenCivic search URLs are added only after HTML detection
                # (avoids ``/?s=webcast`` noise on Revize, Granicus, static sites, …).
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
            elif should_seed_home_and_sitemap:
                result.errors.append("no_usable_homepage_url")

            contact_seed_list = merged_contact_seed_urls(jid, contact_seed_urls)
            contact_seed_norm: Set[str] = set()
            front_seeds: List[str] = []
            for su in contact_seed_list:
                au = _expand_contact_seed_url((hp or initial_hp or "").strip(), su)
                if au:
                    contact_seed_norm.add(_strip_fragment(au))
                    front_seeds.append(au)
            if front_seeds:
                _enqueue_many_front(front_seeds)
                logger.info(
                    "jurisdiction_contact_seed_urls jurisdiction={} n={}",
                    jid,
                    len(front_seeds),
                )

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

                cdir = classify_contact_directory_page(page_ctx, html)
                seed_hit = _strip_fragment(page_ctx) in contact_seed_norm
                flagged = bool(cdir.get("is_directory")) or seed_hit
                if flagged:
                    rec = {**cdir, "page_url": page_ctx, "is_directory": True}
                    if seed_hit:
                        rec["directory_kind"] = str(rec.get("directory_kind") or "seed_url")
                        ms = list(rec.get("matched_signals") or [])
                        ms.append("cli_seed_url")
                        rec["matched_signals"] = ms
                    contact_directory_pages.append(rec)

                page_structured: List[Dict[str, Any]] = []
                if _structured_contact_extract_enabled() and flagged:
                    page_structured = extract_structured_contacts_from_html(html, page_ctx)
                    for prow in page_structured:
                        prow["source_page_url"] = page_ctx
                        prow["page_classification"] = str(
                            cdir.get("directory_kind") or ("seed_url" if seed_hit else "unknown")
                        )
                        prow["directory_score"] = int(cdir.get("score") or 0)
                        structured_contact_rows_accum.append(prow)

                if _contact_profile_images_enabled() and flagged:
                    # One folder of headshots: file name = contact name in snake_case, or unknown, unknown_2, …
                    img_dir = base_dir / "_contact_images"
                    jobs = extract_profile_image_jobs(
                        html,
                        page_ctx,
                        max_jobs=_contact_profile_image_max(),
                    )
                    seen_img: Set[str] = {str(j.get("image_url") or "") for j in jobs}
                    for prow in page_structured:
                        pu = (prow.get("profile_image_url") or "").strip()
                        if not pu or pu in seen_img:
                            continue
                        seen_img.add(pu)
                        jobs.append(
                            {
                                "person_name": prow.get("person_name"),
                                "title_or_role": prow.get("title_or_role"),
                                "image_url": pu,
                                "match_method": "json_ld_person_row",
                            }
                        )
                    if jobs:
                        try:
                            dl_rows = await download_profile_images(
                                client,
                                jobs,
                                img_dir,
                                referer=page_ctx,
                                max_images=_contact_profile_image_max(),
                                save_as_png=_contact_profile_images_save_png(),
                            )
                            for dr in dl_rows:
                                fn = dr.get("saved_filename")
                                rel = f"_contact_images/{fn}" if fn else ""
                                contact_profile_images_accum.append(
                                    {
                                        **dr,
                                        "discovered_on": page_ctx,
                                        "saved_relative_path": rel or None,
                                    }
                                )
                        except Exception as exc:
                            result.errors.append(f"contact_profile_images:{exc!r}")

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
                    else:
                        try:
                            from scripts.scraping.crawl_llm_sidecar import (
                                maybe_extract_after_readable_txt,
                            )

                            maybe_extract_after_readable_txt(
                                txt_path,
                                page_url=page_ctx,
                                crawl_root=base_dir,
                            )
                        except Exception as exc:
                            result.errors.append(f"ollama_sidecar:{txt_path}:{exc!r}")

                if pdf_count < self.max_pdfs:
                    pdf_jobs = [
                        ("pdf", u, a) for u, a in self._extract_pdf_pairs(html, page_ctx, hp)
                    ]
                    html_jobs: List[Tuple[str, str, str]] = []
                    if _simbli_agenda_html_to_pdf_enabled():
                        html_jobs = [
                            ("html_print", u, a)
                            for u, a in extract_simbli_agenda_minutes_html_pairs(html, page_ctx, hp)
                        ]
                    for kind, pdf_raw, anchor_text in pdf_jobs + html_jobs:
                        pdf = _normalize_http_url_path_encoding(pdf_raw)
                        if pdf in pdfs_seen:
                            continue
                        pdfs_seen.add(pdf)
                        doc_label = classify_document(pdf, anchor_text)
                        y = infer_calendar_folder_year(
                            pdf,
                            anchor_text,
                            doc_label,
                            fallback_year=year_now,
                        )
                        dest_dir = self._target_dir(st, jid, y)
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        storage_suffix = meeting_document_storage_suffix(pdf)
                        dest = allocate_unique_pdf_path(
                            dest_dir,
                            pdf,
                            anchor_text,
                            doc_label,
                            year_fallback=str(y),
                            storage_suffix=storage_suffix,
                        )
                        try:
                            blob: Optional[bytes] = None
                            why = ""
                            if kind == "pdf":
                                pr, why = await _fetch_pdf_with_referers(
                                    client, pdf, referers=[page_ctx, fetch_url, hp]
                                )
                                if pr is not None:
                                    blob = pr.content
                            else:
                                blob, why = await _print_simbli_agenda_html_to_pdf_bytes(
                                    pdf,
                                    referers=[page_ctx, fetch_url, hp],
                                    timeout_s=self.timeout_s,
                                    user_agent=_DEFAULT_UA,
                                )
                            if blob is not None:
                                dest.write_bytes(blob)
                                final_dest = dest
                                final_suffix = storage_suffix
                                converted_from: Optional[str] = None
                                out_bytes = len(blob)
                                if (
                                    kind == "pdf"
                                    and storage_suffix in (".docx", ".doc")
                                    and _meetings_office_to_pdf_enabled()
                                ):
                                    pdf_out, conv_why = await asyncio.to_thread(
                                        _convert_office_file_to_pdf_sync, dest
                                    )
                                    if pdf_out is not None:
                                        final_dest = pdf_out
                                        final_suffix = ".pdf"
                                        converted_from = storage_suffix
                                        try:
                                            blob = final_dest.read_bytes()
                                            out_bytes = len(blob)
                                        except OSError as exc:
                                            result.errors.append(f"office_pdf_read:{pdf}:{exc!r}")
                                            try:
                                                out_bytes = int(final_dest.stat().st_size)
                                            except OSError:
                                                out_bytes = 0
                                    elif conv_why:
                                        result.errors.append(f"office_to_pdf:{pdf}:{conv_why}")
                                if (
                                    kind == "pdf"
                                    and storage_suffix in (".mp3", ".m4a", ".wav")
                                    and _meetings_mp3_to_opus_enabled()
                                ):
                                    opus_out, owhy = await asyncio.to_thread(
                                        _convert_meeting_audio_to_opus_sync, final_dest, storage_suffix
                                    )
                                    if opus_out is not None:
                                        final_dest = opus_out
                                        final_suffix = ".opus"
                                        if converted_from is None:
                                            converted_from = storage_suffix
                                        try:
                                            out_bytes = int(final_dest.stat().st_size)
                                        except OSError as exc:
                                            result.errors.append(f"opus_stat:{pdf}:{exc!r}")
                                    elif owhy:
                                        result.errors.append(f"audio_to_opus:{pdf}:{owhy}")
                                row: Dict[str, Any] = {
                                    "url": pdf,
                                    "path": str(final_dest),
                                    # Calendar year as string in JSON (avoids int in manifests / TS strict JSON).
                                    "year": str(y),
                                    "bytes": out_bytes,
                                    "doc_type": doc_label,
                                    "anchor_text": (anchor_text or "")[:500],
                                    "storage_suffix": final_suffix,
                                }
                                if converted_from:
                                    row["converted_from_suffix"] = converted_from
                                if kind == "html_print":
                                    row["source_kind"] = "html_print"
                                    row["renderer"] = "playwright_pdf"
                                if final_suffix == ".pdf":
                                    png_mode = _meetings_pdf_to_png_mode()
                                    if _pdf_path_eligible_for_png_pages(
                                        final_dest, self.output_root, png_mode
                                    ):
                                        _n_png, png_err = await asyncio.to_thread(
                                            _write_pdf_sibling_png_pages_sync, final_dest
                                        )
                                        if png_err:
                                            result.errors.append(f"pdf_to_png:{pdf}:{png_err}")
                                result.pdfs_downloaded.append(row)
                                pdf_count += 1
                            else:
                                label = (
                                    "document_rejected_bad_body"
                                    if kind == "pdf"
                                    else "simbli_html_print_failed"
                                )
                                result.errors.append(f"{label}:{pdf}:{why}")
                                try:
                                    if dest.is_file():
                                        peek = dest.read_bytes()[:16]
                                        suf = meeting_document_storage_suffix(pdf)
                                        bad = True
                                        if suf == ".pdf":
                                            bad = not peek.startswith(b"%PDF")
                                        elif suf == ".docx":
                                            bad = not peek.startswith(b"PK\x03\x04")
                                        elif suf == ".doc":
                                            bad = not peek.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
                                        elif suf == ".rtf":
                                            bad = not peek.lstrip().lower().startswith(b"{\\rtf")
                                        elif suf == ".pptx":
                                            bad = not peek.startswith(b"PK\x03\x04")
                                        elif suf == ".ppt":
                                            bad = not peek.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
                                        elif suf == ".mp3":
                                            bad = not (
                                                peek.startswith(b"ID3")
                                                or peek[:2] in (b"\xff\xfb", b"\xff\xfa", b"\xff\xf3")
                                            )
                                        elif suf == ".m4a":
                                            bad = len(peek) < 12 or b"ftyp" not in peek[4:20]
                                        elif suf == ".wav":
                                            bad = not peek.startswith(b"RIFF")
                                        if bad:
                                            dest.unlink(missing_ok=True)
                                except OSError:
                                    pass
                        except OSError as exc:
                            result.errors.append(f"pdf_write:{pdf}:{exc}")
                        except Exception as exc:
                            tag = "pdf_dl" if kind == "pdf" else "html_print"
                            result.errors.append(f"{tag}:{pdf}:{exc}")

                        if pdf_count >= self.max_pdfs:
                            break

                # Enqueue linked meeting pages (not yet visited). Simbli listing: prefer ViewMeeting.aspx
                # URLs in DOM order so top-of-grid meetings run before unrelated nav links exhaust max_pages.
                nav_links = self._extract_nav_urls(html, page_ctx, hp)
                if is_simbli_meeting_listing_page_url(page_ctx):
                    prio: List[str] = []
                    tail: List[str] = []
                    for link in nav_links:
                        if MEETING_DOWNLOAD_EXT.search(link):
                            continue
                        low = link.lower()
                        if "viewmeeting.aspx" in low and "mid=" in low:
                            prio.append(link)
                        else:
                            tail.append(link)
                    _enqueue_many_front(prio)
                    nav_links = tail
                else:
                    photo_hints = int(cdir.get("person_adjacent_image_score") or 0)
                    try:
                        page_host = (urlparse(page_ctx).netloc or "").lower()
                    except Exception:
                        page_host = ""
                    html_nav = [l for l in nav_links if not MEETING_DOWNLOAD_EXT.search(l)]
                    pdfs_nav = [l for l in nav_links if MEETING_DOWNLOAD_EXT.search(l)]
                    prio_nav, rest_nav = partition_nav_for_photo_priority(
                        html_nav,
                        page_host=page_host,
                        photo_score=photo_hints,
                        min_photo_score=_person_photo_nav_boost_min(),
                    )
                    if prio_nav:
                        _enqueue_many_front(prio_nav)
                    nav_links = rest_nav + pdfs_nav
                for link in nav_links:
                    if MEETING_DOWNLOAD_EXT.search(link):
                        continue
                    nu = _strip_fragment(link)
                    if nu not in visited:
                        _enqueue(link)

                if _meetings_crawl_state_each_page_enabled():
                    for row in result.pdfs_downloaded:
                        u = row.get("url")
                        if u:
                            pdfs_seen.add(_normalize_http_url_path_encoding(str(u).strip()))
                    pdf_count = len(result.pdfs_downloaded)
                    for r in result.youtube:
                        u = r.get("url")
                        if u:
                            youtube_seen.add(str(u).strip())
                    for r in result.other_video_streams:
                        u = r.get("url")
                        if u:
                            other_stream_seen.add(str(u).strip())
                    _persist_meetings_crawl_state(
                        state_path,
                        jurisdiction_id=jid,
                        resolved_homepage_url=(hp or ""),
                        visited=visited,
                        queued=queued,
                        to_visit=to_visit,
                        search_seeded=search_seeded,
                        pdf_count=pdf_count,
                        pdfs_seen=pdfs_seen,
                        youtube_seen=youtube_seen,
                        other_stream_seen=other_stream_seen,
                        contact_page_rows=contact_page_rows,
                        stack_hints=stack_hints,
                    )

            for row in result.pdfs_downloaded:
                u = row.get("url")
                if u:
                    pdfs_seen.add(_normalize_http_url_path_encoding(str(u).strip()))
            pdf_count = len(result.pdfs_downloaded)
            for r in result.youtube:
                u = r.get("url")
                if u:
                    youtube_seen.add(str(u).strip())
            for r in result.other_video_streams:
                u = r.get("url")
                if u:
                    other_stream_seen.add(str(u).strip())
            _persist_meetings_crawl_state(
                state_path,
                jurisdiction_id=jid,
                resolved_homepage_url=(hp or ""),
                visited=visited,
                queued=queued,
                to_visit=to_visit,
                search_seeded=search_seeded,
                pdf_count=pdf_count,
                pdfs_seen=pdfs_seen,
                youtube_seen=youtube_seen,
                other_stream_seen=other_stream_seen,
                contact_page_rows=contact_page_rows,
                stack_hints=stack_hints,
            )

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
                for va in result.video_assets:
                    u = (va.get("source_mp4_url") or "").strip()
                    if u:
                        seen_mp4.add(u)
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

            fresh_contacts = (
                merge_contact_manifest_rows(contact_page_rows)
                if _meetings_contact_extract_enabled()
                else {}
            )
            pec = prior_manifest_for_merge.get("extracted_contacts") if resume else None
            if resume and isinstance(pec, dict) and pec:
                result.extracted_contacts = _merge_prior_extracted_contacts(pec, fresh_contacts)
            else:
                result.extracted_contacts = fresh_contacts

            prior_sc = prior_manifest_for_merge.get("structured_contacts") if resume else None
            if resume and isinstance(prior_sc, list) and prior_sc:
                result.structured_contact_rows = _merge_structured_contact_rows(
                    prior_sc, structured_contact_rows_accum
                )
            else:
                result.structured_contact_rows = list(structured_contact_rows_accum)

            prior_cdp = prior_manifest_for_merge.get("contact_directory_pages") if resume else None
            if resume and isinstance(prior_cdp, list) and prior_cdp:
                result.contact_directory_pages = _merge_contact_directory_pages(
                    prior_cdp, contact_directory_pages
                )
            else:
                result.contact_directory_pages = list(contact_directory_pages)

            prior_cpi = prior_manifest_for_merge.get("contact_profile_images") if resume else None
            if resume and isinstance(prior_cpi, list) and prior_cpi:
                result.contact_profile_images = _merge_contact_profile_images(
                    prior_cpi, contact_profile_images_accum
                )
            else:
                result.contact_profile_images = list(contact_profile_images_accum)

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
                        "scrape_batch_id": scrape_batch_id,
                        "contact_directory_pages": result.contact_directory_pages,
                        "structured_contacts": result.structured_contact_rows,
                        "contact_profile_images": result.contact_profile_images,
                        "sitemaps": sitemap_summary,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            result.errors.append(f"manifest:{exc}")

        if persist_contacts_db and result.structured_contact_rows:
            dbu = (resolve_database_url() or "").strip()
            if not dbu:
                result.errors.append("contacts_db:no_database_url")
            else:
                try:
                    n_ins = insert_bronze_contacts_scraped(
                        dbu,
                        scrape_batch_id=scrape_batch_id,
                        jurisdiction_id=jid,
                        state_code=st,
                        rows=result.structured_contact_rows,
                    )
                    logger.info(
                        "contacts_bronze_inserted jurisdiction={} rows={} batch={}",
                        jid,
                        n_ins,
                        scrape_batch_id,
                    )
                except Exception as exc:
                    result.errors.append(f"contacts_db:{exc!r}")

        return result


ComprehensiveDiscoveryPipelineMeetings = ComprehensiveDiscoveryPipelineJurisdiction


def _job_contact_seed_urls(job: Dict[str, Any]) -> Optional[List[str]]:
    raw = job.get("contact_seed_urls")
    if raw is None:
        return None
    if isinstance(raw, str):
        out = [s.strip() for s in raw.split(",") if s.strip()]
        return out or None
    if isinstance(raw, list):
        out = [str(s).strip() for s in raw if str(s).strip()]
        return out or None
    return None


async def run_meetings_batch(
    pipe: ComprehensiveDiscoveryPipelineMeetings,
    jobs: List[Dict[str, Any]],
    *,
    concurrency: int,
    resume: bool = False,
) -> List[MeetingsScrapeResult]:
    """
    Run many ``scrape`` calls concurrently with a semaphore (bounded parallelism).

    Each job dict: ``state``, ``geoid``, ``jtype``, ``url``, ``jurisdiction_id``; optional
    ``contact_seed_urls`` (list or comma string) and ``persist_contacts_db`` (bool).
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

    async def one(job: Dict[str, Any]) -> MeetingsScrapeResult:
        jid = job["jurisdiction_id"]
        async with sem:
            try:
                r = await pipe.scrape(
                    state=job["state"],
                    geoid=job["geoid"],
                    jtype=job["jtype"],
                    homepage_url=job["url"],
                    skip_output_root_mkdir=True,
                    resume=resume,
                    contact_seed_urls=_job_contact_seed_urls(job),
                    persist_contacts_db=bool(job.get("persist_contacts_db")),
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
        description=(
            "Jurisdiction crawl: meeting minutes/agendas plus optional board/council contact directory "
            "scraping; default output <repo>/data/cache/scraped_meetings (env SCRAPED_MEETINGS_ROOT overrides)."
        ),
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
    parser.add_argument(
        "--max-pages",
        type=int,
        default=80,
        help="Max distinct HTML pages per jurisdiction (default 80; raise for deep official directories)",
    )
    parser.add_argument("--max-pdfs", type=int, default=80, help="Max PDF downloads per jurisdiction")
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Continue from _crawl_state.json (visited + frontier queue). Treat --max-pages as the "
            "**total** distinct HTML fetch budget across runs. If state is missing but _manifest.json "
            "exists, bootstrap SuiteOne /event URLs from saved _crawl_html snapshots."
        ),
    )
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
    parser.add_argument(
        "--contact-seed-urls",
        default="",
        help=(
            "Comma-separated URLs to fetch first (absolute or site-relative to resolved homepage). "
            "Merged after built-in pilot seeds (see jurisdiction_contact_seed_urls). "
            "Flags directory/contact pages for structured extraction."
        ),
    )
    parser.add_argument(
        "--persist-contacts-db",
        action="store_true",
        help="INSERT structured contact rows into bronze.bronze_contacts_scraped (requires DATABASE_URL / Neon).",
    )
    args = parser.parse_args()

    state = (args.state or "").strip().upper()
    jobs: List[Dict[str, Any]] = []

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

    contact_seeds = [u.strip() for u in (args.contact_seed_urls or "").split(",") if u.strip()]
    if len(jobs) == 1:
        if contact_seeds:
            jobs[0]["contact_seed_urls"] = contact_seeds
        jobs[0]["persist_contacts_db"] = bool(args.persist_contacts_db)

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
    pipe = ComprehensiveDiscoveryPipelineJurisdiction(
        output_root=root,
        max_pages=args.max_pages,
        max_pdfs=args.max_pdfs,
        max_video_downloads=max_video_downloads,
        timeout_s=args.timeout,
    )
    logger.info(
        "meetings_limits resume={} max_pages={} max_pdfs={} max_video_downloads={}",
        args.resume,
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
                resume=args.resume,
                contact_seed_urls=_job_contact_seed_urls(j0),
                persist_contacts_db=bool(j0.get("persist_contacts_db")),
            )
        )
        try:
            root_disp = str(pipe.output_root.resolve())
        except OSError:
            root_disp = str(pipe.output_root.expanduser())
        sample_pdf = out.pdfs_downloaded[0]["path"] if out.pdfs_downloaded else "(no pdfs)"
        logger.success(
            "Done {} — pages={}, pdfs={}, youtube={}, other_streams={}, video_assets={}, "
            "structured_contacts={}, directory_pages={}, profile_images={}, errors={} | root={} | sample_pdf={}",
            out.jurisdiction_id,
            len(out.pages_fetched),
            len(out.pdfs_downloaded),
            len(out.youtube),
            len(out.other_video_streams),
            len(out.video_assets),
            len(out.structured_contact_rows),
            len(out.contact_directory_pages),
            len(out.contact_profile_images),
            len(out.errors),
            root_disp,
            sample_pdf,
        )
    else:
        results = asyncio.run(
            run_meetings_batch(pipe, jobs, concurrency=args.concurrency, resume=args.resume)
        )
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
