"""
Per-jurisdiction end-to-end pipeline: Gatekeeper → scope → organize → demos 1–4.

Used by ``02_run_meeting_llm.ipynb`` so each jurisdiction finishes before the next starts.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

import gatekeeper_triage
from colab_demos import DemoContext, JurisdictionDemoReports, run_demos_for_jurisdiction
from governance_meeting_llm import MeetingInventory, inventory_for_jurisdiction


def per_jurisdiction_e2e_enabled() -> bool:
    return os.environ.get("GOVERNANCE_PER_JURISDICTION_E2E", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def gatekeeper_enabled() -> bool:
    return os.environ.get("GOVERNANCE_GATEKEEPER_ENABLED", "1") != "0"


@dataclass
class JurisdictionRunContext:
    raw_root: Path
    pipe_root: Path
    api_key: str
    gatekeeper_model: str
    demo_ctx: DemoContext
    demo_date_cap: Optional[int] = None
    gatekeeper_max_files: Optional[int] = None
    organize_meetings: bool = True


def scope_inventory(
    inv: MeetingInventory,
    raw_root: Path,
    *,
    max_dates: Optional[int],
) -> MeetingInventory:
    """Apply DEMO date scope to one inventory."""
    if max_dates is None:
        return inv
    try:
        from meeting_date_scope import filter_inventory_media
    except ImportError:
        return inv
    inv.pdfs, inv.audio = filter_inventory_media(
        inv.pdfs, inv.audio, raw_root, inv.jurisdiction.root, max_dates=max_dates
    )
    return inv


def organize_inventory(raw_root: Path, inv: MeetingInventory) -> int:
    try:
        from meeting_grouping import organize_inventory_into_meeting_folders
    except ImportError:
        return 0
    moves = organize_inventory_into_meeting_folders(raw_root, [inv])
    return len(moves)


def reload_inventory(
    inv: MeetingInventory,
    raw_root: Path,
    *,
    max_dates: Optional[int],
) -> MeetingInventory:
    """Re-walk disk after Gatekeeper / organize moves."""
    fresh = inventory_for_jurisdiction(raw_root, inv.jurisdiction.root)
    if fresh is None:
        return inv
    return scope_inventory(fresh, raw_root, max_dates=max_dates)


def run_gatekeeper_for_jurisdiction(
    inv: MeetingInventory,
    ctx: JurisdictionRunContext,
    *,
    stamp: str,
    report_dir: Path,
    logs_dir: Path,
) -> Optional[gatekeeper_triage.TriageReport]:
    if not gatekeeper_enabled():
        print("  Gatekeeper skipped (GOVERNANCE_GATEKEEPER_ENABLED=0).")
        return None

    kinds = tuple(
        k.strip().lower()
        for k in os.environ.get("GOVERNANCE_GATEKEEPER_KINDS", "pdf,audio").split(",")
        if k.strip()
    )
    dry_run = os.environ.get("GOVERNANCE_GATEKEEPER_DRY_RUN", "0") == "1"
    jur_root = inv.jurisdiction.root
    label = inv.jurisdiction.relative_label

    total = gatekeeper_triage.count_triageable_files(
        ctx.raw_root, kinds=kinds, jurisdiction_root=jur_root
    )
    triage_paths, _n, allowed_dates, _years = gatekeeper_triage.select_triageable_files(
        ctx.raw_root,
        kinds=kinds,
        max_files=ctx.gatekeeper_max_files,
        jurisdiction_root=jur_root,
    )
    print(
        f"  Gatekeeper | {label} | candidates={total} | will_triage={len(triage_paths)}"
    )
    if allowed_dates and label in allowed_dates:
        print(f"    dates: {', '.join(sorted(allowed_dates[label]))}")

    log_path = report_dir / f"triage_{label.replace('/', '_')}_{stamp}.txt"
    mirror_log = logs_dir / f"gatekeeper_{label.replace('/', '_')}_{stamp}.log"
    gatekeeper_triage.configure_logging(
        verbose=True,
        log_path=log_path,
        mirror_log_path=mirror_log,
        console=True,
    )
    try:
        report = gatekeeper_triage.run_triage(
            raw_root=ctx.raw_root,
            api_key=ctx.api_key,
            model=ctx.gatekeeper_model,
            kinds=kinds,
            pdf_pages=int(os.environ.get("GOVERNANCE_GATEKEEPER_PDF_PAGES", "2")),
            pdf_dpi=int(os.environ.get("GOVERNANCE_GATEKEEPER_PDF_DPI", "120")),
            audio_window_seconds=int(
                os.environ.get("GOVERNANCE_GATEKEEPER_AUDIO_WINDOW", "120")
            ),
            confidence_threshold=float(
                os.environ.get("GOVERNANCE_GATEKEEPER_CONFIDENCE", "0.6")
            ),
            dry_run=dry_run,
            max_files=ctx.gatekeeper_max_files,
            preload_models=False,
            progress_stdout=True,
            log_path=log_path,
            flush_log_each_file=True,
            organize_meetings=ctx.organize_meetings
            and os.environ.get("GOVERNANCE_ORGANIZE_MEETINGS", "1") == "1",
            jurisdiction_root=jur_root,
        )
    finally:
        gatekeeper_triage.close_gatekeeper_logging()

    report_path = report_dir / f"triage_report_{label.replace('/', '_')}_{stamp}.json"
    report_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"  Gatekeeper done | keep={len(report.proceed)} exclude={len(report.excluded)} "
        f"errors={len(report.errors)} → {report_path.name}"
    )
    return report


def run_one_jurisdiction(
    inv: MeetingInventory,
    ctx: JurisdictionRunContext,
    *,
    idx: int,
    total: int,
    stamp: str,
    report_dir: Path,
    logs_dir: Path,
    brief_cache: dict[str, str],
) -> JurisdictionDemoReports:
    label = inv.jurisdiction.relative_label
    banner = f"{'=' * 72}\n  [{idx}/{total}] {label}\n{'=' * 72}"
    print(banner)

    run_gatekeeper_for_jurisdiction(inv, ctx, stamp=stamp, report_dir=report_dir, logs_dir=logs_dir)
    inv = reload_inventory(inv, ctx.raw_root, max_dates=ctx.demo_date_cap)
    if not inv.has_media:
        print(f"  No media left after Gatekeeper for {label}.")
        return JurisdictionDemoReports()

    if ctx.organize_meetings and os.environ.get("GOVERNANCE_ORGANIZE_MEETINGS", "1") == "1":
        n_moves = organize_inventory(ctx.raw_root, inv)
        if n_moves:
            print(f"  Organized {n_moves} file(s) into meetings/…")
            inv = reload_inventory(inv, ctx.raw_root, max_dates=ctx.demo_date_cap)

    print(
        f"  Demos | pdfs={len(inv.pdfs)} audio={len(inv.audio)} images={len(inv.images)}"
    )
    reports = run_demos_for_jurisdiction(inv, ctx.demo_ctx, brief_cache=brief_cache)
    print(f"\n  ✓ Finished {label} — outputs under {ctx.demo_ctx.processed_root.name}/")
    return reports


def run_per_jurisdiction_e2e(
    inventories: List[MeetingInventory],
    ctx: JurisdictionRunContext,
) -> List[JurisdictionDemoReports]:
    """Gatekeeper + organize + demos 1–4 for each jurisdiction in order."""
    if not inventories:
        print("No jurisdictions with media.")
        return []

    report_dir = ctx.pipe_root / "03_processed_outputs" / "_gatekeeper"
    report_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = ctx.pipe_root / "00_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    print(
        f"Per-jurisdiction E2E | {len(inventories)} jurisdiction(s) | "
        f"Gatekeeper → organize → demos 1–4"
    )

    all_reports: List[JurisdictionDemoReports] = []
    brief_cache: dict[str, str] = {}
    total = len(inventories)
    for idx, inv in enumerate(inventories, 1):
        all_reports.append(
            run_one_jurisdiction(
                inv,
                ctx,
                idx=idx,
                total=total,
                stamp=stamp,
                report_dir=report_dir,
                logs_dir=logs_dir,
                brief_cache=brief_cache,
            )
        )
    print(f"\n{'=' * 72}\nAll jurisdictions complete ({total}).\n{'=' * 72}")
    return all_reports
