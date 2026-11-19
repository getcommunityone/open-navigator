"""Collect GEOIDs whose scraped-meetings manifests qualify for a retry crawl (#401).

Folder layouts under ``{scraped_root}/{state}/{jtype}/``:

* Legacy: ``{jtype}_{geoid}/_manifest.json`` (e.g. ``county/county_01001``)
* Current: ``{jurisdiction_id}/_manifest.json`` (e.g. ``municipality/tuscaloosa_0177256``)

The GEOID comes from the manifest's ``jurisdiction_id`` via
:func:`core_lib.jurisdictions.jurisdiction_id.parse_jurisdiction_id`, with a
folder-name fallback for unreadable / missing ids.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple

from core_lib.jurisdictions.jurisdiction_id import parse_jurisdiction_id

_FS_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")

# Jurisdiction-type folder names the crawl writes under ``{state}/``.
KNOWN_JURISDICTION_TYPES: Tuple[str, ...] = (
    "county",
    "municipality",
    "township",
    "school",
    "school_district",
)


def fs_safe_segment(s: str) -> str:
    return _FS_SAFE_RE.sub("_", (s or "").strip())[:200] or "unknown"


def manifest_page_count(path: Path) -> int:
    """Return ``len(pages_fetched)``, or ``-1`` if the manifest is unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return len(data.get("pages_fetched") or [])
    except Exception:
        return -1


def _geoid_from_manifest(path: Path) -> Optional[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    jid = (data.get("jurisdiction_id") or "").strip()
    if not jid:
        return None
    _jt, geoid, _slug = parse_jurisdiction_id(jid)
    return geoid or None


def _geoid_from_folder(folder_name: str, jtype: str) -> Optional[str]:
    name = (folder_name or "").strip()
    if not name:
        return None
    prefix = f"{jtype}_"
    if name.startswith(prefix) and len(name) > len(prefix):
        # Legacy ``county_01001`` — remaining segment is the GEOID.
        return name[len(prefix) :]
    _jt, geoid, _slug = parse_jurisdiction_id(name)
    return geoid or None


def discover_scraped_jurisdiction_types(scraped_root: Path, state: str) -> List[str]:
    """Concrete ``jtype`` folders under ``{scraped_root}/{state}/`` that look crawlable."""
    st = fs_safe_segment((state or "").strip().upper())
    base = scraped_root / st
    if not base.is_dir():
        return []
    found: List[str] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        name = child.name.strip().lower()
        if name in KNOWN_JURISDICTION_TYPES or name.startswith("school"):
            found.append(child.name)
    return found


def collect_retry_geoids_from_scraped_manifests(
    *,
    state: str,
    jtype: str,
    scraped_root: Path,
    shallow_max_pages: int,
    retry_modes: Set[str],
) -> List[str]:
    """
    GEOIDs whose manifest under ``scraped_root`` qualifies for retry: **failed**
    (0 HTML pages fetched) or **shallow** (``1 <= pages < shallow_max_pages``).

    Unreadable or missing manifests are skipped. Requires a concrete ``jtype``
    (not ``all``); callers that want every type loop with
    :func:`discover_scraped_jurisdiction_types`.
    """
    st = (state or "").strip().upper()
    jt = (jtype or "").strip().lower()
    if not jt or jt == "all":
        raise ValueError(
            "collect_retry_geoids_from_scraped_manifests requires a concrete jtype "
            "(e.g. county); use discover_scraped_jurisdiction_types for --type all"
        )
    cap = max(2, int(shallow_max_pages))
    base = scraped_root / fs_safe_segment(st) / fs_safe_segment(jt)
    found: Set[str] = set()
    if not base.is_dir():
        return []

    # One level: ``{folder}/_manifest.json`` (legacy type_geoid and current jid).
    for mf in sorted(base.glob("*/_manifest.json")):
        n = manifest_page_count(mf)
        if n < 0:
            continue
        geoid = _geoid_from_manifest(mf) or _geoid_from_folder(mf.parent.name, jt)
        if not geoid:
            continue
        if "failed" in retry_modes and n == 0:
            found.add(geoid)
        if "shallow" in retry_modes and 0 < n < cap:
            found.add(geoid)

    def _sort_key(g: str) -> Tuple[int, Any]:
        return (0, int(g)) if g.isdigit() else (1, g)

    return sorted(found, key=_sort_key)
