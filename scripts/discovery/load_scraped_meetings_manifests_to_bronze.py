#!/usr/bin/env python3
"""
Load ``_manifest.json`` from the meetings scrape cache into bronze as **one row per scraped link or
document** (never one row per manifest).

**Default cache root** matches the meetings scraper: ``resolve_scraped_meetings_output_root()`` —
``<repo>/data/cache/scraped_meetings`` unless ``SCRAPED_MEETINGS_ROOT`` is set. Use the same env (or
pass ``--cache-root``) as you used when scraping; if you scraped with ``--output-root /path/to/other``,
pass that path as ``--cache-root`` here (or re-scrape without ``--output-root`` into the standard tree).

- **resource_category** ``link`` — HTML pages in ``pages_fetched``, YouTube URLs, other stream URLs.
- **resource_category** ``document`` — PDFs from ``pdfs`` (downloaded file metadata when present).

Each row carries **detected_stacks** and **extracted_contacts** copied from the parent manifest so
you can filter by platform stack or global crawl contacts without joining back to ``_manifest.json``.
**contact_hints** still narrows emails/phones to rows whose URL matches ``extracted_contacts.by_page``.
HTTP(S) URLs are **path-normalized on load** (e.g. spaces to ``%20``) so bronze stays correct even if
an older manifest still has raw spaces in ``pdfs[].url`` — re-run this script only; no rescrape required.

DDL: ``packages/hosting/scripts/neon/migrations/020_recreate_bronze_events_meetings_scraped_link_document.sql``.

Examples::

    .venv/bin/python scripts/discovery/load_scraped_meetings_manifests_to_bronze.py --state AL --apply-ddl
    .venv/bin/python scripts/discovery/load_scraped_meetings_manifests_to_bronze.py -s AL
    .venv/bin/python scripts/discovery/load_scraped_meetings_manifests_to_bronze.py -s AL --cache-root /path/to/scrape/root
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, unquote_plus, urlparse, urlunparse

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from loguru import logger

try:
    import psycopg2
    from psycopg2.extras import Json, execute_batch
except ModuleNotFoundError as exc:  # pragma: no cover
    if exc.name != "psycopg2":
        raise
    psycopg2 = None  # type: ignore[misc,assignment]

from scripts.discovery.jurisdiction_discovery_pipeline import resolve_database_url
from scripts.discovery.meeting_document_naming import (
    date_from_url_query,
    pdf_meeting_title as _pdf_meeting_title,
    pick_meeting_date as _pick_meeting_date,
)
from scripts.utils.gdrive_paths import resolve_scraped_meetings_output_root
from scripts.utils.http_url_normalize import normalize_http_url_path_encoding as _norm_http_url

from core_lib.jurisdictions.jurisdiction_id import parse_jurisdiction_id as _parse_jurisdiction_id

MIGRATION_PATH = _root / "scripts" / "deployment" / "neon" / "migrations" / "020_recreate_bronze_events_meetings_scraped_link_document.sql"

TABLE_FOR_PREFIX = {
    "county": "bronze.bronze_events_meetings_counties_scraped",
    "municipality": "bronze.bronze_events_meetings_municipalities_scraped",
    "school_district": "bronze.bronze_events_meetings_school_districts_scraped",
}

CACHE_TYPE_DIRS = {
    "county": "county",
    "municipality": "municipality",
    "school_district": "school",
}

_MEETING_HINT = re.compile(
    r"(agenda|minute|minutes|packet|webcast|livestream|live[-_]?stream|board[-_]?of|"
    r"board[-_]?meeting|city[-_]?council|county[-_]?commission|commission|hearing|"
    r"town[-_]?hall|calendar|township|school[-_]?board|eboard|simbli|granicus|legistar|"
    r"video\.php|watch\?v=|youtu\.be/)",
    re.I,
)


def _url_key(u: str) -> str:
    p = urlparse((u or "").strip())
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, "")).rstrip("/").lower()


def _sha256_url(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


def _parse_scraped_at(raw: Any) -> datetime:
    if raw is None:
        return datetime.now(timezone.utc)
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    s = str(raw).strip()
    if not s:
        return datetime.now(timezone.utc)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _html_meeting_title(url: str) -> str:
    q = parse_qs(urlparse(url).query)
    for key in ("pg", "title", "t"):
        vals = q.get(key) or []
        if vals and vals[0]:
            return unquote_plus(vals[0]).replace("+", " ")[:500]
    seg = [s for s in urlparse(url).path.split("/") if s]
    return (seg[-1] if seg else url)[:500]


def _is_likely_meeting_html(url: str) -> bool:
    u = url.lower()
    if _MEETING_HINT.search(u):
        return True
    d, _ = date_from_url_query(url)
    if d and ("calendar" in u or "event" in u or "meeting" in u or "display" in u):
        return True
    return False


def _is_likely_meeting_pdf(doc_type: Optional[str], anchor: str, url: str) -> bool:
    dt = (doc_type or "").lower()
    if dt in ("agenda", "minutes", "packet", "video", "meeting"):
        return True
    blob = f"{anchor} {url}".lower()
    return _MEETING_HINT.search(blob) is not None


def _is_likely_meeting_youtube(row: Dict[str, Any]) -> bool:
    u = (row.get("url") or "").lower()
    rel = (row.get("meeting_relevance") or "").lower()
    if "skipped_non_video" in rel or "channel" in (row.get("link_type") or "").lower():
        return False
    if "watch?v=" in u or "youtu.be/" in u:
        return True
    return "video" in (row.get("link_type") or "").lower()


def _is_likely_meeting_other_stream(row: Dict[str, Any]) -> bool:
    u = (row.get("url") or "").lower()
    return any(
        x in u
        for x in (
            "zoom.us",
            "teams.microsoft",
            "meet.google",
            "vimeo.com",
            "m3u8",
            "gomeet.com",
        )
    )


def _contact_hints_by_url(manifest: Dict[str, Any]) -> Dict[str, Dict[str, List[str]]]:
    out: Dict[str, Dict[str, List[str]]] = {}
    ec = manifest.get("extracted_contacts") or {}
    for row in ec.get("by_page") or []:
        if not isinstance(row, dict):
            continue
        pu = row.get("page_url")
        if not pu or not isinstance(pu, str):
            continue
        key = _url_key(_norm_http_url(pu))
        emails = [str(x) for x in (row.get("emails") or []) if x]
        phones = [str(x) for x in (row.get("phones") or []) if x]
        if not emails and not phones:
            continue
        slot = out.setdefault(key, {"emails": [], "phones": []})
        for e in emails:
            if e not in slot["emails"]:
                slot["emails"].append(e)
        for ph in phones:
            if ph not in slot["phones"]:
                slot["phones"].append(ph)
    return out


def _hints_for_url(hmap: Dict[str, Dict[str, List[str]]], url: str) -> Optional[Dict[str, Any]]:
    key = _url_key(_norm_http_url(url))
    slot = hmap.get(key)
    if not slot or (not slot.get("emails") and not slot.get("phones")):
        return None
    return {"emails": slot["emails"], "phones": slot["phones"]}


def _rel_local_path(abs_path: str, repo_root: Path) -> Optional[str]:
    if not abs_path:
        return None
    try:
        return str(Path(abs_path).resolve().relative_to(repo_root.resolve()))
    except Exception:
        return str(abs_path)


def _granular_rows_for_manifest(
    manifest: Dict[str, Any],
    manifest_path: Path,
    repo_root: Path,
) -> Optional[List[Tuple[Any, ...]]]:
    jid = str(manifest.get("jurisdiction_id") or "").strip()
    _jt, geoid, _slug = _parse_jurisdiction_id(jid)
    if not geoid:
        logger.warning("Skip manifest with unknown jurisdiction_id={}", jid)
        return None
    state_code = str(manifest.get("state") or "").strip().upper()[:2]
    if len(state_code) != 2:
        return None
    scraped_at = _parse_scraped_at(manifest.get("scraped_at"))
    try:
        rel_manifest = str(manifest_path.resolve().relative_to(repo_root.resolve()))
    except Exception:
        rel_manifest = str(manifest_path)
    homepage = (manifest.get("homepage_url") or "").strip() or None
    hmap = _contact_hints_by_url(manifest)
    stacks_j = Json(manifest.get("detected_stacks") or [])
    contacts_j = Json(manifest.get("extracted_contacts") or {})

    rows: List[Tuple[Any, ...]] = []

    for page_url in manifest.get("pages_fetched") or []:
        if not isinstance(page_url, str) or not page_url.strip():
            continue
        u = _norm_http_url(page_url.strip())
        is_m = _is_likely_meeting_html(u)
        md, mdsrc = (None, None)
        if is_m:
            md, mdsrc = date_from_url_query(u)
        title = _html_meeting_title(u)
        hints = _hints_for_url(hmap, u)
        rows.append(
            (
                jid,
                state_code,
                geoid,
                homepage,
                scraped_at,
                rel_manifest,
                "link",
                "html_page",
                u,
                _sha256_url(u),
                None,
                None,
                None,
                None,
                stacks_j,
                contacts_j,
                Json(hints) if hints else None,
                is_m,
                md,
                mdsrc,
                title,
                None,
                Json({"kind": "html_page", "url": u}),
            )
        )

    for pdf in manifest.get("pdfs") or []:
        if not isinstance(pdf, dict):
            continue
        u = _norm_http_url(str(pdf.get("url") or "").strip())
        if not u:
            continue
        anchor = str(pdf.get("anchor_text") or "").strip()
        doc_type = str(pdf.get("doc_type") or "").strip() or None
        is_m = _is_likely_meeting_pdf(doc_type, anchor, u)
        md, mdsrc = _pick_meeting_date(url=u, anchor=anchor, doc_type=doc_type)
        if is_m and md is None and pdf.get("year"):
            ys = str(pdf.get("year")).strip()[:4]
            if ys.isdigit():
                try:
                    md = date(int(ys), 1, 1)
                    mdsrc = "manifest_year_only"
                except ValueError:
                    pass
        title = _pdf_meeting_title(anchor, u)
        hints = _hints_for_url(hmap, u)
        lp = _rel_local_path(str(pdf.get("path") or ""), repo_root)
        rows.append(
            (
                jid,
                state_code,
                geoid,
                homepage,
                scraped_at,
                rel_manifest,
                "document",
                "pdf",
                u,
                _sha256_url(u),
                lp,
                pdf.get("bytes"),
                doc_type,
                anchor or None,
                stacks_j,
                contacts_j,
                Json(hints) if hints else None,
                is_m,
                md,
                mdsrc,
                title,
                None,
                Json(pdf),
            )
        )

    for yt in manifest.get("youtube") or []:
        if not isinstance(yt, dict):
            continue
        u = _norm_http_url(str(yt.get("url") or "").strip())
        if not u:
            continue
        is_m = _is_likely_meeting_youtube(yt)
        md, mdsrc = None, None
        title = u[:500]
        hints = _hints_for_url(hmap, u)
        rows.append(
            (
                jid,
                state_code,
                geoid,
                homepage,
                scraped_at,
                rel_manifest,
                "link",
                "youtube",
                u,
                _sha256_url(u),
                None,
                None,
                None,
                None,
                stacks_j,
                contacts_j,
                Json(hints) if hints else None,
                is_m,
                md,
                mdsrc,
                title,
                None,
                Json(yt),
            )
        )

    for ot in manifest.get("other_video_streams") or []:
        if not isinstance(ot, dict):
            continue
        u = _norm_http_url(str(ot.get("url") or "").strip())
        if not u:
            continue
        anchor = str(ot.get("anchor_text") or "").strip()
        is_m = _is_likely_meeting_other_stream(ot) or bool(
            anchor and _MEETING_HINT.search(anchor)
        )
        md, mdsrc = _pick_meeting_date(url=u, anchor=anchor, doc_type="video")
        title = (anchor or u)[:500]
        rows.append(
            (
                jid,
                state_code,
                geoid,
                homepage,
                scraped_at,
                rel_manifest,
                "link",
                "other_stream",
                u,
                _sha256_url(u),
                None,
                None,
                None,
                anchor or None,
                stacks_j,
                contacts_j,
                Json(_hints_for_url(hmap, u)) if _hints_for_url(hmap, u) else None,
                is_m,
                md,
                mdsrc,
                title,
                None,
                Json(ot),
            )
        )

    return rows


def _manifest_paths(cache_root: Path, state: str) -> List[Path]:
    st = state.strip().upper()
    base = cache_root / st
    if not base.is_dir():
        logger.warning("No cache directory at {}", base)
        return []
    paths: List[Path] = []
    for _jt, seg in CACHE_TYPE_DIRS.items():
        d = base / seg
        if not d.is_dir():
            continue
        for child in sorted(d.iterdir()):
            if not child.is_dir():
                continue
            mf = child / "_manifest.json"
            if mf.is_file():
                paths.append(mf)
    return paths


def _classify_jurisdiction(jurisdiction_id: str) -> Optional[str]:
    jt, _geoid, _slug = _parse_jurisdiction_id((jurisdiction_id or "").strip())
    return jt


def _apply_ddl(conn: Any) -> None:
    if not MIGRATION_PATH.is_file():
        raise FileNotFoundError(f"Migration SQL not found: {MIGRATION_PATH}")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.success("Applied DDL from {}", MIGRATION_PATH)


_INSERT_SQL = """
INSERT INTO {table} (
    jurisdiction_id,
    state_code,
    census_geoid,
    homepage_url,
    manifest_scraped_at,
    manifest_relative_path,
    resource_category,
    resource_kind,
    url,
    url_sha256,
    local_path,
    file_bytes,
    doc_type,
    anchor_or_link_text,
    detected_stacks,
    extracted_contacts,
    contact_hints,
    is_likely_meeting,
    meeting_date,
    meeting_date_source,
    meeting_title,
    meeting_attendees,
    raw_resource
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
"""


def _dedupe_rows_by_url_sha256(rows: List[Tuple[Any, ...]]) -> List[Tuple[Any, ...]]:
    """One row per (jurisdiction_id, url_sha256); manifests may list the same URL twice after normalization."""
    seen: Set[str] = set()
    out: List[Tuple[Any, ...]] = []
    for r in rows:
        sha = str(r[9])
        if sha in seen:
            continue
        seen.add(sha)
        out.append(r)
    return out


def _load_manifest_to_table(conn: Any, table: str, manifest: Dict[str, Any], manifest_path: Path, repo_root: Path) -> int:
    jid = str(manifest.get("jurisdiction_id") or "").strip()
    rows = _granular_rows_for_manifest(manifest, manifest_path, repo_root)
    if rows is None:
        return 0
    rows = _dedupe_rows_by_url_sha256(rows)
    sql = _INSERT_SQL.format(table=table)
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM {table} WHERE jurisdiction_id = %s", (jid,))
        if rows:
            execute_batch(cur, sql, rows, page_size=500)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "If you omit --state, set SCRAPED_MEETINGS_STATE=AL (or pass -s AL). "
            "Use --apply-ddl once per DB to run migration 020 (drops and recreates the three tables). "
            "Default --cache-root matches SCRAPED_MEETINGS_ROOT / data/cache/scraped_meetings (same as the scraper)."
        ),
    )
    parser.add_argument(
        "-s",
        "--state",
        default=os.environ.get("SCRAPED_MEETINGS_STATE", "").strip().upper() or None,
        metavar="ST",
        help="USPS state code (e.g. AL). Default: env SCRAPED_MEETINGS_STATE if set.",
    )
    parser.add_argument(
        "--cache-root",
        type=str,
        default="",
        help=(
            "Root containing {STATE}/county|municipality|school/.../jurisdiction_id/_manifest.json. "
            "Default: same as meetings scraper (SCRAPED_MEETINGS_ROOT or repo data/cache/scraped_meetings)."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=str,
        default=str(_root),
        help="Repository root (for relative paths in JSON)",
    )
    parser.add_argument(
        "--apply-ddl",
        action="store_true",
        help=f"Run {MIGRATION_PATH.name} (DROP + CREATE link/document-per-row tables).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse manifests only; no DB writes")
    args = parser.parse_args()

    state_raw = (args.state or "").strip().upper()
    if len(state_raw) != 2:
        parser.error(
            "need a two-letter USPS state: pass --state AL (or -s AL), or export "
            "SCRAPED_MEETINGS_STATE=AL. Example:\n"
            "  .venv/bin/python scripts/discovery/load_scraped_meetings_manifests_to_bronze.py --state AL"
        )
    state = state_raw

    if psycopg2 is None and not args.dry_run:
        raise SystemExit("psycopg2 is required unless --dry-run")

    repo_root = Path(args.repo_root).expanduser().resolve()
    cache_root = (
        Path(args.cache_root).expanduser().resolve()
        if (args.cache_root or "").strip()
        else resolve_scraped_meetings_output_root().resolve()
    )

    paths = _manifest_paths(cache_root, state)
    logger.info("Found {} manifest(s) under {}", len(paths), cache_root / state)

    conn = None
    if not args.dry_run:
        conn = psycopg2.connect(resolve_database_url())
        if args.apply_ddl:
            _apply_ddl(conn)

    n_ok = 0
    n_skip = 0
    n_rows = 0
    for mf in paths:
        try:
            manifest = json.loads(mf.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Unreadable manifest {}: {}", mf, exc)
            n_skip += 1
            continue
        jid = str(manifest.get("jurisdiction_id") or "").strip()
        jt = _classify_jurisdiction(jid)
        if not jt:
            n_skip += 1
            continue
        table = TABLE_FOR_PREFIX.get(jt)
        if not table:
            n_skip += 1
            continue
        if args.dry_run:
            rows = _granular_rows_for_manifest(manifest, mf, repo_root)
            n_r = len(rows or [])
            n_meet = sum(1 for r in (rows or []) if r[17])  # is_likely_meeting
            logger.info("[dry-run] {} -> {} rows={} likely_meeting={}", jid, table, n_r, n_meet)
            n_ok += 1
            n_rows += n_r
            continue
        assert conn is not None
        try:
            inserted = _load_manifest_to_table(conn, table, manifest, mf, repo_root)
            conn.commit()
            n_ok += 1
            n_rows += inserted
        except Exception as exc:
            conn.rollback()
            logger.error("Load failed {} {}: {}", table, jid, exc)
            n_skip += 1

    if conn is not None:
        conn.close()

    logger.success(
        "Done state={} manifests_ok={} skipped_or_failed={} total_url_rows={}",
        state,
        n_ok,
        n_skip,
        n_rows,
    )


if __name__ == "__main__":
    main()
