"""
Discover meeting-related page URLs from ``robots.txt`` and XML sitemaps (``sitemap.xml``,
``sitemap index``, WordPress sitemaps).

When persistence is enabled (default), each successful HTTP response is written under
``{jurisdiction_dir}/_sitemaps/raw/`` and a **database-oriented** export is written:

- ``sitemap_inventory.json`` — bundle metadata and per-document summaries (counts, paths, hashes).
- ``sitemap_rows.ndjson`` — one JSON object per line with **identical keys** on every row
  (``row_kind`` of ``document`` or ``loc``) for bulk load into Postgres / BigQuery / etc.

Disable crawling with env ``SCRAPED_MEETINGS_SITEMAP=false``.
Disable writing artifacts (still enqueues meeting candidates) with
``SCRAPED_MEETINGS_SITEMAP_PERSIST=false``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TextIO

import httpx
from loguru import logger
from urllib.parse import urljoin, urlparse

from scripts.discovery.meetings_platform_heuristics import (
    PDF_EXT,
    is_linked_local_meeting_microsite,
    is_same_site,
    is_trusted_offsite,
    is_vendor_meeting_page_url,
)

MEETING_URL_HINT = re.compile(
    r"(meeting|minutes|minute|agenda|calendar|board|commission|council|hearing|session|video|zoom|webcast)",
    re.I,
)

SCHEMA_VERSION = 1

# Every NDJSON row includes these keys (null when not applicable).
SITEMAP_ROW_KEYS: tuple[str, ...] = (
    "schema_version",
    "jurisdiction_id",
    "state",
    "geoid",
    "jurisdiction_type",
    "homepage_url",
    "collected_at",
    "row_kind",
    "sitemap_document_id",
    "request_url",
    "response_final_url",
    "http_status",
    "content_kind",
    "storage_rel_path",
    "byte_length",
    "sha256_hex",
    "xml_root_local_tag",
    "is_sitemap_index",
    "parse_ok",
    "parse_error",
    "sitemap_directive_urls",
    "loc_url",
    "loc_role",
    "meeting_candidate",
    "parent_sitemap_document_id",
    "loc_index",
)

_DEFAULT_MAX_BODY_BYTES = 8_000_000
_DEFAULT_MAX_OUTPUT_URLS = 2_000
_DEFAULT_MAX_CHILD_SITEMAPS = 40
_DEFAULT_MAX_DEPTH = 3
_DEFAULT_MAX_LOCS_PER_DOC_NDJSON = 100_000
_DEFAULT_MAX_TOTAL_LOC_NDJSON = 500_000


def _sitemap_enabled() -> bool:
    v = (os.getenv("SCRAPED_MEETINGS_SITEMAP") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _sitemap_persist_enabled() -> bool:
    v = (os.getenv("SCRAPED_MEETINGS_SITEMAP_PERSIST") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _int_env(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        return max(minimum, int((os.getenv(name) or str(default)).strip()))
    except ValueError:
        return default


def _origin(homepage: str) -> str:
    p = urlparse((homepage or "").strip())
    if not p.scheme or not p.netloc:
        return ""
    return f"{p.scheme}://{p.netloc}"


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _parse_robots_sitemap_directives(robots_txt: str) -> List[str]:
    out: List[str] = []
    for line in (robots_txt or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.lower().startswith("sitemap:"):
            u = s.split(":", 1)[1].strip()
            if u:
                out.append(u)
    return out


def _default_sitemap_seeds(origin: str) -> List[str]:
    return [
        urljoin(origin + "/", "sitemap.xml"),
        urljoin(origin + "/", "sitemap_index.xml"),
        urljoin(origin + "/", "sitemap-index.xml"),
        urljoin(origin + "/", "wp-sitemap.xml"),
        urljoin(origin + "/", "page-sitemap.xml"),
    ]


def _collect_loc_elements(root: ET.Element) -> List[str]:
    locs: List[str] = []
    for el in root.iter():
        if _local_tag(el.tag) != "loc":
            continue
        t = (el.text or "").strip()
        if t:
            locs.append(t)
    return locs


def _is_sitemap_index_root(root: ET.Element) -> bool:
    return _local_tag(root.tag) == "sitemapindex"


def _loc_passes_filters(loc: str, homepage: str) -> bool:
    u = (loc or "").strip()
    if not u.startswith(("http://", "https://")):
        return False
    if PDF_EXT.search(u):
        return bool(
            is_same_site(u, homepage)
            or is_linked_local_meeting_microsite(u, homepage)
            or is_trusted_offsite(u)
        )
    if is_vendor_meeting_page_url(u):
        return True
    if not MEETING_URL_HINT.search(u):
        return False
    return bool(
        is_same_site(u, homepage)
        or is_linked_local_meeting_microsite(u, homepage)
        or is_trusted_offsite(u)
    )


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rel_under_jurisdiction(output_dir: Path, jurisdiction_base: Path) -> str:
    """``_sitemaps/...`` path relative to jurisdiction folder."""
    try:
        rel = output_dir.resolve().relative_to(jurisdiction_base.resolve())
    except ValueError:
        rel = Path(output_dir.name)
    return str(rel).replace("\\", "/")


def _blank_row(meta: Dict[str, Any]) -> Dict[str, Any]:
    row = {k: None for k in SITEMAP_ROW_KEYS}
    row["schema_version"] = SCHEMA_VERSION
    row["jurisdiction_id"] = meta["jurisdiction_id"]
    row["state"] = meta["state"]
    row["geoid"] = meta["geoid"]
    row["jurisdiction_type"] = meta["jurisdiction_type"]
    row["homepage_url"] = meta["homepage_url"]
    row["collected_at"] = meta["collected_at"]
    return row


@dataclass
class SitemapPersistConfig:
    """Write under ``output_dir`` (typically ``.../county_xxx/_sitemaps``)."""

    output_dir: Path
    jurisdiction_base_dir: Path
    jurisdiction_id: str
    state: str
    geoid: str
    jurisdiction_type: str
    homepage_url: str


@dataclass
class SitemapDiscoveryResult:
    enqueue_urls: List[str] = field(default_factory=list)
    inventory_rel_path: Optional[str] = None
    ndjson_rel_path: Optional[str] = None
    documents_recorded: int = 0
    ndjson_row_count: int = 0
    persist_errors: List[str] = field(default_factory=list)


class _NdjsonWriter:
    def __init__(self, path: Path, meta: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._meta = meta
        self._fp: Optional[TextIO] = None
        self.document_rows = 0
        self.loc_rows = 0

    def __enter__(self) -> "_NdjsonWriter":
        self._fp = self._path.open("w", encoding="utf-8")
        return self

    def __exit__(self, *args: Any) -> None:
        if self._fp:
            self._fp.close()
            self._fp = None

    def write(self, partial: Dict[str, Any]) -> None:
        if not self._fp:
            return
        row = _blank_row(self._meta)
        row.update(partial)
        for k in SITEMAP_ROW_KEYS:
            if k not in row:
                row[k] = None
        self._fp.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        rk = row.get("row_kind")
        if rk == "document":
            self.document_rows += 1
        elif rk == "loc":
            self.loc_rows += 1


async def _http_get_content(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_bytes: int,
) -> tuple[Optional[int], str, Optional[bytes], Optional[str]]:
    """
    Returns ``(status_code, final_url, body_bytes, error)``.
    ``body_bytes`` is set only for OK responses within ``max_bytes``.
    """
    try:
        r = await client.get(url, follow_redirects=True)
        final = str(r.url)
        status = r.status_code
        if status != 200:
            return status, final, None, None
        raw = r.content
        if len(raw) > max_bytes:
            return status, final, None, f"oversize_{len(raw)}_bytes"
        return status, final, raw, None
    except Exception as exc:
        return None, url, None, repr(exc)


def _write_raw_file(raw_dir: Path, doc_id: str, content_kind: str, body: bytes) -> tuple[str, str]:
    h = _sha256_hex(body)[:12]
    if content_kind == "robots_txt":
        suffix = "txt"
    elif content_kind == "sitemap_xml":
        suffix = "xml"
    else:
        suffix = "bin"
    fname = f"{doc_id}_{h}.{suffix}"
    path = raw_dir / fname
    path.write_bytes(body)
    rel = f"_sitemaps/raw/{fname}"
    return rel, _sha256_hex(body)


async def discover_meeting_candidate_urls_from_sitemaps(
    client: httpx.AsyncClient,
    homepage: str,
    *,
    persist: Optional[SitemapPersistConfig] = None,
) -> SitemapDiscoveryResult:
    """
    Return meeting-candidate URLs to enqueue plus optional persisted sitemap artifacts.
    """
    out = SitemapDiscoveryResult()
    if not _sitemap_enabled():
        return out

    origin = _origin(homepage)
    if not origin:
        return out

    do_persist = persist is not None and _sitemap_persist_enabled()

    max_body = _int_env(
        "SCRAPED_MEETINGS_SITEMAP_MAX_BYTES",
        _DEFAULT_MAX_BODY_BYTES,
        minimum=4096,
    )
    max_out = _int_env("SCRAPED_MEETINGS_SITEMAP_MAX_URLS", _DEFAULT_MAX_OUTPUT_URLS)
    max_children = _int_env(
        "SCRAPED_MEETINGS_SITEMAP_MAX_CHILD_SITEMAPS",
        _DEFAULT_MAX_CHILD_SITEMAPS,
    )
    max_depth = _int_env("SCRAPED_MEETINGS_SITEMAP_MAX_DEPTH", _DEFAULT_MAX_DEPTH)
    max_locs_per_doc_ndjson = _int_env(
        "SCRAPED_MEETINGS_SITEMAP_MAX_LOCS_PER_DOC_NDJSON",
        _DEFAULT_MAX_LOCS_PER_DOC_NDJSON,
        minimum=1,
    )
    max_total_loc_ndjson = _int_env(
        "SCRAPED_MEETINGS_SITEMAP_MAX_TOTAL_LOC_NDJSON",
        _DEFAULT_MAX_TOTAL_LOC_NDJSON,
        minimum=1,
    )

    collected_at = datetime.now(timezone.utc).isoformat()
    meta: Dict[str, Any] = {
        "jurisdiction_id": (persist.jurisdiction_id if persist else ""),
        "state": (persist.state if persist else ""),
        "geoid": (persist.geoid if persist else ""),
        "jurisdiction_type": (persist.jurisdiction_type if persist else ""),
        "homepage_url": homepage,
        "collected_at": collected_at,
    }

    seeds: List[str] = list(dict.fromkeys(_default_sitemap_seeds(origin)))
    robots_url = urljoin(origin + "/", "robots.txt")
    robots_status, robots_final, robots_bytes, robots_err = await _http_get_content(
        client, robots_url, max_bytes=min(2_000_000, max_body)
    )

    inventory_docs: List[Dict[str, Any]] = []
    seen_sitemaps: Set[str] = set()
    page_candidates: List[str] = []
    child_fetches = 0
    doc_seq = 0
    total_loc_ndjson = 0
    ndjson_path: Optional[Path] = None
    writer_cm: Optional[_NdjsonWriter] = None
    writer: Optional[_NdjsonWriter] = None
    raw_dir: Optional[Path] = None
    j_base = persist.jurisdiction_base_dir if persist else Path(".")

    if do_persist and persist:
        assert persist.output_dir is not None
        persist.output_dir.mkdir(parents=True, exist_ok=True)
        raw_dir = persist.output_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        ndjson_path = persist.output_dir / "sitemap_rows.ndjson"
        writer_cm = _NdjsonWriter(ndjson_path, meta)
        writer_cm.__enter__()
        writer = writer_cm

    def next_doc_id() -> str:
        nonlocal doc_seq
        doc_seq += 1
        return f"sm_{doc_seq:04d}"

    def emit_document_row(
        *,
        doc_id: str,
        request_url: str,
        response_final_url: str,
        http_status: Optional[int],
        content_kind: str,
        storage_rel_path: Optional[str],
        byte_length: Optional[int],
        sha256_hex_val: Optional[str],
        xml_root_local_tag: Optional[str],
        is_sitemap_index: Optional[bool],
        parse_ok: Optional[bool],
        parse_error: Optional[str],
        sitemap_directive_urls: Optional[List[str]],
    ) -> None:
        if not writer:
            return
        writer.write(
            {
                "row_kind": "document",
                "sitemap_document_id": doc_id,
                "request_url": request_url,
                "response_final_url": response_final_url,
                "http_status": http_status,
                "content_kind": content_kind,
                "storage_rel_path": storage_rel_path,
                "byte_length": byte_length,
                "sha256_hex": sha256_hex_val,
                "xml_root_local_tag": xml_root_local_tag,
                "is_sitemap_index": is_sitemap_index,
                "parse_ok": parse_ok,
                "parse_error": parse_error,
                "sitemap_directive_urls": sitemap_directive_urls,
            }
        )

    def emit_loc_row(
        *,
        doc_id: str,
        loc_url: str,
        loc_role: str,
        meeting_candidate: bool,
        loc_index: int,
    ) -> None:
        nonlocal total_loc_ndjson
        if not writer:
            return
        if total_loc_ndjson >= max_total_loc_ndjson:
            return
        writer.write(
            {
                "row_kind": "loc",
                "sitemap_document_id": None,
                "parent_sitemap_document_id": doc_id,
                "request_url": None,
                "response_final_url": None,
                "http_status": None,
                "content_kind": None,
                "storage_rel_path": None,
                "byte_length": None,
                "sha256_hex": None,
                "xml_root_local_tag": None,
                "is_sitemap_index": None,
                "parse_ok": None,
                "parse_error": None,
                "sitemap_directive_urls": None,
                "loc_url": loc_url,
                "loc_role": loc_role,
                "meeting_candidate": meeting_candidate,
                "loc_index": loc_index,
            }
        )
        total_loc_ndjson += 1

    # --- robots.txt ---
    directives: List[str] = []
    robots_doc_id = next_doc_id()
    if robots_bytes is not None:
        try:
            text = robots_bytes.decode("utf-8", errors="replace")
            directives = _parse_robots_sitemap_directives(text)
        except Exception:
            directives = []
        st_rel: Optional[str] = None
        sh: Optional[str] = None
        blen = len(robots_bytes)
        if do_persist and raw_dir is not None:
            try:
                st_rel, sh = _write_raw_file(raw_dir, robots_doc_id, "robots_txt", robots_bytes)
            except OSError as exc:
                out.persist_errors.append(f"robots_write:{exc}")
        elif robots_bytes is not None:
            sh = _sha256_hex(robots_bytes)
        emit_document_row(
            doc_id=robots_doc_id,
            request_url=robots_url,
            response_final_url=robots_final,
            http_status=robots_status,
            content_kind="robots_txt",
            storage_rel_path=st_rel,
            byte_length=blen,
            sha256_hex_val=sh,
            xml_root_local_tag=None,
            is_sitemap_index=None,
            parse_ok=robots_err is None,
            parse_error=robots_err,
            sitemap_directive_urls=directives if directives else None,
        )
        inventory_docs.append(
            {
                "sitemap_document_id": robots_doc_id,
                "content_kind": "robots_txt",
                "request_url": robots_url,
                "response_final_url": robots_final,
                "http_status": robots_status,
                "storage_rel_path": st_rel,
                "byte_length": blen,
                "sha256_hex": sh,
                "parse_error": robots_err,
                "sitemap_directive_count": len(directives),
            }
        )
    else:
        emit_document_row(
            doc_id=robots_doc_id,
            request_url=robots_url,
            response_final_url=robots_final,
            http_status=robots_status,
            content_kind="robots_txt",
            storage_rel_path=None,
            byte_length=None,
            sha256_hex_val=None,
            xml_root_local_tag=None,
            is_sitemap_index=None,
            parse_ok=False,
            parse_error=robots_err or "no_body",
            sitemap_directive_urls=None,
        )
        inventory_docs.append(
            {
                "sitemap_document_id": robots_doc_id,
                "content_kind": "robots_txt",
                "request_url": robots_url,
                "response_final_url": robots_final,
                "http_status": robots_status,
                "storage_rel_path": None,
                "parse_error": robots_err or "no_body",
            }
        )

    seeds.extend(directives)
    seeds = list(dict.fromkeys(s for s in seeds if s.strip()))[:30]

    ndjson_doc_rows = 0
    ndjson_loc_rows = 0

    try:

        async def walk_sitemap(sitemap_url: str, depth: int) -> None:
            nonlocal child_fetches
            if depth > max_depth:
                return
            key = sitemap_url.split("#")[0].strip()
            if not key or key in seen_sitemaps:
                return
            seen_sitemaps.add(key)
            if depth > 0:
                child_fetches += 1
                if child_fetches > max_children:
                    return

            doc_id = next_doc_id()
            status, final_u, body_bytes, fetch_err = await _http_get_content(client, key, max_bytes=max_body)

            inv_summary: Dict[str, Any] = {
                "sitemap_document_id": doc_id,
                "content_kind": "sitemap_xml",
                "request_url": key,
                "response_final_url": final_u,
                "http_status": status,
                "depth": depth,
            }
            st_rel: Optional[str] = None
            sh: Optional[str] = None
            xml_root: Optional[str] = None
            is_index: Optional[bool] = None
            parse_ok: Optional[bool] = None
            parse_err: Optional[str] = fetch_err
            loc_count = 0
            meeting_count = 0
            loc_truncated = False

            if body_bytes is None:
                emit_document_row(
                    doc_id=doc_id,
                    request_url=key,
                    response_final_url=final_u,
                    http_status=status,
                    content_kind="sitemap_xml",
                    storage_rel_path=None,
                    byte_length=None,
                    sha256_hex_val=None,
                    xml_root_local_tag=None,
                    is_sitemap_index=None,
                    parse_ok=False,
                    parse_error=fetch_err or f"http_{status}",
                    sitemap_directive_urls=None,
                )
                inv_summary["parse_error"] = fetch_err or f"http_{status}"
                inventory_docs.append(inv_summary)
                return

            text = body_bytes.decode("utf-8", errors="replace")
            if not text.lstrip().startswith("<"):
                emit_document_row(
                    doc_id=doc_id,
                    request_url=key,
                    response_final_url=final_u,
                    http_status=status,
                    content_kind="sitemap_xml",
                    storage_rel_path=None,
                    byte_length=len(body_bytes),
                    sha256_hex_val=_sha256_hex(body_bytes),
                    xml_root_local_tag=None,
                    is_sitemap_index=None,
                    parse_ok=False,
                    parse_error="not_xml",
                    sitemap_directive_urls=None,
                )
                inv_summary["parse_error"] = "not_xml"
                inventory_docs.append(inv_summary)
                return

            if do_persist and raw_dir is not None:
                try:
                    st_rel, sh = _write_raw_file(raw_dir, doc_id, "sitemap_xml", body_bytes)
                except OSError as exc:
                    out.persist_errors.append(f"sitemap_write:{key}:{exc}")
                    sh = _sha256_hex(body_bytes)
            else:
                sh = _sha256_hex(body_bytes)

            try:
                root = ET.fromstring(text)
            except ET.ParseError as exc:
                parse_err = repr(exc)
                emit_document_row(
                    doc_id=doc_id,
                    request_url=key,
                    response_final_url=final_u,
                    http_status=status,
                    content_kind="sitemap_xml",
                    storage_rel_path=st_rel,
                    byte_length=len(body_bytes),
                    sha256_hex_val=sh,
                    xml_root_local_tag=None,
                    is_sitemap_index=None,
                    parse_ok=False,
                    parse_error=parse_err,
                    sitemap_directive_urls=None,
                )
                inv_summary["parse_error"] = parse_err
                inventory_docs.append(inv_summary)
                return

            xml_root = _local_tag(root.tag)
            is_index = _is_sitemap_index_root(root)
            parse_ok = True
            parse_err = None
            locs = _collect_loc_elements(root)
            loc_count = len(locs)

            if is_index:
                emit_document_row(
                    doc_id=doc_id,
                    request_url=key,
                    response_final_url=final_u,
                    http_status=status,
                    content_kind="sitemap_xml",
                    storage_rel_path=st_rel,
                    byte_length=len(body_bytes),
                    sha256_hex_val=sh,
                    xml_root_local_tag=xml_root,
                    is_sitemap_index=True,
                    parse_ok=True,
                    parse_error=None,
                    sitemap_directive_urls=None,
                )
                for i, child in enumerate(locs):
                    emit_loc_row(
                        doc_id=doc_id,
                        loc_url=child,
                        loc_role="child_sitemap",
                        meeting_candidate=False,
                        loc_index=i,
                    )
                if depth >= max_depth:
                    inv_summary.update(
                        {
                            "storage_rel_path": st_rel,
                            "byte_length": len(body_bytes),
                            "sha256_hex": sh,
                            "xml_root_local_tag": xml_root,
                            "is_sitemap_index": True,
                            "loc_count": loc_count,
                            "skipped_recursion_depth": True,
                        }
                    )
                    inventory_docs.append(inv_summary)
                    return
                for child in locs:
                    await walk_sitemap(child, depth + 1)
                inv_summary.update(
                    {
                        "storage_rel_path": st_rel,
                        "byte_length": len(body_bytes),
                        "sha256_hex": sh,
                        "xml_root_local_tag": xml_root,
                        "is_sitemap_index": True,
                        "loc_count": loc_count,
                    }
                )
                inventory_docs.append(inv_summary)
                return

            # urlset (or treated as leaf): document row first, then each <loc> up to caps
            meeting_count = sum(1 for loc in locs if _loc_passes_filters(loc, homepage))
            emit_document_row(
                doc_id=doc_id,
                request_url=key,
                response_final_url=final_u,
                http_status=status,
                content_kind="sitemap_xml",
                storage_rel_path=st_rel,
                byte_length=len(body_bytes),
                sha256_hex_val=sh,
                xml_root_local_tag=xml_root,
                is_sitemap_index=False,
                parse_ok=True,
                parse_error=None,
                sitemap_directive_urls=None,
            )
            emitted = 0
            for i, loc in enumerate(locs):
                if emitted >= max_locs_per_doc_ndjson or total_loc_ndjson >= max_total_loc_ndjson:
                    loc_truncated = True
                    break
                mc = _loc_passes_filters(loc, homepage)
                emit_loc_row(
                    doc_id=doc_id,
                    loc_url=loc,
                    loc_role="page",
                    meeting_candidate=mc,
                    loc_index=i,
                )
                emitted += 1
                if mc and len(page_candidates) < max_out:
                    page_candidates.append(loc)

            inv_summary.update(
                {
                    "storage_rel_path": st_rel,
                    "byte_length": len(body_bytes),
                    "sha256_hex": sh,
                    "xml_root_local_tag": xml_root,
                    "is_sitemap_index": False,
                    "loc_count": loc_count,
                    "meeting_candidate_loc_count": meeting_count,
                    "loc_ndjson_emitted": emitted,
                    "loc_ndjson_truncated": loc_truncated or emitted < loc_count,
                }
            )
            inventory_docs.append(inv_summary)

        for s in seeds:
            await walk_sitemap(s, 0)

    finally:
        if writer_cm:
            ndjson_doc_rows = writer_cm.document_rows
            ndjson_loc_rows = writer_cm.loc_rows
            writer_cm.__exit__(None, None, None)

    out.enqueue_urls = list(dict.fromkeys(page_candidates))

    if out.enqueue_urls:
        logger.info(
            "meetings_sitemap_candidates homepage={} sitemap_docs_fetched={} filtered_urls={}",
            origin,
            len(seen_sitemaps),
            len(out.enqueue_urls),
        )

    if do_persist and persist and ndjson_path is not None:
        inv_path = persist.output_dir / "sitemap_inventory.json"
        try:
            bundle = {
                "schema_version": SCHEMA_VERSION,
                "bundle_type": "meetings_sitemap_crawl",
                "jurisdiction_id": persist.jurisdiction_id,
                "state": persist.state,
                "geoid": persist.geoid,
                "jurisdiction_type": persist.jurisdiction_type,
                "homepage_url": homepage,
                "collected_at": collected_at,
                "storage": {
                    "raw_directory": _rel_under_jurisdiction(persist.output_dir / "raw", j_base)
                    if persist.output_dir
                    else "_sitemaps/raw",
                    "rows_ndjson": _rel_under_jurisdiction(ndjson_path, j_base),
                },
                "documents": inventory_docs,
                "meeting_candidate_urls_for_crawl": out.enqueue_urls,
                "summary": {
                    "sitemap_urls_visited": len(seen_sitemaps),
                    "inventory_documents": len(inventory_docs),
                    "ndjson_row_count": ndjson_doc_rows + ndjson_loc_rows,
                    "ndjson_document_rows": ndjson_doc_rows,
                    "ndjson_loc_rows": ndjson_loc_rows,
                    "total_loc_rows_emitted_cap": max_total_loc_ndjson,
                },
            }
            inv_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
            out.inventory_rel_path = _rel_under_jurisdiction(inv_path, j_base)
            out.ndjson_rel_path = _rel_under_jurisdiction(ndjson_path, j_base)
            out.documents_recorded = len(inventory_docs)
            out.ndjson_row_count = ndjson_doc_rows + ndjson_loc_rows
        except OSError as exc:
            out.persist_errors.append(f"inventory_write:{exc}")

    return out
