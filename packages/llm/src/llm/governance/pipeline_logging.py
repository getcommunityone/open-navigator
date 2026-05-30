"""
Human-readable pipeline progress for Colab (what step runs on PDF vs video).

- ``GOVERNANCE_PIPELINE_VERBOSE=1`` (default) — plan + modality hints
- ``GOVERNANCE_PIPELINE_PROGRESS=1`` (default) — % complete + ETA lines
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from .colab_demos import DemoContext
    from .governance_meeting_llm import MeetingInventory

_ACTIVE_PROGRESS: Optional["PipelineProgress"] = None


def pipeline_verbose_enabled() -> bool:
    return os.environ.get("GOVERNANCE_PIPELINE_VERBOSE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def pipeline_progress_enabled() -> bool:
    return os.environ.get("GOVERNANCE_PIPELINE_PROGRESS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def format_duration(seconds: float) -> str:
    if seconds < 0 or seconds != seconds:  # NaN
        return "?"
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"


def _estimate_config() -> Dict[str, float]:
    return {
        "gatekeeper_rules": float(
            os.environ.get("GOVERNANCE_EST_SEC_GATEKEEPER_RULES", "5")
        ),
        "demo1_pdf": float(os.environ.get("GOVERNANCE_EST_SEC_DEMO1_PDF", "40")),
        "demo2_high": float(os.environ.get("GOVERNANCE_EST_SEC_DEMO2_HIGH_PAGE", "55")),
        "demo2_low": float(os.environ.get("GOVERNANCE_EST_SEC_DEMO2_LOW_PAGE", "28")),
        "demo3_pdf": float(os.environ.get("GOVERNANCE_EST_SEC_DEMO3_PDF", "240")),
        "demo4_chunk": float(os.environ.get("GOVERNANCE_EST_SEC_DEMO4_CHUNK", "150")),
        "demo4_drift": float(os.environ.get("GOVERNANCE_EST_SEC_DEMO4_DRIFT", "90")),
        "consolidated": float(os.environ.get("GOVERNANCE_EST_SEC_CONSOLIDATED", "15")),
        "inter_call": float(os.environ.get("GOVERNANCE_GENAI_INTER_CALL_DELAY_HIGH_SECONDS", "5")),
    }


def _rel_names(paths: List[Path], raw_root: Path, *, limit: int = 8) -> List[str]:
    out: List[str] = []
    for p in paths[:limit]:
        try:
            out.append(p.resolve().relative_to(raw_root.resolve()).as_posix())
        except ValueError:
            out.append(p.name)
    if len(paths) > limit:
        out.append(f"… +{len(paths) - limit} more")
    return out


def _pdf_page_count(pdf: Path, cap: int) -> int:
    try:
        import fitz

        with fitz.open(pdf) as doc:
            return min(len(doc), cap)
    except Exception:
        return cap


@dataclass
class WorkPlan:
    """Planned API work units for one jurisdiction (seconds = rough Gemma time)."""

    units: List[Tuple[str, float]] = field(default_factory=list)
    reuse_units: int = 0
    api_units: int = 0

    @property
    def total_seconds(self) -> float:
        return sum(w for _, w in self.units)

    @property
    def total_minutes(self) -> float:
        return self.total_seconds / 60.0


def build_work_plan(inv: "MeetingInventory", ctx: "DemoContext") -> WorkPlan:
    """Estimate remaining Gemma/API seconds from inventory + existing outputs."""
    try:
        from .pipeline_media_scope import get_active_media_scope

        mscope = get_active_media_scope()
    except ImportError:
        mscope = None
    from .colab_demos import pick_demo3_pdfs_for_inventory, select_demo4_media
    from .governance_meeting_llm import (
        TOKEN_BUDGET_HIGH,
        VIDEO_EXTS,
        demo2_page_output_complete,
        demo2_pdf_outputs_complete,
        demo3_thinking_json_complete,
        demo4_drift_output_complete,
        force_reprocess_outputs,
        mirror_output_path,
        policy_chunk_output_complete,
    )

    cfg = _estimate_config()
    force = force_reprocess_outputs()
    plan = WorkPlan()
    pdfs = (
        list(inv.pdfs[: ctx.max_pdfs_per_jur])
        if mscope is None or mscope.run_demo1 or mscope.run_demo2 or mscope.run_demo3
        else []
    )

    run_d1 = mscope is None or mscope.run_demo1
    run_d2 = mscope is None or mscope.run_demo2
    run_d3 = mscope is None or mscope.run_demo3
    run_d4 = mscope is None or mscope.run_demo4

    if run_d1:
        for pdf in pdfs:
            if not pdf.is_file():
                continue
            plan.units.append(("Demo 1 OCR (reuse/skipped)", 2.0 if not force else cfg["demo1_pdf"]))

    if run_d2:
        for pdf in pdfs:
            if not pdf.is_file():
                continue
            n_pages = _pdf_page_count(pdf, ctx.max_pages_per_pdf)
            per_pdf_dir = mirror_output_path(
                input_path=pdf,
                raw_root=ctx.raw_root,
                processed_root=ctx.gemma_json_root,
                suffix="",
            )
            if not force and demo2_pdf_outputs_complete(per_pdf_dir, expected_pages=n_pages):
                plan.units.append((f"Demo 2 {pdf.name} ({n_pages} pg, cached)", 1.0))
                plan.reuse_units += n_pages
                continue
            for i in range(n_pages):
                page_out = per_pdf_dir / f"page_{i + 1:03d}.json"
                if not force and demo2_page_output_complete(page_out):
                    plan.units.append((f"Demo 2 {pdf.name} p{i + 1} (cached)", 0.5))
                    plan.reuse_units += 1
                    continue
                budget_key = "demo2_high" if i == 0 or (n_pages > 4 and i >= n_pages - 2) else "demo2_low"
                if pdf.name.lower().find("minute") >= 0 and i >= 2:
                    budget_key = "demo2_high" if i % 3 == 2 else "demo2_low"
                sec = cfg[budget_key] + cfg["inter_call"]
                plan.units.append((f"Demo 2 {pdf.name} p{i + 1}", sec))
                plan.api_units += 1

    if run_d3:
        demo3_pdfs = pick_demo3_pdfs_for_inventory(
            pdfs, ctx.raw_root, max_per_meeting=2, max_total=ctx.max_pdfs_per_jur
        )
        for pdf in demo3_pdfs:
            if not pdf.is_file():
                continue
            json_out = mirror_output_path(
                input_path=pdf,
                raw_root=ctx.raw_root,
                processed_root=ctx.gemma_json_root,
                suffix=".thinking.json",
            )
            if not force and demo3_thinking_json_complete(json_out):
                plan.units.append((f"Demo 3 {pdf.name} (cached)", 2.0))
                plan.reuse_units += 1
            else:
                plan.units.append((f"Demo 3 {pdf.name}", cfg["demo3_pdf"]))
                plan.api_units += 1

    videos = (
        select_demo4_media(inv.audio, ctx.raw_root, max_files=ctx.max_audio_per_jur)
        if run_d4
        else []
    )
    for media in videos:
        if not media.is_file():
            continue
        per_dir = mirror_output_path(
            input_path=media,
            raw_root=ctx.raw_root,
            processed_root=ctx.gemma_json_root,
            suffix="",
        )
        n_chunks = min(ctx.max_audio_chunks, 2)
        drift_cached = (not force) and demo4_drift_output_complete(per_dir / "policy_drift.json")
        for idx in range(n_chunks):
            chunk_out = per_dir / f"chunk_{idx:03d}.json"
            if not force and policy_chunk_output_complete(chunk_out):
                plan.units.append((f"Demo 4 {media.name} chunk {idx} (cached)", 1.0))
                plan.reuse_units += 1
            else:
                plan.units.append((f"Demo 4 {media.name} chunk {idx}", cfg["demo4_chunk"]))
                plan.api_units += 1
        if not drift_cached:
            plan.units.append((f"Demo 4 drift {media.name}", cfg["demo4_drift"]))
            plan.api_units += 1

    plan.units.append(("Consolidated summaries", cfg["consolidated"]))
    return plan


@dataclass
class PipelineProgress:
    """Track weighted completion and print ETA."""

    label: str
    units: List[Tuple[str, float]]
    done_weight: float = 0.0
    index: int = 0
    t0: float = field(default_factory=time.perf_counter)

    @classmethod
    def from_plan(cls, label: str, plan: WorkPlan) -> "PipelineProgress":
        return cls(label=label, units=list(plan.units))

    @property
    def total_weight(self) -> float:
        return sum(w for _, w in self.units)

    def advance(
        self,
        desc: str,
        *,
        weight: Optional[float] = None,
        actual_seconds: Optional[float] = None,
    ) -> None:
        if not pipeline_progress_enabled():
            self.index += 1
            return
        planned = weight
        if planned is None and self.index < len(self.units):
            planned = self.units[self.index][1]
        if planned is None:
            planned = 1.0
        if actual_seconds is not None and actual_seconds > 0:
            # Blend actual into rolling estimate for ETA
            planned = max(planned, actual_seconds)
        self.done_weight += planned
        self.index += 1
        total = self.total_weight or planned
        pct = min(100.0, 100.0 * self.done_weight / total) if total else 100.0
        elapsed = time.perf_counter() - self.t0
        remaining_w = max(0.0, total - self.done_weight)
        eta_s = (remaining_w / self.done_weight * elapsed) if self.done_weight > 0 else remaining_w
        from .colab_timed_steps import log_line

        log_line(
            f"⏱ Progress [{self.label}]: {pct:.0f}% — {desc} — "
            f"elapsed {format_duration(elapsed)}, "
            f"ETA ~{format_duration(eta_s)} remaining",
        )

    def finish(self) -> None:
        if not pipeline_progress_enabled():
            return
        elapsed = time.perf_counter() - self.t0
        from .colab_timed_steps import log_line

        log_line(f"✓ Progress [{self.label}]: 100% — done in {format_duration(elapsed)}")


def set_pipeline_progress(progress: Optional[PipelineProgress]) -> None:
    global _ACTIVE_PROGRESS
    _ACTIVE_PROGRESS = progress


def get_pipeline_progress() -> Optional[PipelineProgress]:
    return _ACTIVE_PROGRESS


def progress_tick(
    desc: str,
    *,
    weight: Optional[float] = None,
    actual_seconds: Optional[float] = None,
) -> None:
    p = _ACTIVE_PROGRESS
    if p is not None:
        p.advance(desc, weight=weight, actual_seconds=actual_seconds)


def print_runtime_estimate(inv: "MeetingInventory", ctx: "DemoContext") -> WorkPlan:
    """Print estimated API time for this jurisdiction; return plan for progress tracker."""
    if not pipeline_verbose_enabled() and not pipeline_progress_enabled():
        return WorkPlan()
    plan = build_work_plan(inv, ctx)
    low = plan.total_seconds * 0.85
    high = plan.total_seconds * 1.35
    print("  ── Runtime estimate (this jurisdiction) ──", flush=True)
    print(
        f"  Planned API work: ~{plan.api_units} unit(s), "
        f"~{plan.reuse_units} cached/skipped",
        flush=True,
    )
    print(
        f"  Estimated Gemma time: ~{format_duration(low)} – {format_duration(high)} "
        f"(~{plan.total_minutes:.0f} min midpoint; 429 retries add more)",
        flush=True,
    )
    print(
        "  Heaviest steps: Demo 2 PDF pages, Demo 3 policy PDFs, Demo 4 recordings "
        "(video runs in Demo 4 only, after PDFs).",
        flush=True,
    )
    print("  ─────────────────────────────────────────", flush=True)
    return plan


def print_gatekeeper_mode_hint() -> None:
    """One line after Gatekeeper explaining rules-only vs API (no video frame scan)."""
    if not pipeline_verbose_enabled():
        return
    rules = os.environ.get("GOVERNANCE_GATEKEEPER_RULES_ONLY", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )
    cfg = _estimate_config()
    if rules:
        print(
            "  Gatekeeper mode: rules-only (filename/path/manifest) — "
            f"typically <{format_duration(cfg['gatekeeper_rules'])}; "
            "does not watch or transcribe video.",
            flush=True,
        )
    else:
        print(
            "  Gatekeeper mode: API triage (may read PDF pages / audio snippets).",
            flush=True,
        )


def print_demo_run_plan(inv: "MeetingInventory", raw_root: Path) -> None:
    """Print what Demos 1–4 will touch (PDF vs video) before the long Gemma calls."""
    if not pipeline_verbose_enabled():
        return
    from .governance_meeting_llm import VIDEO_EXTS, format_inventory_media_line

    try:
        from .pipeline_media_scope import get_active_media_scope

        mscope = get_active_media_scope()
        print(f"  Media scope: {mscope.key!r} — {mscope.label}", flush=True)
    except ImportError:
        mscope = None

    pdfs = list(inv.pdfs) if mscope is None or mscope.run_demo1 or mscope.run_demo2 or mscope.run_demo3 else []
    videos = [p for p in inv.audio if p.suffix.lower() in VIDEO_EXTS]
    audio_only = [p for p in inv.audio if p.suffix.lower() not in VIDEO_EXTS]

    run_d4 = mscope is None or mscope.run_demo4
    print("  ── Pipeline plan (this jurisdiction) ──", flush=True)
    print(f"  Inventory: {format_inventory_media_line(inv)}", flush=True)
    if mscope is None or mscope.run_demo1:
        print(
            "  Demo 1 — PDF visual OCR (scanned pages only; digital text skipped)",
            flush=True,
        )
        for line in _rel_names(pdfs, raw_root):
            print(f"      • {line}", flush=True)
    if mscope is None or mscope.run_demo2:
        print(
            "  Demo 2 — PDF per-page token budget (HIGH/LOW images to Gemma) — not video",
            flush=True,
        )
    if mscope is None or mscope.run_demo3:
        print(
            "  Demo 3 — full policy_analysis on agenda/minutes PDFs (thinking model)",
            flush=True,
        )
    if run_d4:
        print(
            "  Demo 4 — meeting recordings (ffmpeg → chunks → Gemma):",
            flush=True,
        )
        if videos:
            for line in _rel_names(videos, raw_root):
                print(f"      • {line}", flush=True)
        if audio_only:
            print("  Also audio files:", flush=True)
            for line in _rel_names(audio_only, raw_root):
                print(f"      • {line}", flush=True)
        if not videos and not audio_only:
            print("      (no video/audio in scoped inventory — Demo 4 will skip)", flush=True)
    print(
        "  Then: consolidated _meeting_summary.md per session under meetings/…/session/",
        flush=True,
    )
    print("  ─────────────────────────────────────", flush=True)
