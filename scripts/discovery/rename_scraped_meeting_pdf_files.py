#!/usr/bin/env python3
"""
Rename downloaded meeting PDFs to readable snake_case names (meeting date + title), move each PDF
into the ``{calendar_year}/`` folder that matches the meeting date (or URL fallback), update
``pdfs[].path`` / ``pdfs[].year`` inside each ``_manifest.json``, and by default remove leftover
``filedownload_<sha256(url)[:14]>.pdf`` copies once the manifest already points at the canonical file.

Uses the same logic as live scraping (:mod:`scripts.discovery.meeting_document_naming`).

Examples::

    .venv/bin/python scripts/discovery/rename_scraped_meeting_pdf_files.py --dry-run
    .venv/bin/python scripts/discovery/rename_scraped_meeting_pdf_files.py --state AL
    .venv/bin/python scripts/discovery/rename_scraped_meeting_pdf_files.py --state AL \\
        --jurisdiction-id municipality_0177256 --calendar-year 2026 \\
        --backfill-manifest-from-crawl-html
    .venv/bin/python scripts/discovery/rename_scraped_meeting_pdf_files.py --no-cleanup-legacy-hash-pdfs
    SCRAPED_MEETINGS_ROOT=/mnt/g/cache .venv/bin/python scripts/discovery/rename_scraped_meeting_pdf_files.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.discovery.meeting_document_naming import (
    allocate_unique_pdf_path,
    infer_year_hint_from_url,
    legacy_sha14_pdf_candidate,
    pick_meeting_date,
)
from scripts.discovery.scraped_meetings_crawl_html_pdfs import build_pdf_rows_from_disk_and_crawl_html
from scripts.utils.gdrive_paths import resolve_scraped_meetings_output_root


def _iter_manifests(
    cache_root: Path,
    state: Optional[str],
    *,
    jurisdiction_id: Optional[str] = None,
) -> List[Path]:
    cache_root = cache_root.expanduser().resolve()
    if jurisdiction_id:
        jid = jurisdiction_id.strip()
        if state:
            cand = cache_root / state.strip().upper()
            if cand.is_dir():
                hits = sorted(cand.rglob(f"*/{jid}/_manifest.json"))
                if hits:
                    return hits
        hits = sorted(cache_root.rglob(f"*/{jid}/_manifest.json"))
        return hits
    if state:
        sub = cache_root / state.strip().upper()
        if not sub.is_dir():
            return []
        return sorted(sub.rglob("_manifest.json"))
    return sorted(cache_root.rglob("_manifest.json"))


def _backfill_manifest_pdfs_from_crawl_html(
    manifest_path: Path,
    *,
    calendar_year_dirs: Optional[List[str]],
    dry_run: bool,
) -> int:
    """Populate empty ``pdfs[]`` from ``_crawl_html`` + on-disk hash filenames; return rows added."""
    base = manifest_path.parent.resolve()
    crawl_html = base / "_crawl_html"
    if not crawl_html.is_dir():
        return 0

    try:
        data: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0

    existing = data.get("pdfs")
    if isinstance(existing, list) and existing:
        return 0

    seed = [str(u) for u in data.get("pages_fetched") or [] if isinstance(u, str)]
    rows = build_pdf_rows_from_disk_and_crawl_html(
        base,
        calendar_year_dirs=calendar_year_dirs,
        seed_urls=seed,
    )
    if not rows:
        return 0

    if dry_run:
        print(f"{manifest_path}: Would backfill {len(rows)} pdf row(s) from _crawl_html")
        return len(rows)

    data["pdfs"] = rows
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"{manifest_path}: Backfilled {len(rows)} pdf row(s) from _crawl_html")
    return len(rows)


_LEGACY_HASH_NAME = re.compile(r"^filedownload_([a-f0-9]{14})\.pdf$", re.I)


def _cleanup_superseded_legacy_hash_pdfs(
    manifest_path: Path,
    *,
    dry_run: bool,
    delete_unmapped: bool,
) -> Tuple[int, int, int]:
    """
    Drop ``filedownload_<sha256(url)[:14]>.pdf`` left on disk after the manifest ``path`` moved
    to a human-readable filename for the **same** ``url``.

    Returns ``(deleted_or_would_delete, unmapped_files, unmapped_deleted_or_would)``.
    """
    base = manifest_path.parent.resolve()
    try:
        data: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0, 0, 0

    pdfs = data.get("pdfs")
    if not isinstance(pdfs, list) or not pdfs:
        return 0, 0, 0

    canon_for_h14: Dict[str, Path] = {}
    for r in pdfs:
        if not isinstance(r, dict):
            continue
        u = str(r.get("url") or "").strip()
        ps = str(r.get("path") or "").strip()
        if not u or not ps:
            continue
        h14 = hashlib.sha256(u.encode("utf-8", errors="replace")).hexdigest()[:14]
        try:
            canon_for_h14[h14] = Path(ps).expanduser().resolve()
        except OSError:
            continue

    n_done = 0
    n_unmapped = 0
    n_unmapped_done = 0

    for p in sorted(base.rglob("*.pdf")):
        m = _LEGACY_HASH_NAME.match(p.name)
        if not m:
            continue
        h14 = m.group(1).lower()

        canon = canon_for_h14.get(h14)
        if canon is None:
            n_unmapped += 1
            if delete_unmapped and p.is_file():
                rel = p.relative_to(base)
                if dry_run:
                    print(f"{manifest_path}: Would delete unmapped legacy hash {rel}")
                    n_unmapped_done += 1
                else:
                    try:
                        p.unlink()
                        print(f"{manifest_path}: Deleted unmapped legacy hash {rel}")
                        n_unmapped_done += 1
                    except OSError as exc:
                        print(f"{manifest_path}: unlink failed {rel}: {exc}", file=sys.stderr)
            continue

        if not p.is_file():
            continue
        try:
            pr = p.resolve()
            cr = canon.resolve()
        except OSError:
            continue

        if pr == cr:
            continue
        if not canon.is_file():
            continue

        rel = p.relative_to(base)
        try:
            cr_rel = canon.relative_to(base)
        except ValueError:
            cr_rel = canon

        if dry_run:
            print(f"{manifest_path}: Would delete superseded legacy hash {rel} (canonical {cr_rel})")
            n_done += 1
            continue

        try:
            p.unlink()
            print(f"{manifest_path}: Deleted superseded legacy hash {rel}")
            n_done += 1
        except OSError as exc:
            print(f"{manifest_path}: unlink failed {rel}: {exc}", file=sys.stderr)

    return n_done, n_unmapped, n_unmapped_done


def _process_manifest(
    manifest_path: Path,
    *,
    dry_run: bool,
    manifest_data: Optional[Dict[str, Any]] = None,
) -> int:
    if manifest_data is not None:
        data = manifest_data
    else:
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0

    pdfs = data.get("pdfs")
    if not isinstance(pdfs, list) or not pdfs:
        return 0

    changed = False
    n_renamed = 0
    rows = [r for r in pdfs if isinstance(r, dict)]
    rows.sort(key=lambda r: str(r.get("url") or ""))

    reserved: Set[str] = set()
    reserved_paths: Set[str] = set()
    base = manifest_path.parent.resolve()

    for row in rows:
        url = str(row.get("url") or "").strip()
        path_str = str(row.get("path") or "").strip()
        if not url or not path_str:
            continue

        anchor = str(row.get("anchor_text") or "")
        doc_type = str(row.get("doc_type") or "")
        row_year_s = str(row.get("year") or "").strip()

        declared = Path(path_str).expanduser()
        try:
            declared = declared.resolve()
        except OSError:
            continue

        lookup_dir = declared.parent
        if not lookup_dir.is_dir():
            continue

        old_path = declared
        if not old_path.is_file():
            leg = legacy_sha14_pdf_candidate(lookup_dir, url)
            if leg is None:
                continue
            old_path = leg

        parent_guess = old_path.parent.name
        fb_year = (
            int(parent_guess)
            if parent_guess.isdigit() and len(parent_guess) == 4
            else (
                int(row_year_s)
                if row_year_s.isdigit() and len(row_year_s) == 4
                else datetime.now(timezone.utc).year
            )
        )

        d_pick, _ = pick_meeting_date(url=url, anchor=anchor, doc_type=doc_type or None)
        if d_pick:
            dest_year_s = str(d_pick.year)
        else:
            iso_m = re.match(r"^(\d{4})-\d{2}-\d{2}_", old_path.name)
            if iso_m:
                dest_year_s = iso_m.group(1)
            else:
                dest_year_s = str(infer_year_hint_from_url(url, fb_year))

        dest_dir = (base / dest_year_s).resolve()

        target = allocate_unique_pdf_path(
            dest_dir,
            url,
            anchor,
            doc_type,
            year_fallback=dest_year_s,
            reserved_basenames=reserved,
            reserved_paths=reserved_paths,
            ignore_existing_path=old_path,
        ).resolve()

        try:
            tgt_key = str(target.resolve())
        except OSError:
            tgt_key = str(target)

        if target == old_path:
            if row.get("year") != dest_year_s:
                if not dry_run:
                    row["year"] = dest_year_s
                    changed = True
            reserved.add(target.name)
            reserved_paths.add(tgt_key)
            continue

        if dry_run:
            try:
                old_rel = old_path.relative_to(base)
            except ValueError:
                old_rel = old_path.name
            try:
                new_rel = target.relative_to(base)
            except ValueError:
                new_rel = Path(dest_year_s) / target.name
            print(f"{manifest_path}: {old_rel} -> {new_rel}")
            reserved.add(target.name)
            reserved_paths.add(tgt_key)
            n_renamed += 1
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)
        old_path.rename(target)
        row["path"] = str(target)
        row["year"] = dest_year_s
        if not row.get("prior_disk_name"):
            row["prior_disk_name"] = old_path.name
        reserved.add(target.name)
        reserved_paths.add(tgt_key)
        changed = True
        n_renamed += 1

    if changed and not dry_run:
        manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return n_renamed


def main() -> None:
    ap = argparse.ArgumentParser(description="Rename cached meeting PDFs to date_snake_title.pdf names.")
    ap.add_argument(
        "--cache-root",
        default="",
        help="Scrape root (default: SCRAPED_MEETINGS_ROOT or repo data/cache/scraped_meetings)",
    )
    ap.add_argument("--state", default="", help="Only manifests under this USPS state folder (e.g. AL)")
    ap.add_argument(
        "--jurisdiction-id",
        default="",
        help="Only this jurisdiction folder (e.g. municipality_0177256); use with --state for faster lookup",
    )
    ap.add_argument(
        "--calendar-year",
        action="append",
        default=[],
        metavar="YYYY",
        help="Limit disk scan / backfill to these calendar-year subfolders (repeatable)",
    )
    ap.add_argument(
        "--backfill-manifest-from-crawl-html",
        action="store_true",
        help="When pdfs[] is empty, rebuild rows from _crawl_html SuiteOne tables + URL hash filenames",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print planned renames without touching disk")
    ap.add_argument(
        "--no-cleanup-legacy-hash-pdfs",
        action="store_true",
        help="Keep filedownload_<sha14>.pdf files even when the manifest already references another path for that URL.",
    )
    ap.add_argument(
        "--delete-unmapped-legacy-hash-pdfs",
        action="store_true",
        help="Also delete legacy hash PDFs whose URL no longer appears in the manifest (only use when sure they are stale).",
    )
    args = ap.parse_args()

    root = (
        Path(args.cache_root).expanduser().resolve()
        if args.cache_root.strip()
        else resolve_scraped_meetings_output_root().resolve()
    )
    st = args.state.strip().upper() if args.state.strip() else None
    jid = args.jurisdiction_id.strip() or None
    year_dirs = [y.strip() for y in args.calendar_year if y.strip()] or None
    manifests = _iter_manifests(root, st, jurisdiction_id=jid)
    total = 0
    cleaned = 0
    unmapped = 0
    unmapped_deleted = 0
    for mf in manifests:
        manifest_data: Optional[Dict[str, Any]] = None
        if args.backfill_manifest_from_crawl_html:
            if args.dry_run:
                try:
                    manifest_data = json.loads(mf.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    manifest_data = None
                if manifest_data is not None and not (manifest_data.get("pdfs") or []):
                    base = mf.parent.resolve()
                    seed = [
                        str(u) for u in manifest_data.get("pages_fetched") or [] if isinstance(u, str)
                    ]
                    rows = build_pdf_rows_from_disk_and_crawl_html(
                        base,
                        calendar_year_dirs=year_dirs,
                        seed_urls=seed,
                    )
                    if rows:
                        print(f"{mf}: Would backfill {len(rows)} pdf row(s) from _crawl_html")
                        manifest_data = {**manifest_data, "pdfs": rows}
            else:
                _backfill_manifest_pdfs_from_crawl_html(
                    mf,
                    calendar_year_dirs=year_dirs,
                    dry_run=False,
                )
        total += _process_manifest(
            mf, dry_run=args.dry_run, manifest_data=manifest_data
        )
        if not args.no_cleanup_legacy_hash_pdfs:
            d, u, ud = _cleanup_superseded_legacy_hash_pdfs(
                mf,
                dry_run=args.dry_run,
                delete_unmapped=args.delete_unmapped_legacy_hash_pdfs,
            )
            cleaned += d
            unmapped += u
            unmapped_deleted += ud

    action = "Would rename" if args.dry_run else "Renamed"
    print(f"{action} {total} pdf(s) across {len(manifests)} manifest(s) under {root}")
    if not args.no_cleanup_legacy_hash_pdfs:
        cact = "Would remove" if args.dry_run else "Removed"
        print(f"{cact} {cleaned} superseded legacy-hash pdf(s)")
        if unmapped:
            note = (
                f"{unmapped} legacy-hash pdf(s) had no manifest URL match "
                "(omit --delete-unmapped-legacy-hash-pdfs to leave them)."
            )
            print(note)
        if args.delete_unmapped_legacy_hash_pdfs:
            uact = "Would remove" if args.dry_run else "Removed"
            print(f"{uact} {unmapped_deleted} unmapped legacy-hash pdf(s)")


if __name__ == "__main__":
    main()
