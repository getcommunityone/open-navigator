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
- Handle URLs with fragments (e.g. ``.../monthly-meetings/#toggle-id-2``) by fetching the base URL
  and still collecting same-page anchors.
- Collect **YouTube** video and channel links from crawled HTML (anchors, embeds, ``data-src``);
  stored in ``_manifest.json`` under ``youtube`` (not downloaded). After the crawl, each **video**
  URL is checked against YouTube **oEmbed** (title / channel name) and scored for meeting-like
  language (agenda, council, commission, webcast, …). Meeting-related **search keywords** (including
  ``youtube``, ``video``, ``webcast``, ``live``) are only sent to templates we recognized.
- Collect **other** meeting / stream platforms (Vimeo, Facebook video, Twitch, Granicus, Zoom,
  Teams, Google Meet, Wistia, Brightcove, ``.m3u8`` HLS, …) into ``other_video_streams`` in the
  manifest (not downloaded).

- Download PDFs (and optional HTML snapshots of key pages) under:

    ``{root}/{state}/{jurisdiction_type}/{jurisdiction_id}/{year}/``

Default ``root`` is the repo cache **``data/cache/scraped_meetings``** (same ``data/cache`` family
as wikidata JSON). Override with env ``SCRAPED_MEETINGS_ROOT`` (e.g. a Google Drive mount) or
``--output-root``. ``.env`` is loaded first.

TLS: set ``SCRAPED_MEETINGS_HTTP_VERIFY=false`` only if you must (corporate MITM / broken CA store).

CAPTCHA / anti-bot: successful HTTP 200 responses that look like Cloudflare hCaptcha/reCAPTCHA
interstitials (and a few other WAFs) are treated as fetch failures with reason ``captcha:…`` and
log event ``meetings_fetch_captcha_or_bot_wall``. There is no in-repo bypass; use a real browser
(Playwright), a different network / egress IP, lower concurrency, or add an alternate
``website_url`` in ``int_jurisdiction_websites`` (e.g. ``www.…`` vs apex) if the host serves real
HTML to browsers but not to this scraper.

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
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
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

try:
    import psycopg2
except ModuleNotFoundError:  # pragma: no cover
    psycopg2 = None  # type: ignore[misc,assignment]

MEETING_HINTS = re.compile(
    r"(meeting|minutes|minute|agenda|calendar|board|commission|council|hearing|session|video|zoom)",
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


def _fs_safe_segment(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', "_", (s or "").strip())[:200] or "unknown"


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
            out.append(u)
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


def _fetch_retries() -> int:
    """Extra attempts after a timeout (``SCRAPED_MEETINGS_FETCH_RETRIES``, default 1)."""
    try:
        n = int((os.getenv("SCRAPED_MEETINGS_FETCH_RETRIES") or "1").strip())
    except ValueError:
        n = 1
    return max(0, min(n, 5))


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
    """

    def __init__(
        self,
        *,
        output_root: Optional[Path] = None,
        max_pages: int = 25,
        max_pdfs: int = 80,
        timeout_s: float = 120.0,
    ):
        self.output_root = Path(output_root) if output_root else default_scraped_meetings_root()
        self.max_pages = max_pages
        self.max_pdfs = max_pdfs
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

    async def _fetch_page_once(self, client: httpx.AsyncClient, url: str) -> tuple[Optional[str], str]:
        """Single GET attempt (no retries)."""
        try:
            r = await client.get(url, follow_redirects=True)
            if r.status_code != 200:
                reason = f"http_status_{r.status_code}"
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
                return None, reason
            text = r.text
            captcha_hint = _captcha_or_bot_wall_reason(text, r.headers)
            if captcha_hint:
                logfn = logger.debug if _is_probable_site_search_probe(url) else logger.warning
                logfn(
                    "meetings_fetch_captcha_or_bot_wall url={url!r} signal={signal} html_chars={}",
                    url=url,
                    signal=captcha_hint,
                    len(text),
                )
                return None, f"captcha:{captcha_hint}"
            return text, ""
        except httpx.TimeoutException as exc:
            reason = f"timeout:{type(exc).__name__}"
            logfn = logger.debug if _is_probable_site_search_probe(url) else logger.warning
            logfn(
                "meetings_fetch_failed url={url!r} {detail}",
                url=url,
                detail=f"{reason} ({exc!r})",
            )
            return None, reason
        except httpx.RequestError as exc:
            reason = f"request_error:{type(exc).__name__}"
            logfn = logger.debug if _is_probable_site_search_probe(url) else logger.warning
            logfn(
                "meetings_fetch_failed url={url!r} {detail}",
                url=url,
                detail=f"{reason} ({exc!r})",
            )
            return None, reason
        except Exception as exc:
            reason = f"unexpected:{type(exc).__name__}"
            et = type(exc).__name__
            er = repr(exc)
            logfn = logger.debug if _is_probable_site_search_probe(url) else logger.warning
            logfn(f"meetings_fetch_failed url={url!r} type={et} detail={er}")
            return None, reason

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> tuple[Optional[str], str]:
        """
        GET ``url``; return ``(html, "")`` on success, or ``(None, reason)``.

        Retries once (configurable) only when the failure reason starts with ``timeout:`` —
        helps flaky WSL / slow TLS handshakes (``ConnectTimeout`` vs ``ReadTimeout``).
        """
        extra = _fetch_retries()
        last_reason = "unknown"
        for attempt in range(extra + 1):
            html, last_reason = await self._fetch_page_once(client, url)
            if html is not None:
                return html, ""
            if attempt < extra and (last_reason or "").startswith("timeout:"):
                delay = 0.75 * (attempt + 1)
                logger.info(
                    "meetings_fetch_retry_after_timeout url={url!r} attempt={}/{} sleep_s={}",
                    url,
                    attempt + 2,
                    extra + 1,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            break
        return None, last_reason

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
            html, err = await self._fetch_page(client, fu)
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
            else:
                result.errors.append("no_usable_homepage_url")

            while to_visit and len(visited) < self.max_pages and pdf_count < self.max_pdfs:
                url = to_visit.pop(0)
                fetch_url = _strip_fragment(url)
                if fetch_url in visited:
                    continue
                visited.add(fetch_url)

                html, fetch_err = await self._fetch_page(client, fetch_url)
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
                result.pages_fetched.append(fetch_url)

                if _meetings_contact_extract_enabled():
                    chunk = extract_contacts_from_page(html, fetch_url)
                    if chunk.get("emails") or chunk.get("phones"):
                        contact_page_rows.append(chunk)

                if not search_seeded and _is_homepage_document_url(fetch_url, hp):
                    search_seeded = True
                    for su in _discover_site_search_seed_urls(html, hp):
                        _enqueue(su)
                stack_hints = merge_stack_hints(stack_hints, detect_meeting_stacks(html, fetch_url))
                result.detected_stacks = list(stack_hints)

                # Revize / ASP “Site Search” portals (not WordPress ``/?s=``); try a few GET query variants.
                for portal in extract_site_search_portal_urls(html, fetch_url, hp):
                    for variant in site_search_portal_variants(portal):
                        _enqueue(variant)

                for yt in extract_youtube_refs(html, fetch_url):
                    yu = yt.get("url") or ""
                    if not yu or yu in youtube_seen:
                        continue
                    youtube_seen.add(yu)
                    row = {
                        "url": yu,
                        "link_type": yt.get("link_type", "other"),
                        "found_via": yt.get("found_via", ""),
                        "discovered_on": fetch_url,
                    }
                    result.youtube.append(row)

                for vs in extract_other_video_stream_refs(html, fetch_url):
                    vu = vs.get("url") or ""
                    if not vu or vu in other_stream_seen:
                        continue
                    other_stream_seen.add(vu)
                    result.other_video_streams.append(
                        {
                            "url": vu,
                            "platform": vs.get("platform", "unknown"),
                            "found_via": vs.get("found_via", ""),
                            "discovered_on": fetch_url,
                        }
                    )

                # HTML snapshots for audit (outside ``{year}/`` so PDF folders stay clean)
                safe_name = re.sub(r"[^\w.-]+", "_", urlparse(fetch_url).path)[:120] or "index"
                snap_path = snap_dir / f"page_{safe_name}.html"
                try:
                    snap_path.write_text(html[:2_000_000], encoding="utf-8", errors="replace")
                except OSError as exc:
                    result.errors.append(f"snapshot_write:{snap_path}:{exc}")

                for pdf, anchor_text in self._extract_pdf_pairs(html, fetch_url, hp):
                    if pdf in pdfs_seen:
                        continue
                    pdfs_seen.add(pdf)
                    y = _infer_year(pdf, year_now)
                    dest_dir = self._target_dir(st, jid, y)
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    fname = Path(urlparse(pdf).path).name or "document.pdf"
                    fname = _fs_safe_segment(fname)
                    dest = dest_dir / fname
                    try:
                        pr, why = await _fetch_pdf_with_referers(
                            client, pdf, referers=[fetch_url, hp]
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
                for link in self._extract_nav_urls(html, fetch_url, hp):
                    if PDF_EXT.search(link):
                        continue
                    nu = _strip_fragment(link)
                    if nu not in visited:
                        _enqueue(link)

            await self._enrich_youtube_rows(client, result.youtube, homepage_url=hp)

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
                        "errors": result.errors,
                        "extracted_contacts": result.extracted_contacts,
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
                    "meetings_done jurisdiction={} pages={} pdfs={} youtube={} other_streams={} err_lines={}",
                    jid,
                    len(r.pages_fetched),
                    len(r.pdfs_downloaded),
                    len(r.youtube),
                    len(r.other_video_streams),
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
    parser.add_argument("--max-pages", type=int, default=25)
    parser.add_argument("--max-pdfs", type=int, default=80)
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
        help="Max concurrent jurisdictions when running multiple jobs (--geoids or --batch-from-db)",
    )
    args = parser.parse_args()

    state = (args.state or "").strip().upper()
    jobs: List[Dict[str, str]] = []

    if args.batch_from_db:
        jf: Optional[str] = None if (args.type or "").strip().lower() == "all" else args.type
        jobs = load_meeting_scrape_jobs_for_state(state, jf)
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
        raise SystemExit("Provide --geoid, --geoids, or --batch-from-db")

    if not jobs:
        raise SystemExit("No scrape jobs to run (empty list).")

    root = Path(args.output_root).expanduser() if args.output_root else None
    pipe = ComprehensiveDiscoveryPipelineMeetings(
        output_root=root,
        max_pages=args.max_pages,
        max_pdfs=args.max_pdfs,
        timeout_s=args.timeout,
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
            "Done {} — pages={}, pdfs={}, youtube={}, other_streams={}, errors={} | root={} | sample_pdf={}",
            out.jurisdiction_id,
            len(out.pages_fetched),
            len(out.pdfs_downloaded),
            len(out.youtube),
            len(out.other_video_streams),
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
