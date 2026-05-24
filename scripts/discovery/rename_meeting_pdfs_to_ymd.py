#!/usr/bin/env python3
"""
Rename downloaded meeting PDFs to ``YYYY_MM_DD_<agenda|minutes>_<title-slug>.pdf``.

Operates over ``data/cache/scraped_meetings/{STATE}/{type}/{slug}_{geoid}/_manifest.json``,
reads the ``pdfs[]`` entries, and:

  1. Derives ``doc_kind`` ∈ {agenda, minutes, other} from anchor_text + URL +
     existing filename (keyword match).
  2. Derives ``YYYY_MM_DD`` from URL path segments, anchor text, or PDF metadata
     when present; falls back to the manifest's year + a "00_00" month/day stub
     when only the year is known.
  3. Renames each PDF to the new convention and updates the manifest's ``path``
     pointer.
  4. **Moves non-primary PDFs** (``doc_kind == "other"``) into a sibling
     ``_collateral/`` subdirectory so the year directory only contains the
     primary agendas + minutes.

Safe to run while meeting-download processes are still active — skips any file
modified within the last 60 seconds (treats as in-flight). Idempotent —
re-running on already-renamed files is a no-op.

Usage::

    .venv/bin/python -m scripts.discovery.rename_meeting_pdfs_to_ymd --dry-run
    .venv/bin/python -m scripts.discovery.rename_meeting_pdfs_to_ymd --states AL,GA
    .venv/bin/python -m scripts.discovery.rename_meeting_pdfs_to_ymd
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("rename_meeting_pdfs")

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data" / "cache" / "scraped_meetings"
DEFAULT_PRIORITY_STATES = ("AL", "GA", "IN", "MA", "WA", "WI")

# In-flight guard: skip files modified less than N seconds ago.
_IN_FLIGHT_SECONDS = 60

# Stop-word set used by the title slug — strip noise like "FINAL", page numbers,
# duplicate "-1200x110" image-resize tokens, etc.
_TITLE_NOISE_RE = re.compile(
    r"\b(?:final|draft|copy|approved|revised|updated|page\s*\d+|signed)\b",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------------------
# Heuristics — kind + date derivation
# --------------------------------------------------------------------------------------


_KIND_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("agenda",  re.compile(r"\bagendas?\b", re.IGNORECASE)),
    ("minutes", re.compile(r"\bminutes?\b", re.IGNORECASE)),
    ("minutes", re.compile(r"\bmtg[-_\s]*notes\b", re.IGNORECASE)),
    ("minutes", re.compile(r"\bmeeting[-_\s]*notes\b", re.IGNORECASE)),
)


def derive_kind(*text_sources: str) -> str:
    blob = " ".join(t or "" for t in text_sources)
    for kind, pat in _KIND_PATTERNS:
        if pat.search(blob):
            return kind
    return "other"


# Date patterns, ordered most specific to least.
_DATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # 2025-11-04, 2025_11_04, 2025/11/04, 2025.11.04
    re.compile(r"(?P<y>20\d{2})[-_/.](?P<m>0?[1-9]|1[0-2])[-_/.](?P<d>0?[1-9]|[12]\d|3[01])"),
    # 11-04-2025, 11_04_2025, 11/04/2025
    re.compile(r"(?P<m>0?[1-9]|1[0-2])[-_/.](?P<d>0?[1-9]|[12]\d|3[01])[-_/.](?P<y>20\d{2})"),
    # November 4, 2025  /  Nov 4 2025
    re.compile(
        r"(?P<mon>jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+"
        r"(?P<d>0?[1-9]|[12]\d|3[01]),?\s+(?P<y>20\d{2})",
        re.IGNORECASE,
    ),
    # 20251104
    re.compile(r"(?<!\d)(?P<y>20\d{2})(?P<m>0[1-9]|1[0-2])(?P<d>0[1-9]|[12]\d|3[01])(?!\d)"),
)

_MONTH_NAME_TO_NUM = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def derive_date(*text_sources: str) -> tuple[str, str, str] | None:
    """Return (yyyy, mm, dd) or None if no date can be confidently extracted."""
    blob = " ".join(t or "" for t in text_sources)
    for pat in _DATE_PATTERNS:
        m = pat.search(blob)
        if not m:
            continue
        gd = m.groupdict()
        if "mon" in gd:
            mm = _MONTH_NAME_TO_NUM.get((gd.get("mon") or "").lower()[:4]) \
                or _MONTH_NAME_TO_NUM.get((gd.get("mon") or "").lower()[:3])
            if not mm:
                continue
            return gd["y"], f"{mm:02d}", f"{int(gd['d']):02d}"
        try:
            return gd["y"], f"{int(gd['m']):02d}", f"{int(gd['d']):02d}"
        except (KeyError, ValueError):
            continue
    return None


def title_slug(*text_sources: str, max_len: int = 60) -> str:
    blob = " ".join(t or "" for t in text_sources).strip()
    blob = _TITLE_NOISE_RE.sub("", blob)
    # Drop everything that looks like a date so we don't double-stamp it
    blob = re.sub(
        r"\b(?:20\d{2}|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\w*\b[\s_/.-]*",
        "", blob, flags=re.IGNORECASE,
    )
    blob = re.sub(r"[^A-Za-z0-9]+", "_", blob).strip("_").lower()
    blob = re.sub(r"_+", "_", blob)
    if not blob:
        return "document"
    return blob[:max_len].rstrip("_")


# --------------------------------------------------------------------------------------
# Per-jurisdiction processing
# --------------------------------------------------------------------------------------


@dataclass
class JurisdictionStats:
    jurisdiction_dir: Path
    renamed_agenda: int = 0
    renamed_minutes: int = 0
    moved_to_collateral: int = 0
    skipped_in_flight: int = 0
    skipped_missing: int = 0
    skipped_already_named: int = 0
    skipped_no_date: int = 0
    errors: list[str] = field(default_factory=list)


_NEW_NAME_RE = re.compile(r"^(20\d{2})_(0[0-9]|1[0-2])_([0-3][0-9])_(agenda|minutes|other)_")


def _looks_already_renamed(name: str) -> bool:
    return bool(_NEW_NAME_RE.match(name))


def _unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    n = 2
    while True:
        cand = target.with_name(f"{stem}_{n}{suffix}")
        if not cand.exists():
            return cand
        n += 1


def process_jurisdiction(
    jurisdiction_dir: Path, *, dry_run: bool, now_ts: float,
) -> JurisdictionStats:
    stats = JurisdictionStats(jurisdiction_dir=jurisdiction_dir)
    manifest_path = jurisdiction_dir / "_manifest.json"
    if not manifest_path.exists():
        return stats
    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception as exc:
        stats.errors.append(f"manifest_load:{exc}")
        return stats
    pdfs = manifest.get("pdfs") or []
    if not isinstance(pdfs, list) or not pdfs:
        return stats

    changed = False
    for entry in pdfs:
        url = str(entry.get("url") or "")
        old_path_str = str(entry.get("path") or "")
        anchor = str(entry.get("anchor_text") or "")
        existing_kind = str(entry.get("doc_type") or "")
        if not old_path_str:
            continue
        old_path = Path(old_path_str)
        if not old_path.exists():
            stats.skipped_missing += 1
            continue
        try:
            mtime = old_path.stat().st_mtime
        except OSError:
            stats.skipped_missing += 1
            continue
        if now_ts - mtime < _IN_FLIGHT_SECONDS:
            stats.skipped_in_flight += 1
            continue
        if _looks_already_renamed(old_path.name):
            stats.skipped_already_named += 1
            continue

        kind = existing_kind if existing_kind in ("agenda", "minutes") else derive_kind(
            anchor, url, old_path.name,
        )

        date = derive_date(anchor, url, old_path.name)
        if date is None:
            # If we can't get a real date, leave the file alone (we don't want bogus stubs).
            stats.skipped_no_date += 1
            continue
        y, m, d = date

        ts = title_slug(anchor, old_path.stem)
        new_basename = f"{y}_{m}_{d}_{kind}_{ts}{old_path.suffix.lower()}"

        if kind == "other":
            # Move into _collateral/
            target_dir = old_path.parent / "_collateral"
        else:
            target_dir = old_path.parent

        target = _unique_path(target_dir / new_basename)

        if not dry_run:
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                old_path.rename(target)
            except OSError as exc:
                stats.errors.append(f"rename {old_path.name} -> {target}: {exc}")
                continue
            entry["path"] = str(target)
            entry["doc_type"] = kind
            entry["renamed_to_ymd_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            changed = True

        if kind == "agenda":
            stats.renamed_agenda += 1
        elif kind == "minutes":
            stats.renamed_minutes += 1
        else:
            stats.moved_to_collateral += 1

    if changed and not dry_run:
        try:
            manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
        except Exception as exc:
            stats.errors.append(f"manifest_write:{exc}")

    return stats


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------


def iter_jurisdiction_dirs(root: Path, states: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for st in states:
        state_dir = root / st
        if not state_dir.is_dir():
            continue
        for jtype_dir in state_dir.iterdir():
            if not jtype_dir.is_dir():
                continue
            for juris in jtype_dir.iterdir():
                if juris.is_dir() and (juris / "_manifest.json").exists():
                    out.append(juris)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--states", default=",".join(DEFAULT_PRIORITY_STATES))
    p.add_argument("--root", default=str(DEFAULT_ROOT))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    root = Path(args.root)
    states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip())
    jurisdictions = iter_jurisdiction_dirs(root, states)
    logger.info("Scanning %d jurisdiction dir(s) under %s", len(jurisdictions), root)

    now_ts = time.time()
    totals = {
        "agenda": 0, "minutes": 0, "collateral": 0,
        "in_flight": 0, "missing": 0, "already": 0, "no_date": 0, "errors": 0,
    }
    for juris in jurisdictions:
        s = process_jurisdiction(juris, dry_run=args.dry_run, now_ts=now_ts)
        totals["agenda"]    += s.renamed_agenda
        totals["minutes"]   += s.renamed_minutes
        totals["collateral"]+= s.moved_to_collateral
        totals["in_flight"] += s.skipped_in_flight
        totals["missing"]   += s.skipped_missing
        totals["already"]   += s.skipped_already_named
        totals["no_date"]   += s.skipped_no_date
        totals["errors"]    += len(s.errors)
        if s.errors:
            for e in s.errors[:3]:
                logger.warning("[%s] %s", juris.name, e)

    print()
    print(f"Jurisdictions scanned:      {len(jurisdictions)}")
    print(f"Agendas renamed:            {totals['agenda']}")
    print(f"Minutes renamed:            {totals['minutes']}")
    print(f"Moved to _collateral/:      {totals['collateral']}")
    print(f"Skipped (in-flight <60s):   {totals['in_flight']}")
    print(f"Skipped (already renamed):  {totals['already']}")
    print(f"Skipped (no date found):    {totals['no_date']}")
    print(f"Skipped (file missing):     {totals['missing']}")
    print(f"Errors:                     {totals['errors']}")
    print()
    if args.dry_run:
        print("DRY RUN — no files were renamed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
