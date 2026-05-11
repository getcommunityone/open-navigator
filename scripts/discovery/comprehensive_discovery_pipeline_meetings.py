"""
Meetings / minutes scraper (separate from ``ComprehensiveDiscoveryPipeline``).

Goals:
- Start from a jurisdiction homepage (or ``intermediate.int_jurisdiction_websites``).
- Prefer **site search** when present (WordPress-style ``?s=meetings``, ``?s=minutes``, etc.).
- Apply **vendor-style heuristics** (Legistar, Granicus, CivicClerk, …) in
  ``meetings_platform_heuristics`` — same spirit as City-Bureau city-scrapers, without Scrapy.
- Follow agenda / minutes / meeting links from the homepage and search results.
- Handle URLs with fragments (e.g. ``.../monthly-meetings/#toggle-id-2``) by fetching the base URL
  and still collecting same-page anchors.
- Download PDFs (and optional HTML snapshots of key pages) under a CommunityOne folder tree:

    ``{root}/{state}/{jurisdiction_type}/{jurisdiction_id}/{year}/``

Default ``root`` matches **log sync / wikidata**: ``LOG_GDRIVE_MOUNT`` (default
``/mnt/g/My Drive``) + ``CommunityOne/scraped_meetings``, unless ``SCRAPED_MEETINGS_ROOT`` is set
(full override) or ``SCRAPED_MEETINGS_RELATIVE`` changes the subpath. Load ``.env`` first so these
match the rest of the repo. If the mount directory does not exist, falls back to
``~/CommunityOne/scraped_meetings``.

TLS: set ``SCRAPED_MEETINGS_HTTP_VERIFY=false`` only if you must (corporate MITM / broken CA store).

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
from urllib.parse import urlparse, urlunparse

import httpx
from loguru import logger

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.discovery.jurisdiction_discovery_pipeline import (
    INT_JURISDICTION_WEBSITES_TABLE,
    jurisdiction_pk_from_geoid,
    resolve_database_url,
)
from scripts.utils.gdrive_paths import resolve_scraped_meetings_output_root
from scripts.discovery.meetings_platform_heuristics import (
    classify_document,
    detect_meeting_stacks,
    extract_meeting_urls,
    merge_stack_hints,
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
    return resolve_scraped_meetings_output_root()


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
                "Check SCRAPED_MEETINGS_ROOT and that the drive is mounted."
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
                    " Your other scripts use ``LOG_GDRIVE_MOUNT`` (see ``scripts/utils/log_sync.py``). "
                    "Set ``LOG_GDRIVE_MOUNT`` in ``.env`` to the **same** folder that already works "
                    "for logs/exports, **remove** ``SCRAPED_MEETINGS_ROOT`` so meetings uses "
                    "``$LOG_GDRIVE_MOUNT/CommunityOne/scraped_meetings``, or set ``SCRAPED_MEETINGS_ROOT`` "
                    "to that full path. Raw ``G:`` at ``/mnt/g`` without a ``My Drive`` child cannot "
                    "be auto-created from WSL."
                )
            raise RuntimeError(
                f"Cannot create directory {step} while preparing meetings output {target}.{hint}"
            ) from exc


def _strip_fragment(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ""))


def _fs_safe_segment(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', "_", (s or "").strip())[:200] or "unknown"


def _jurisdiction_type_from_id(jurisdiction_id: str) -> str:
    if "_" in jurisdiction_id:
        return jurisdiction_id.split("_", 1)[0]
    return "unknown"


def _infer_year(url: str, fallback: int) -> int:
    m = YEAR_IN_PATH.search(url)
    if m:
        try:
            y = int(m.group(1))
            if 1990 <= y <= 2100:
                return y
        except ValueError:
            pass
    return fallback


def _load_homepage_from_db(jurisdiction_id: str) -> Optional[str]:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 required for --from-db")
    url = resolve_database_url()
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT trim(website_url)
                FROM {INT_JURISDICTION_WEBSITES_TABLE}
                WHERE jurisdiction_id = %s
                  AND website_url IS NOT NULL
                  AND btrim(website_url) <> ''
                ORDER BY CASE website_source
                    WHEN 'uscm' THEN 1
                    WHEN 'naco' THEN 2
                    WHEN 'nces_directory' THEN 3
                    WHEN 'gsa' THEN 4
                    ELSE 5 END
                LIMIT 1
                """,
                (jurisdiction_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return str(row[0]).strip()


_JURISDICTION_ID_RE = re.compile(
    r"^(?P<jtype>county|municipality|state|township|school_district)_(?P<geoid>.+)$",
    re.I,
)


def _prefer_https_homepage() -> bool:
    return (os.getenv("SCRAPED_MEETINGS_PREFER_HTTPS", "true").strip().lower() not in ("0", "false", "no", "off"))


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
            CASE website_source
                WHEN 'uscm' THEN 1
                WHEN 'naco' THEN 2
                WHEN 'nces_directory' THEN 3
                WHEN 'gsa' THEN 4
                ELSE 5 END,
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
    queries = ["meetings", "minutes", "agenda", "board", "council", "commission"]
    out: List[str] = []
    for q in queries:
        out.append(f"{origin}/?s={q}")
    out.append(f"{origin}/?s=meeting+minutes")
    return list(dict.fromkeys(out))


@dataclass
class MeetingsScrapeResult:
    jurisdiction_id: str
    state: str
    homepage_url: str
    root_dir: Path
    detected_stacks: List[str] = field(default_factory=list)
    pages_fetched: List[str] = field(default_factory=list)
    pdfs_downloaded: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36 OpenNavigatorMeetings/1.0"
)


def _http_verify() -> bool:
    v = (os.getenv("SCRAPED_MEETINGS_HTTP_VERIFY") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


class ComprehensiveDiscoveryPipelineMeetings:
    """
    Scrape meeting-related pages and download PDFs into ``SCRAPED_MEETINGS_ROOT`` tree.
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

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> tuple[Optional[str], str]:
        """
        GET ``url``; return ``(html, "")`` on success, or ``(None, reason)``.

        Reasons are logged at WARNING so they appear without ``LOGURU_LEVEL=DEBUG``.
        Loguru ``{{}}`` placeholders in exception text can break ``logger.*("...{}", exc)``;
        use a plain f-string for the exception part only.
        """
        try:
            r = await client.get(url, follow_redirects=True)
            if r.status_code != 200:
                reason = f"http_status_{r.status_code}"
                logger.warning(
                    "meetings_fetch_non_ok url={url!r} status={status} location={loc!r}",
                    url=url,
                    status=r.status_code,
                    loc=(r.headers.get("location") or ""),
                )
                return None, reason
            return r.text, ""
        except httpx.TimeoutException as exc:
            reason = f"timeout:{type(exc).__name__}"
            logger.warning(
                "meetings_fetch_failed url={url!r} {detail}",
                url=url,
                detail=f"{reason} ({exc!r})",
            )
            return None, reason
        except httpx.RequestError as exc:
            reason = f"request_error:{type(exc).__name__}"
            logger.warning(
                "meetings_fetch_failed url={url!r} {detail}",
                url=url,
                detail=f"{reason} ({exc!r})",
            )
            return None, reason
        except Exception as exc:
            reason = f"unexpected:{type(exc).__name__}"
            et = type(exc).__name__
            er = repr(exc)
            logger.warning(f"meetings_fetch_failed url={url!r} type={et} detail={er}")
            return None, reason

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

        hp = _canonical_homepage_url(homepage_url or "")

        year_now = datetime.now(timezone.utc).year
        stack_hints: List[str] = []
        result = MeetingsScrapeResult(
            jurisdiction_id=jid,
            state=st,
            homepage_url=hp,
            root_dir=self.output_root,
        )

        if not skip_output_root_mkdir:
            _mkdir_from_existing_ancestor(self.output_root)

        visited: Set[str] = set()
        queued: Set[str] = set()
        to_visit: List[str] = []
        pdfs_seen: Set[str] = set()
        pdf_count = 0

        def _enqueue(u: str) -> None:
            nu = _strip_fragment(u)
            if nu in queued:
                return
            queued.add(nu)
            to_visit.append(u)

        # Homepage (hash URLs fetch the same document as the base URL)
        _enqueue(hp)
        for su in _search_url_candidates(hp):
            _enqueue(su)

        headers = {
            "User-Agent": _DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        read_s = float(self.timeout_s)
        timeout = httpx.Timeout(connect=25.0, read=read_s, write=25.0, pool=25.0)

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

            while to_visit and len(visited) < self.max_pages and pdf_count < self.max_pdfs:
                url = to_visit.pop(0)
                fetch_url = _strip_fragment(url)
                if fetch_url in visited:
                    continue
                visited.add(fetch_url)

                html, fetch_err = await self._fetch_page(client, fetch_url)
                if not html:
                    result.errors.append(f"no_html:{fetch_url}:{fetch_err or 'unknown'}")
                    continue
                result.pages_fetched.append(fetch_url)
                stack_hints = merge_stack_hints(stack_hints, detect_meeting_stacks(html, fetch_url))
                result.detected_stacks = list(stack_hints)

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
                        pr = await client.get(pdf, follow_redirects=True)
                        if pr.status_code == 200 and pr.content:
                            dest.write_bytes(pr.content)
                            result.pdfs_downloaded.append(
                                {
                                    "url": pdf,
                                    "path": str(dest),
                                    "year": y,
                                    "bytes": len(pr.content),
                                    "doc_type": classify_document(pdf, anchor_text),
                                    "anchor_text": (anchor_text or "")[:500],
                                }
                            )
                            pdf_count += 1
                        else:
                            result.errors.append(f"pdf_http:{pdf}:{pr.status_code}")
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

        manifest_path = base_dir / "_manifest.json"
        try:
            manifest_path.write_text(
                json.dumps(
                    {
                        "jurisdiction_id": jid,
                        "state": st,
                        "homepage_url": hp,
                        "detected_stacks": result.detected_stacks,
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "pages_fetched": result.pages_fetched,
                        "pdfs": result.pdfs_downloaded,
                        "errors": result.errors,
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
                    "meetings_done jurisdiction={} pages={} pdfs={} err_lines={}",
                    jid,
                    len(r.pages_fetched),
                    len(r.pdfs_downloaded),
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
                    errors=[f"exception:{exc!r}"],
                )

    return list(await asyncio.gather(*(one(j) for j in jobs)))


def main() -> None:
    _load_repo_dotenv()
    parser = argparse.ArgumentParser(
        description="Scrape meeting minutes PDFs into SCRAPED_MEETINGS_ROOT (CommunityOne layout)."
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
        help="HTTP read timeout per request (seconds); connect timeout is fixed at 25s",
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
        logger.success(
            "Done {} — pages={}, pdfs={}, errors={}",
            out.jurisdiction_id,
            len(out.pages_fetched),
            len(out.pdfs_downloaded),
            len(out.errors),
        )
    else:
        results = asyncio.run(run_meetings_batch(pipe, jobs, concurrency=args.concurrency))
        n_crash = sum(
            1 for r in results if any(str(e).startswith("exception:") for e in r.errors)
        )
        pages = sum(len(r.pages_fetched) for r in results)
        pdfs = sum(len(r.pdfs_downloaded) for r in results)
        logger.success(
            "Batch done jobs={} scrape_crashes={} total_pages={} total_pdfs={}",
            len(results),
            n_crash,
            pages,
            pdfs,
        )


if __name__ == "__main__":
    main()
