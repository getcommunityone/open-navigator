"""
Notebook demos 1–4 extracted for per-jurisdiction end-to-end runs.

Imported by ``jurisdiction_pipeline`` and optionally by ``02_run_meeting_llm.ipynb``.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from media_playback_links import (
    enrich_policy_analysis_media_links,
    format_media_context_hint,
    list_media_sources,
    resolve_media_for_input_file,
)
from colab_timed_steps import format_elapsed, format_file_size, log_line, log_phase, timed_step
from genai_quota_retry import (
    call_with_wall_clock_timeout,
    demo3_api_timeout_seconds,
    genai_inter_call_pause,
)
from pipeline_logging import (
    PipelineProgress,
    build_work_plan,
    progress_tick,
    set_pipeline_progress,
)

try:
    from pipeline_media_scope import (
        demo4_step_label,
        describe_demo4_file,
        get_active_media_scope,
    )
except ImportError:

    def get_active_media_scope():  # type: ignore[misc]
        class _All:
            key = "all"
            label = "all"
            run_demo1 = run_demo2 = run_demo3 = run_demo4 = True

        return _All()

    def demo4_step_label(scope=None):  # type: ignore[misc]
        return "Demo 4 meeting recordings"

    def describe_demo4_file(path, *, demo4_model):  # type: ignore[misc]
        return "15‑min slices → Gemma"
from governance_meeting_llm import (
    TOKEN_BUDGET_HIGH,
    TOKEN_BUDGET_LOW,
    TOKEN_BUDGET_MEDIUM,
    VIDEO_EXTS,
    MeetingInventory,
    call_google_genai_multimodal,
    discover_demo4_chunk_media,
    iter_demo4_ingest_strategies,
    demo2_page_output_complete,
    demo2_pdf_outputs_complete,
    demo3_thinking_json_complete,
    demo4_drift_output_complete,
    extract_pdf_digital_text,
    demo3_input_mode,
    demo3_min_digital_chars,
    demo3_text_first_enabled,
    demo1_skip_when_digital,
    demo2_skip_when_digital,
    is_scanned_pdf,
    truncate_demo3_document_text,
    demo4_use_video_chunks,
    find_existing_demo4_chunks,
    force_reprocess_outputs,
    mime_for,
    mirror_output_path,
    parse_policy_analysis_response,
    policy_chunk_output_complete,
    policy_drift_summarize,
    read_json_file,
    render_pdf_pages,
    demo4_media_work_dir,
    demo4_uses_huggingface,
    resolve_demo4_model,
    select_demo4_media,
    demo4_models_to_try,
    is_audio_modality_rejected,
    model_supports_audio_video_input,
    model_supports_video_input,
    text_output_complete,
)


@dataclass
class DemoContext:
    api_key: str
    genai_model: str
    raw_root: Path
    processed_root: Path
    gemma_json_root: Path
    summaries_root: Path
    scratch_audio_root: Path
    policy_prompt: str
    thinking_model: str = ""
    demo4_model: str = ""
    gatekeeper_model: str = ""
    max_pdfs_per_jur: int = 3
    max_pages_per_pdf: int = 8
    max_audio_per_jur: int = 1
    max_audio_chunks: int = 4
    thinking_budget: int = -1
    drift_focus: Optional[str] = None


DEMO1_SYSTEM = (
    "You are a careful document transcription engine. Faithfully transcribe every "
    "word and number on each page of the attached PDF in reading order. Preserve "
    "table structure with vertical bars and dashes. Do not paraphrase, summarize, "
    "or invent content."
)
DEMO1_USER = (
    "Transcribe the attached PDF page by page. Begin each page with a heading line "
    "'### Page <n>' on its own line. If a page is blank, write '(blank page)'."
)

DEMO2_SYSTEM = (
    "You are a careful page-level extractor. Return JSON only — no markdown fences."
)
DEMO2_USER_HIGH = (
    "This page contains tabular or financial content (bids, contract awards, "
    "ledgers, line-item budgets). Preserve column alignment and every dollar "
    "amount. Return JSON with this shape: "
    '{"page_type":"financial_or_tabular","raw_text":"...","line_items":[{"label":"...","amount":"..."}],"notes":"..."}'
)
DEMO2_USER_LOW = (
    "This page is standard meeting minutes text. Return JSON with this shape: "
    '{"page_type":"text_heavy","raw_text":"...","headline":"...","notes":"..."}'
)
DEMO2_USER_SCANNED = (
    "This page is a scanned image with no digital text. Visually OCR it. "
    "Return JSON with this shape: "
    '{"page_type":"scanned","raw_text":"...","notes":"..."}'
)
DEMO2_USER_BY_CLASS = {
    "financial_or_tabular": DEMO2_USER_HIGH,
    "text_heavy": DEMO2_USER_LOW,
    "scanned": DEMO2_USER_SCANNED,
}

DEMO3_SYSTEM = (
    "You are an expert political scientist and data architect specializing in "
    "local governance. Follow the user's instructions exactly. Document 1 must be "
    "raw JSON starting with `{` (no markdown fences, no markdown-only reply). "
    "COFOG codes belong on each decision via primary_theme_cofog / secondary_theme_cofog. "
    "When MEDIA CONTEXT lists recordings, populate meeting.media_sources and per-decision "
    "media_citation timestamps (elapsed from recording start)."
)

_PRIORITY_PATTERNS = (
    "demolition",
    "demolitions",
    "nuisance",
    "minutes",
    "regular_session",
    "regular-session",
    "regular session",
    "council",
    "commission",
    "board",
    "hearing",
)

DEMO4_SYSTEM = (
    "You are an expert political scientist analyzing one chunk of a long meeting. "
    "Follow the user's instructions exactly. Document 1 must be raw JSON starting with "
    "`{` (no markdown fences, no markdown-only reply). COFOG codes belong on each "
    "decision. Use MEDIA CONTEXT for recording URLs; timestamp decisions from the full "
    "recording start (add chunk_start_seconds). The chunk_index tells you which "
    "15-minute slice you are hearing."
)


def pick_representative_pdf(pdfs: List[Path]) -> Optional[Path]:
    if not pdfs:
        return None
    scored = []
    for p in pdfs:
        name = p.name.lower()
        score = 0
        for tag in _PRIORITY_PATTERNS:
            if tag in name:
                score += 5
        try:
            score += min(p.stat().st_size // 50_000, 50)
        except OSError:
            pass
        scored.append((score, p))
    scored.sort(key=lambda t: (-t[0], t[1].name))
    return scored[0][1]


def pick_demo3_pdfs(pdfs: List[Path], *, max_pdfs: int = 2) -> List[Path]:
    """Prefer agenda then minutes (legacy: jurisdiction-wide cap only)."""
    import os

    cap = max(1, int(os.environ.get("GOVERNANCE_DEMO3_MAX_PDFS", str(max_pdfs))))
    if not pdfs:
        return []
    agenda = [p for p in pdfs if "agenda" in p.name.lower()]
    minutes = [p for p in pdfs if "minute" in p.name.lower() and p not in agenda]
    rest = [p for p in pdfs if p not in agenda and p not in minutes]
    ordered: List[Path] = []
    for group in (agenda, minutes, sorted(rest, key=lambda x: x.name)):
        for p in group:
            if p not in ordered:
                ordered.append(p)
            if len(ordered) >= cap:
                return ordered
    if ordered:
        return ordered
    one = pick_representative_pdf(pdfs)
    return [one] if one else []


def pick_demo3_pdfs_for_inventory(
    pdfs: List[Path],
    raw_root: Path,
    *,
    max_per_meeting: int = 2,
    max_total: Optional[int] = None,
) -> List[Path]:
    """
    Pick agenda + minutes **per meeting session**, not only N PDFs for the whole jurisdiction.

    ``GOVERNANCE_DEMO3_MAX_PDFS_PER_MEETING`` (default 2) × each session under
    ``meetings/``; optional jurisdiction cap via ``max_total`` / ``GOVERNANCE_DEMO3_MAX_PDFS_TOTAL``.
    """
    import os
    from collections import defaultdict

    if not pdfs:
        return []

    per_meeting = max(
        1,
        int(
            os.environ.get(
                "GOVERNANCE_DEMO3_MAX_PDFS_PER_MEETING",
                str(max_per_meeting),
            )
        ),
    )
    total_cap = max_total
    if total_cap is None:
        env_total = os.environ.get("GOVERNANCE_DEMO3_MAX_PDFS_TOTAL", "").strip()
        if env_total:
            total_cap = max(1, int(env_total))

    try:
        from meeting_grouping import meeting_dir_for_media_file, resolve_meeting_dir
    except ImportError:
        return pick_demo3_pdfs(pdfs, max_pdfs=per_meeting if total_cap is None else total_cap)

    buckets: Dict[str, List[Path]] = defaultdict(list)
    for p in pdfs:
        session = meeting_dir_for_media_file(p, raw_root)
        if session is None:
            session = resolve_meeting_dir(p, raw_root)
        if session is not None:
            key = str(session.resolve())
        else:
            try:
                from meeting_date_scope import infer_meeting_date_for_file

                d = infer_meeting_date_for_file(p, raw_root) or "undated"
            except ImportError:
                d = "undated"
            key = f"date:{d}"
        buckets[key].append(p)

    selected: List[Path] = []
    for _key in sorted(buckets.keys()):
        group = pick_demo3_pdfs(buckets[_key], max_pdfs=per_meeting)
        for p in group:
            if p not in selected:
                selected.append(p)
            if total_cap is not None and len(selected) >= total_cap:
                return selected
    return selected


def run_demo1(inv: MeetingInventory, ctx: DemoContext) -> List[Dict[str, Any]]:
    j = inv.jurisdiction
    pdfs = inv.pdfs[: ctx.max_pdfs_per_jur]
    report: List[Dict[str, Any]] = []
    if not pdfs:
        return report
    log_line(f"\n— Demo 1 | {j.relative_label} — {len(pdfs)} PDF(s)", prefix="")
    force = force_reprocess_outputs()
    for pdf in pdfs:
        out_txt = mirror_output_path(
            input_path=pdf,
            raw_root=ctx.raw_root,
            processed_root=ctx.gemma_json_root,
            suffix=".visual_ocr.txt",
        )
        if not force and text_output_complete(out_txt):
            log_line(
                f"• {pdf.name}: reuse existing OCR → "
                f"{out_txt.relative_to(ctx.processed_root)}"
            )
            report.append(
                {
                    "jurisdiction": j.relative_label,
                    "fips": j.fips,
                    "pdf": str(pdf.relative_to(ctx.raw_root)),
                    "scanned": None,
                    "digital_chars": None,
                    "output": str(out_txt.relative_to(ctx.processed_root)),
                    "model_chars": None,
                    "reused": True,
                }
            )
            continue
        try:
            digital_chars = len(extract_pdf_digital_text(pdf))
        except Exception as e:
            print(f"  ! {pdf.name}: PDF probe failed — {e}")
            continue
        scanned = digital_chars < demo3_min_digital_chars()
        tag = "SCANNED (dark data)" if scanned else f"digital ({digital_chars} chars)"
        log_line(f"• {pdf.name}: {tag}")
        if not scanned and demo1_skip_when_digital():
            digital_text = extract_pdf_digital_text(pdf)
            out_txt.parent.mkdir(parents=True, exist_ok=True)
            out_txt.write_text(digital_text, encoding="utf-8")
            log_line(
                f"digital text layer — skip vision OCR → "
                f"{out_txt.relative_to(ctx.processed_root)} ({len(digital_text)} chars)",
                prefix="    ",
            )
            report.append(
                {
                    "jurisdiction": j.relative_label,
                    "fips": j.fips,
                    "pdf": str(pdf.relative_to(ctx.raw_root)),
                    "scanned": False,
                    "digital_chars": digital_chars,
                    "output": str(out_txt.relative_to(ctx.processed_root)),
                    "model_chars": len(digital_text),
                    "skipped_vision": True,
                }
            )
            continue
        log_line(
            f"⏳ Calling {ctx.genai_model} — visual OCR (often 1–3 min)…",
            prefix="    ",
        )
        t0 = time.perf_counter()
        try:
            result = call_google_genai_multimodal(
                api_key=ctx.api_key,
                model=ctx.genai_model,
                system_instruction=DEMO1_SYSTEM,
                user_text=DEMO1_USER,
                media=[(pdf, "application/pdf")],
                temperature=0.0,
                max_output_tokens=8192,
                media_resolution=TOKEN_BUDGET_HIGH if scanned else None,
            )
        except Exception as e:
            log_line(f"! Gemma call failed: {e}", prefix="    ")
            genai_inter_call_pause(TOKEN_BUDGET_HIGH if scanned else TOKEN_BUDGET_LOW)
            continue
        log_line(
            f"✓ Gemma returned in {format_elapsed(time.perf_counter() - t0)}",
            prefix="    ",
        )
        genai_inter_call_pause(TOKEN_BUDGET_HIGH if scanned else TOKEN_BUDGET_LOW)
        out_txt.write_text(result.text or "(empty response)", encoding="utf-8")
        report.append(
            {
                "jurisdiction": j.relative_label,
                "fips": j.fips,
                "pdf": str(pdf.relative_to(ctx.raw_root)),
                "scanned": scanned,
                "digital_chars": digital_chars,
                "output": str(out_txt.relative_to(ctx.processed_root)),
                "model_chars": len(result.text or ""),
            }
        )
        log_line(
            f"→ {out_txt.relative_to(ctx.processed_root)} ({len(result.text or '')} chars)",
            prefix="    ",
        )
    return report


def run_demo2(inv: MeetingInventory, ctx: DemoContext) -> List[Dict[str, Any]]:
    j = inv.jurisdiction
    pdfs = inv.pdfs[: ctx.max_pdfs_per_jur]
    report: List[Dict[str, Any]] = []
    if not pdfs:
        return report
    log_line(f"\n— Demo 2 | {j.relative_label} — {len(pdfs)} PDF(s)", prefix="")
    force = force_reprocess_outputs()
    for pdf in pdfs:
        if not Path(pdf).is_file():
            print(f"  • {Path(pdf).name}: skip — file not on disk (stale path; re-run §6 after reload)")
            continue
        print(f"  • {pdf.name}")
        if demo2_skip_when_digital():
            try:
                if not is_scanned_pdf(pdf, min_chars=demo3_min_digital_chars()):
                    print(
                        f"    digital PDF — skip Demo 2 page vision "
                        f"(GOVERNANCE_DEMO2_SKIP_WHEN_DIGITAL=1)"
                    )
                    continue
            except Exception as e:
                print(f"  ! PDF probe failed — {e}")
                continue
        try:
            pages = render_pdf_pages(pdf, dpi=200)
        except Exception as e:
            print(f"  ! render failed: {e}")
            continue
        total_pages = len(pages)
        pages = pages[: ctx.max_pages_per_pdf]
        if total_pages > len(pages):
            print(
                f"    {total_pages} pages in file; Demo 2 will process "
                f"first {len(pages)} (GOVERNANCE_DEMO_MAX_PAGES_PER_PDF={ctx.max_pages_per_pdf})"
            )
        elif total_pages:
            print(f"    {total_pages} page(s)")
        per_pdf_dir = mirror_output_path(
            input_path=pdf,
            raw_root=ctx.raw_root,
            processed_root=ctx.gemma_json_root,
            suffix="",
        )
        per_pdf_dir.mkdir(parents=True, exist_ok=True)
        if per_pdf_dir.is_file():
            per_pdf_dir.unlink()
            per_pdf_dir.mkdir(parents=True, exist_ok=True)
        if not force and demo2_pdf_outputs_complete(per_pdf_dir, expected_pages=len(pages)):
            print(
                f"    reuse existing page JSON ({len(pages)} pages) → "
                f"{per_pdf_dir.relative_to(ctx.processed_root)}"
            )
            report.append(read_json_file(per_pdf_dir / "_token_budget_report.json") or {})
            continue
        pdf_summary: Dict[str, Any] = {
            "jurisdiction": j.relative_label,
            "fips": j.fips,
            "pdf": str(pdf.relative_to(ctx.raw_root)),
            "page_count": len(pages),
            "budget_split": {TOKEN_BUDGET_HIGH: 0, TOKEN_BUDGET_LOW: 0},
            "pages": [],
        }
        for page in pages:
            page_out = per_pdf_dir / f"page_{page.page_index + 1:03d}.json"
            if not force and demo2_page_output_complete(page_out):
                page_data = read_json_file(page_out) or {}
                pdf_summary["budget_split"][page_data.get("token_budget", TOKEN_BUDGET_LOW)] = (
                    pdf_summary["budget_split"].get(page_data.get("token_budget", TOKEN_BUDGET_LOW), 0) + 1
                )
                pdf_summary["pages"].append(
                    {
                        "page": page.page_index + 1,
                        "classification": page_data.get("classification", page.classification),
                        "token_budget": page_data.get("token_budget", page.token_budget),
                        "elapsed_s": page_data.get("elapsed_s"),
                        "reused": True,
                    }
                )
                print(f"    page {page.page_index + 1}: reuse existing JSON")
                continue
            budget = page.token_budget
            user = DEMO2_USER_BY_CLASS.get(page.classification, DEMO2_USER_LOW)
            log_line(
                f"page {page.page_index + 1}: calling Gemma ({budget})…",
                prefix="    ",
            )
            t0 = time.perf_counter()
            try:
                result = call_google_genai_multimodal(
                    api_key=ctx.api_key,
                    model=ctx.genai_model,
                    system_instruction=DEMO2_SYSTEM,
                    user_text=user,
                    media=[(page.image_bytes, "image/png")],
                    temperature=0.0,
                    max_output_tokens=2048,
                    media_resolution=budget,
                )
            except Exception as e:
                print(f"  ! page {page.page_index + 1}: Gemma call failed — {e}")
                genai_inter_call_pause(budget)
                continue
            genai_inter_call_pause(budget)
            elapsed = time.perf_counter() - t0
            progress_tick(
                f"Demo 2 {pdf.name} page {page.page_index + 1}/{len(pages)} ({budget})",
                actual_seconds=elapsed,
            )
            try:
                page_json = json.loads(result.text.strip().lstrip("`"))
            except Exception:
                page_json = {"_parse_error": True, "_raw": (result.text or "")[:2000]}
            page_out.write_text(
                json.dumps(
                    {
                        "page_index": page.page_index,
                        "classification": page.classification,
                        "token_budget": budget,
                        "elapsed_s": round(elapsed, 2),
                        "model": ctx.genai_model,
                        "extracted": page_json,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            pdf_summary["budget_split"][budget] = pdf_summary["budget_split"].get(budget, 0) + 1
            pdf_summary["pages"].append(
                {
                    "page": page.page_index + 1,
                    "classification": page.classification,
                    "token_budget": budget,
                    "elapsed_s": round(elapsed, 2),
                }
            )
            log_line(
                f"page {page.page_index + 1}: {page.classification:>22}  "
                f"→ {budget:<6} ({format_elapsed(elapsed)})",
                prefix="    ",
            )
        report_path = per_pdf_dir / "_token_budget_report.json"
        report_path.write_text(json.dumps(pdf_summary, indent=2), encoding="utf-8")
        report.append(pdf_summary)
    return report


def _demo3_ocr_media_resolution() -> str:
    res = os.environ.get("GOVERNANCE_DEMO3_OCR_RESOLUTION", "LOW").strip().upper()
    if res not in ("HIGH", "MEDIUM", "LOW"):
        res = "LOW"
    return {
        "HIGH": TOKEN_BUDGET_HIGH,
        "MEDIUM": TOKEN_BUDGET_MEDIUM,
        "LOW": TOKEN_BUDGET_LOW,
    }[res]


def _demo3_ocr_model(ctx: DemoContext) -> str:
    return (
        os.environ.get("GOVERNANCE_DEMO3_OCR_MODEL", "").strip()
        or ctx.genai_model
    ).strip()


def _ensure_pdf_text_for_demo3(pdf: Path, ctx: DemoContext) -> Tuple[str, str]:
    """
    Meeting document as plain text for Demo 3.

    1. Digital text layer (PyMuPDF) when >= ``GOVERNANCE_DEMO3_MIN_DIGITAL_CHARS``.
    2. Cached ``.visual_ocr.txt`` from Demo 1 or a prior run.
    3. One light OCR call (LOW/MEDIUM vision, transcription-only prompt) → cache OCR file.
    """
    min_chars = demo3_min_digital_chars()
    try:
        digital = extract_pdf_digital_text(pdf)
    except Exception as e:
        raise RuntimeError(f"PDF text probe failed for {pdf.name}: {e}") from e
    if len(digital) >= min_chars:
        return (
            truncate_demo3_document_text(digital),
            f"digital text ({len(digital):,} chars)",
        )

    ocr_out = mirror_output_path(
        input_path=pdf,
        raw_root=ctx.raw_root,
        processed_root=ctx.gemma_json_root,
        suffix=".visual_ocr.txt",
    )
    if not force_reprocess_outputs() and text_output_complete(ocr_out):
        cached = ocr_out.read_text(encoding="utf-8").strip()
        if len(cached) >= min_chars:
            return (
                truncate_demo3_document_text(cached),
                f"cached OCR → {ocr_out.name} ({len(cached):,} chars)",
            )

    ocr_model = _demo3_ocr_model(ctx)
    ocr_res = _demo3_ocr_media_resolution()
    log_line(
        f"scanned PDF (<{min_chars} digital chars) — light OCR via {ocr_model} "
        f"({ocr_res} vision, transcription only)…",
        prefix="    ",
    )
    t0 = time.perf_counter()
    try:
        ocr_result = call_google_genai_multimodal(
            api_key=ctx.api_key,
            model=ocr_model,
            system_instruction=DEMO1_SYSTEM,
            user_text=DEMO1_USER,
            media=[(pdf, "application/pdf")],
            temperature=0.0,
            max_output_tokens=8192,
            media_resolution=ocr_res,
        )
    except Exception as e:
        raise RuntimeError(f"light OCR failed for {pdf.name}: {e}") from e
    log_line(
        f"✓ OCR in {format_elapsed(time.perf_counter() - t0)}",
        prefix="    ",
    )
    genai_inter_call_pause(ocr_res)
    ocr_text = (ocr_result.text or "").strip()
    ocr_out.parent.mkdir(parents=True, exist_ok=True)
    ocr_out.write_text(ocr_text or "(empty OCR response)", encoding="utf-8")
    if len(ocr_text) < min_chars:
        raise RuntimeError(
            f"OCR returned only {len(ocr_text)} chars for {pdf.name} — "
            "try GOVERNANCE_DEMO3_OCR_RESOLUTION=MEDIUM or GOVERNANCE_DEMO3_INPUT=vision"
        )
    return (
        truncate_demo3_document_text(ocr_text),
        f"light OCR ({len(ocr_text):,} chars) → {ocr_out.name}",
    )


def supplemental_demo3_with_video_enabled() -> bool:
    """When media scope is video/audio-only, still analyze agenda+minutes PDFs on disk."""
    return os.environ.get("GOVERNANCE_RUN_DEMO3_WITH_VIDEO", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def run_supplemental_demo3(inv: MeetingInventory, ctx: DemoContext) -> List[Dict[str, Any]]:
    """Run Demo 3 on jurisdiction PDFs when scope skipped Demo 3 but PDFs exist."""
    mscope = get_active_media_scope()
    if mscope.run_demo3 or not supplemental_demo3_with_video_enabled():
        return []
    try:
        from meeting_grouping import list_jurisdiction_pdf_paths
    except ImportError:
        return []
    pdfs = list_jurisdiction_pdf_paths(inv.jurisdiction.root)
    if not pdfs:
        return []
    picked = pick_demo3_pdfs_for_inventory(
        pdfs,
        ctx.raw_root,
        max_per_meeting=2,
        max_total=ctx.max_pdfs_per_jur,
    )
    if not picked:
        return []
    thinking_model = (ctx.thinking_model or ctx.genai_model).strip()
    log_line(
        f"\n— Demo 3 (PDFs with video scope) | {inv.jurisdiction.relative_label}: "
        f"{len(picked)} PDF(s)  (model: {thinking_model})",
        prefix="",
    )
    report: List[Dict[str, Any]] = []
    from theme_audit import audit_decision_themes

    for pdf in picked:
        _run_demo3_one_pdf(
            inv, ctx, pdf, thinking_model, report, audit_fn=audit_decision_themes
        )
    return report


def run_demo3(inv: MeetingInventory, ctx: DemoContext) -> List[Dict[str, Any]]:
    from theme_audit import audit_decision_themes

    j = inv.jurisdiction
    pdfs = pick_demo3_pdfs_for_inventory(
        inv.pdfs[: ctx.max_pdfs_per_jur],
        ctx.raw_root,
        max_per_meeting=2,
        max_total=ctx.max_pdfs_per_jur,
    )
    report: List[Dict[str, Any]] = []
    if not pdfs:
        return report
    thinking_model = (ctx.thinking_model or ctx.genai_model).strip()
    log_line(
        f"\n— Demo 3 | {j.relative_label}: {len(pdfs)} PDF(s)  (model: {thinking_model})",
        prefix="",
    )
    for pdf in pdfs:
        _run_demo3_one_pdf(
            inv, ctx, pdf, thinking_model, report, audit_fn=audit_decision_themes
        )
    return report


def _run_demo3_one_pdf(
    inv: MeetingInventory,
    ctx: DemoContext,
    pdf: Path,
    thinking_model: str,
    report: List[Dict[str, Any]],
    *,
    audit_fn,
) -> None:
    j = inv.jurisdiction
    if not Path(pdf).is_file():
        print(f"  • {Path(pdf).name}: skip — file not on disk (stale path; re-run §6 after reload)")
        return
    log_line(f"• {pdf.name}")
    json_out = mirror_output_path(
        input_path=pdf,
        raw_root=ctx.raw_root,
        processed_root=ctx.gemma_json_root,
        suffix=".thinking.json",
    )
    if not force_reprocess_outputs() and demo3_thinking_json_complete(json_out):
        log_line(
            f"reuse existing → {json_out.relative_to(ctx.processed_root)}",
            prefix="    ",
        )
        progress_tick(f"Demo 3 {pdf.name} (cached)")
        report.append(
            {
                "jurisdiction": j.relative_label,
                "pdf": str(pdf.relative_to(ctx.raw_root)),
                "json_ok": True,
                "reused": True,
            }
        )
        return
    geo_hint = (
        f"Geography hint from folder layout: state_code={j.state_code}, "
        f"scope={j.scope}, fips_or_place_id={j.fips or 'unknown'}. "
        "Use this when populating county_fips / county / postal_code in each decision."
    )
    all_media = list_media_sources(j.root)
    media_hint = format_media_context_hint(
        primary=all_media[0] if all_media else None,
        all_sources=all_media,
        input_modality="pdf_minutes",
        local_file=pdf,
    )
    use_text_input = demo3_text_first_enabled()
    doc_source = ""
    timeout_s = demo3_api_timeout_seconds()
    timeout_note = f", timeout {timeout_s // 60}m" if timeout_s else ""
    demo3_media: List[Tuple[Any, str]] = []
    media_res: Optional[str] = None
    include_thoughts = False
    thinking_budget: Optional[int] = None

    if use_text_input:
        try:
            doc_body, doc_source = _ensure_pdf_text_for_demo3(pdf, ctx)
        except Exception as e:
            log_line(f"! {e}", prefix="    ")
            return
        user_text = (
            f"{media_hint}\n{ctx.policy_prompt}\n\n---\n{geo_hint}\n\n"
            "## Meeting document (plain text)\n\n"
            f"{doc_body}\n\n---\n\n"
            "Apply the full deconstruction prompt to the meeting document above. "
            "Stick to what is actually in the text. Tables may be imperfect — "
            "do not invent content."
        )
        if ctx.thinking_budget is not None and ctx.thinking_budget > 0:
            thinking_budget = ctx.thinking_budget
            include_thoughts = True
        log_line(
            f"Calling {thinking_model} — text-only policy ({doc_source}{timeout_note})",
            prefix="    ",
        )
    else:
        user_text = (
            f"{media_hint}\n{ctx.policy_prompt}\n\n---\n{geo_hint}\n\n"
            "The attached PDF contains the meeting record. Apply the full deconstruction "
            "prompt to it. Stick to what is actually in the document."
        )
        demo3_res = os.environ.get("GOVERNANCE_DEMO3_MEDIA_RESOLUTION", "HIGH").strip().upper()
        if demo3_res not in ("HIGH", "MEDIUM", "LOW"):
            demo3_res = "HIGH"
        media_res = {
            "HIGH": TOKEN_BUDGET_HIGH,
            "MEDIUM": TOKEN_BUDGET_MEDIUM,
            "LOW": TOKEN_BUDGET_LOW,
        }.get(demo3_res, TOKEN_BUDGET_HIGH)
        demo3_media = [(pdf, "application/pdf")]
        include_thoughts = True
        thinking_budget = ctx.thinking_budget
        log_line(
            f"Calling {thinking_model} — full PDF ({demo3_res} vision{timeout_note}); "
            f"heartbeats every ~45s; 429 retries can add minutes",
            prefix="    ",
        )

    def _demo3_call():
        return call_google_genai_multimodal(
            api_key=ctx.api_key,
            model=thinking_model,
            system_instruction=DEMO3_SYSTEM,
            user_text=user_text,
            media=demo3_media,
            temperature=0.1,
            max_output_tokens=8192,
            media_resolution=media_res,
            include_thoughts=include_thoughts,
            thinking_budget=thinking_budget,
        )

    t0 = time.perf_counter()
    try:
        with log_phase(
            f"Demo 3 {pdf.name}",
            prefix="      ",
            detail=f"{thinking_model} {format_file_size(pdf)}",
        ):
            if timeout_s:
                result = call_with_wall_clock_timeout(
                    _demo3_call,
                    timeout_seconds=timeout_s,
                    label=f"Demo 3 {pdf.name}",
                )
            else:
                result = _demo3_call()
    except Exception as e:
        log_line(f"! Gemma call failed: {e}", prefix="    ")
        genai_inter_call_pause(media_res or TOKEN_BUDGET_LOW)
        return
    elapsed = time.perf_counter() - t0
    genai_inter_call_pause(media_res or TOKEN_BUDGET_LOW)
    parsed = parse_policy_analysis_response(result.text or "")
    if isinstance(parsed.get("json_analysis"), dict):
        parsed["json_analysis"] = enrich_policy_analysis_media_links(
            parsed["json_analysis"],
            primary=all_media[0] if all_media else None,
            all_sources=all_media,
        )
    raw_out = mirror_output_path(
        input_path=pdf,
        raw_root=ctx.raw_root,
        processed_root=ctx.gemma_json_root,
        suffix=".thinking.raw.txt",
    )
    raw_out.write_text(result.text or "", encoding="utf-8")
    analysis = parsed.get("json_analysis")
    if isinstance(analysis, dict):
        json_out.write_text(
            json.dumps(analysis, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"    → {json_out.relative_to(ctx.processed_root)}")
        decisions = analysis.get("decisions") or []
        if isinstance(decisions, list):
            audit_path = mirror_output_path(
                input_path=pdf,
                raw_root=ctx.raw_root,
                processed_root=ctx.gemma_json_root,
                suffix=".thinking.theme_audit.json",
            )
            audit_rows = audit_fn(decisions)
            audit_path.write_text(
                json.dumps({"decisions": audit_rows}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            flagged = [r for r in audit_rows if r.get("flags")]
            if flagged:
                print(f"    ⚠ theme audit: {len(flagged)} decision(s) flagged — see {audit_path.name}")
    if parsed.get("summary"):
        summary_out = mirror_output_path(
            input_path=pdf,
            raw_root=ctx.raw_root,
            processed_root=ctx.summaries_root,
            suffix=".thinking.summary.md",
        )
        summary_out.write_text(parsed["summary"], encoding="utf-8")
        print(f"    → {summary_out.relative_to(ctx.processed_root)}")
    if result.thoughts:
        thoughts_out = mirror_output_path(
            input_path=pdf,
            raw_root=ctx.raw_root,
            processed_root=ctx.gemma_json_root,
            suffix=".thinking.thoughts.md",
        )
        thoughts_out.write_text(result.thoughts, encoding="utf-8")
        print(
            f"    → {thoughts_out.relative_to(ctx.processed_root)} "
            f"(trace: {len(result.thoughts)} chars)"
        )
    progress_tick(f"Demo 3 {pdf.name} done", actual_seconds=elapsed)
    report.append(
        {
            "jurisdiction": j.relative_label,
            "pdf": str(pdf.relative_to(ctx.raw_root)),
            "demo3_input": demo3_input_mode(),
            "document_source": doc_source or "pdf attachment",
            "thoughts_chars": len(result.thoughts or ""),
            "json_ok": parsed.get("json_analysis") is not None
            and "_error" not in (parsed.get("json_analysis") or {}),
            "parse_error": parsed.get("parse_error"),
        }
    )


def run_demo4(
    inv: MeetingInventory,
    ctx: DemoContext,
    *,
    brief_cache: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    try:
        from meeting_grouping import (
            build_meeting_collateral_brief,
            format_audio_analysis_prompt,
            resolve_meeting_dir,
        )
    except ImportError:
        build_meeting_collateral_brief = None  # type: ignore[assignment,misc]
        format_audio_analysis_prompt = None  # type: ignore[assignment,misc]
        resolve_meeting_dir = None  # type: ignore[assignment,misc]

    if brief_cache is None:
        brief_cache = {}

    j = inv.jurisdiction
    from governance_meeting_llm import model_accepts_demo4_audio_chunks

    report: List[Dict[str, Any]] = []

    if demo4_uses_huggingface():
        try:
            from gemma_hf_backend import ensure_demo4_hf_ready

            with log_phase("Demo 4 load Hugging Face E2B (first time: download + GPU load)"):
                demo4_model = ensure_demo4_hf_ready(ctx.demo4_model or None)
            log_line(f"Demo 4 model: {demo4_model!r} (native audio/video on GPU)")
        except Exception as e:
            log_line(f"! Demo 4 skipped: {e}")
            return report
    else:
        try:
            demo4_model = resolve_demo4_model(
                ctx.genai_model,
                gatekeeper_model=ctx.gatekeeper_model,
                thinking_model=ctx.thinking_model,
                api_key=ctx.api_key,
            )
        except RuntimeError as e:
            log_line(f"! Demo 4 skipped: {e}")
            return report
    stale = (ctx.demo4_model or "").strip()
    if stale and stale != demo4_model:
        log_line(
            f"Demo 4 model: using {demo4_model!r} "
            f"(ignoring stale demo_ctx.demo4_model={stale!r})"
        )
    elif demo4_model != ctx.genai_model:
        print(
            f"  Demo 4 model: {demo4_model!r} "
            f"(recordings — {ctx.genai_model!r} is PDF/image-only)",
            flush=True,
        )
    else:
        print(f"  Demo 4 model: {demo4_model!r}", flush=True)
    audios = select_demo4_media(
        inv.audio,
        ctx.raw_root,
        max_files=ctx.max_audio_per_jur,
    )
    if not audios:
        return report
    log_line(f"\n— Demo 4 | {j.relative_label}: {len(audios)} media file(s)", prefix="")
    force = force_reprocess_outputs()
    for audio in audios:
        if not Path(audio).is_file():
            print(f"  • {Path(audio).name}: skip — file not on disk ({audio})")
            continue
        from governance_meeting_llm import demo4_prefer_opus_chunks

        use_video_api = (
            audio.suffix.lower() in VIDEO_EXTS
            and demo4_use_video_chunks()
            and model_supports_video_input(demo4_model)
        )
        # Opus-first ingest (default): cache and describe use audio slices, not mp4 segments.
        use_video = use_video_api and not demo4_prefer_opus_chunks()
        log_line(f"• {audio.name}  ({describe_demo4_file(audio, demo4_model=demo4_model)})")
        per_audio_dir = mirror_output_path(
            input_path=audio,
            raw_root=ctx.raw_root,
            processed_root=ctx.gemma_json_root,
            suffix="",
        )
        per_audio_dir.mkdir(parents=True, exist_ok=True)
        scratch = demo4_media_work_dir(ctx.scratch_audio_root, ctx.raw_root, audio)
        drift_out = per_audio_dir / "policy_drift.json"
        existing_chunks = find_existing_demo4_chunks(scratch, video=use_video)
        if existing_chunks and not force:
            ingest_plans: List[Tuple[str, List[Tuple[Path, str]]]] = [
                ("cached", discover_demo4_chunk_media(scratch, video=use_video)),
            ]
            log_line(f"reuse {len(existing_chunks)} ffmpeg chunk(s) from scratch")
        else:
            log_line(f"ffmpeg prep → scratch {scratch.relative_to(ctx.scratch_audio_root)}")
            with log_phase(f"ffmpeg ingest {audio.name}", detail=format_file_size(audio)):
                ingest_plans = list(
                    iter_demo4_ingest_strategies(
                        audio,
                        out_dir=scratch,
                        chunk_minutes=15,
                        prefer_video=use_video,
                        demo4_model=demo4_model,
                    )
                )
            if not ingest_plans:
                log_line("! ffmpeg could not produce any audio slices (Opus or MP3)")
                continue
            for _lbl, _media in ingest_plans:
                log_line(f"  plan: {_lbl} ({len(_media)} chunk(s))")
                break

        chunk_jsons: List[Dict[str, Any]] = []
        chunks_regenerated = False
        chunk_model = demo4_model
        ingest_succeeded = False

        for strategy_label, chunk_media in ingest_plans:
            chunk_media = chunk_media[: ctx.max_audio_chunks]
            if not chunk_media:
                continue
            mime_hint = chunk_media[0][1] if chunk_media else "?"
            log_line(
                f"ingest {strategy_label}: {len(chunk_media)} chunk(s) "
                f"({mime_hint}, cap {ctx.max_audio_chunks})"
            )
            strategy_jsons: List[Dict[str, Any]] = []
            strategy_regenerated = False

            for idx, (chunk_path, chunk_mime) in enumerate(chunk_media):
                chunk_out = per_audio_dir / f"chunk_{idx:03d}.json"
                if not force and policy_chunk_output_complete(chunk_out):
                    data = read_json_file(chunk_out) or {}
                    strategy_jsons.append(data.get("json_analysis") or {})
                    log_line(
                        f"chunk {idx + 1}: reuse existing JSON "
                        f"({chunk_out.relative_to(ctx.processed_root)})",
                        prefix="    ",
                    )
                    continue
                if chunk_out.is_file() and not force:
                    log_line(
                        f"chunk {idx + 1}: re-infer — existing JSON incomplete "
                        f"(need COFOG decisions in json_analysis)",
                        prefix="    ",
                    )
                strategy_regenerated = True
                chunks_regenerated = True
                geo_hint = (
                    f"Geography hint: state_code={j.state_code}, scope={j.scope}, "
                    f"fips_or_place_id={j.fips or 'unknown'}. chunk_index={idx} of {len(chunk_media)}."
                )
                primary_media = resolve_media_for_input_file(audio, j.root)
                all_media = list_media_sources(j.root)
                modality = (
                    "video_recording"
                    if strategy_label == "video_mp4"
                    else "audio_recording"
                )
                media_hint = format_media_context_hint(
                    primary=primary_media,
                    all_sources=all_media,
                    input_modality=modality,
                    chunk_index=idx,
                    chunk_minutes=15,
                    local_file=chunk_path,
                )
                meeting_dir = (
                    resolve_meeting_dir(audio, ctx.raw_root)
                    if resolve_meeting_dir and build_meeting_collateral_brief
                    else None
                )
                brief = ""
                if meeting_dir and build_meeting_collateral_brief:
                    mk = str(meeting_dir)
                    if mk not in brief_cache:
                        brief_cache[mk] = build_meeting_collateral_brief(
                            meeting_dir,
                            api_key=ctx.api_key,
                            model=ctx.genai_model,
                            jurisdiction_root=j.root,
                        )
                    brief = brief_cache.get(mk) or ""
                chunk_hint = (
                    "The attached audio is one 15-minute slice of a longer governance meeting. "
                    "Apply the deconstruction prompt to what is audible. Use the chunk_index "
                    "to anchor the timeline and assign consistent subject_id slugs across chunks."
                )
                if brief and format_audio_analysis_prompt and build_meeting_collateral_brief:
                    user_text = format_audio_analysis_prompt(
                        policy_prompt=ctx.policy_prompt,
                        meeting_brief=brief,
                        geo_hint=geo_hint,
                        chunk_hint=chunk_hint,
                    )
                    user_text = f"{media_hint}\n{user_text}"
                else:
                    user_text = (
                        f"{media_hint}\n{ctx.policy_prompt}\n\n---\n{geo_hint}\n\n{chunk_hint}"
                    )
                result = None
                chunk_sz = format_file_size(chunk_path)
                log_line(
                    f"chunk {idx + 1}/{len(chunk_media)}: {demo4_model} — {chunk_mime} {chunk_sz} "
                    f"(HF generate often 3–15 min; heartbeats every ~45s)…",
                    prefix="    ",
                )
                t_chunk = time.perf_counter()
                for try_model in demo4_models_to_try(
                    demo4_model,
                    api_key=ctx.api_key,
                    thinking_model=ctx.thinking_model,
                    chunk_mime=chunk_mime,
                ):
                    try:
                        if demo4_uses_huggingface():
                            log_line(
                                f"chunk {idx + 1}: ▶ HF forward pass starting…",
                                prefix="      ",
                            )
                        result = call_google_genai_multimodal(
                            api_key=ctx.api_key,
                            model=try_model,
                            system_instruction=DEMO4_SYSTEM,
                            user_text=user_text,
                            media=[(chunk_path, chunk_mime)],
                            temperature=0.1,
                            max_output_tokens=8192,
                            demo4=True,
                        )
                        chunk_model = try_model
                        if try_model != demo4_model:
                            log_line(
                                f"chunk {idx}: via {try_model!r} ({chunk_mime})",
                                prefix="    ",
                            )
                        break
                    except Exception as e:
                        if not demo4_uses_huggingface() and is_audio_modality_rejected(e):
                            continue
                        log_line(f"! chunk {idx} failed: {e}", prefix="    ")
                        genai_inter_call_pause(None)
                        result = None
                        break
                if result is None:
                    tried = demo4_models_to_try(
                        demo4_model,
                        api_key=ctx.api_key,
                        thinking_model=ctx.thinking_model,
                        chunk_mime=chunk_mime,
                    )
                    if not tried:
                        log_line(
                            f"! chunk {idx}: no audio model on key — set GOVERNANCE_DEMO4_MODEL "
                            f"— check HF_TOKEN / GPU (E2B) or §3 Google model list",
                            prefix="    ",
                        )
                    else:
                        log_line(
                            f"! chunk {idx}: rejected by {tried!r} — next ingest format if any",
                            prefix="    ",
                        )
                    genai_inter_call_pause(None)
                    continue
                log_line(
                    f"chunk {idx}: ✓ returned in {format_elapsed(time.perf_counter() - t_chunk)}",
                    prefix="    ",
                )
                genai_inter_call_pause(None)
                parsed = parse_policy_analysis_response(result.text or "")
                chunk_analysis = parsed.get("json_analysis")
                if isinstance(chunk_analysis, dict):
                    chunk_analysis = enrich_policy_analysis_media_links(
                        chunk_analysis,
                        primary=primary_media,
                        all_sources=all_media,
                        chunk_start_seconds=idx * 15 * 60,
                    )
                chunk_out.write_text(
                    json.dumps(
                        {
                            "chunk_index": idx,
                            "audio_source": str(chunk_path.name),
                            "ingest_strategy": strategy_label,
                            "mime_type": chunk_mime,
                            "json_analysis": chunk_analysis,
                            "summary": parsed.get("summary"),
                            "parse_error": parsed.get("parse_error"),
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                strategy_jsons.append(chunk_analysis or {})
                print(f"    chunk {idx}: → {chunk_out.relative_to(ctx.processed_root)}")
                progress_tick(f"Demo 4 {audio.name} chunk {idx + 1}/{len(chunk_media)}")

            if strategy_jsons and any(strategy_jsons):
                chunk_jsons = strategy_jsons
                ingest_succeeded = True
                log_line(f"✓ ingest {strategy_label} succeeded", prefix="    ")
                break
            log_line(
                f"ingest {strategy_label}: no chunk JSON — trying next format",
                prefix="    ",
            )

        if not ingest_succeeded or not chunk_jsons or not any(chunk_jsons):
            log_line(f"! Demo 4: all ingest formats failed for {audio.name}")
            continue
        if (
            not force
            and not chunks_regenerated
            and demo4_drift_output_complete(drift_out)
        ):
            drift = read_json_file(drift_out) or {}
            print(f"    drift: reuse existing → {drift_out.relative_to(ctx.processed_root)}")
        else:
            drift = policy_drift_summarize(
                chunk_jsons,
                api_key=ctx.api_key,
                model=chunk_model,
                thinking_model=ctx.thinking_model,
                focus_hint=ctx.drift_focus,
                canonical_prompt_text=ctx.policy_prompt,
            )
            drift_out.write_text(json.dumps(drift, indent=2, ensure_ascii=False), encoding="utf-8")
        drifted = drift.get("subjects") or drift.get("drifted_subjects") or []
        mmd_blocks = []
        for s in drifted:
            tl = s.get("diagram_timeline")
            if isinstance(tl, str) and tl.strip():
                label = s.get("subject_label") or s.get("subject_id") or "subject"
                mmd_blocks.append(f"%% {label}\n{tl}")
        legacy_tl = drift.get("diagram_timeline")
        if not mmd_blocks and isinstance(legacy_tl, str) and legacy_tl.strip():
            mmd_blocks.append(legacy_tl)
        if mmd_blocks:
            (per_audio_dir / "policy_drift.mmd").write_text("\n\n".join(mmd_blocks), encoding="utf-8")
        print(
            f"    drift: {len(drifted)} subject(s) → {drift_out.relative_to(ctx.processed_root)}"
        )
        progress_tick(f"Demo 4 drift {audio.name}")
        report.append(
            {
                "jurisdiction": j.relative_label,
                "audio": str(audio.relative_to(ctx.raw_root)),
                "chunks": len(chunk_jsons),
                "subjects_tracked": len(drifted),
            }
        )
    return report


@dataclass
class JurisdictionDemoReports:
    demo1: List[Dict[str, Any]] = field(default_factory=list)
    demo2: List[Dict[str, Any]] = field(default_factory=list)
    demo3: List[Dict[str, Any]] = field(default_factory=list)
    demo4: List[Dict[str, Any]] = field(default_factory=list)


def run_demos_for_jurisdiction(
    inv: MeetingInventory,
    ctx: DemoContext,
    *,
    brief_cache: Optional[Dict[str, str]] = None,
) -> JurisdictionDemoReports:
    """Run demos 1–4 for a single jurisdiction inventory."""
    try:
        from meeting_grouping import reconcile_inventory_media_paths

        n = reconcile_inventory_media_paths(inv, ctx.raw_root)
        if n:
            print(
                f"  Remapped {n} stale meeting file path(s) → session/ layout",
                flush=True,
            )
    except ImportError:
        pass
    reports = JurisdictionDemoReports()
    label = inv.jurisdiction.relative_label
    plan = build_work_plan(inv, ctx)
    progress = PipelineProgress.from_plan(label, plan)
    set_pipeline_progress(progress)
    mscope = get_active_media_scope()
    try:
        if mscope.run_demo1:
            with timed_step(f"Demo 1 PDF OCR | {label}"):
                reports.demo1 = run_demo1(inv, ctx)
                progress_tick("Demo 1 complete")
        else:
            log_line(f"⊘ Demo 1 skipped (media scope: {mscope.key})")
        if mscope.run_demo2:
            with timed_step(f"Demo 2 PDF pages (token budget) | {label}"):
                reports.demo2 = run_demo2(inv, ctx)
                progress_tick("Demo 2 complete")
        else:
            log_line(f"⊘ Demo 2 skipped (media scope: {mscope.key})")
        if mscope.run_demo3:
            with timed_step(f"Demo 3 policy PDFs | {label}"):
                reports.demo3 = run_demo3(inv, ctx)
                progress_tick("Demo 3 complete")
        else:
            log_line(f"⊘ Demo 3 skipped (media scope: {mscope.key})")
            sup = run_supplemental_demo3(inv, ctx)
            if sup:
                reports.demo3 = sup
                progress_tick("Demo 3 (agenda+minutes PDFs) complete")
        if mscope.run_demo4:
            with timed_step(f"{demo4_step_label(mscope)} | {label}"):
                reports.demo4 = run_demo4(inv, ctx, brief_cache=brief_cache)
                progress_tick("Demo 4 complete")
        else:
            log_line(f"⊘ Demo 4 skipped (media scope: {mscope.key})")
        try:
            from meeting_consolidated_summary import run_consolidated_summaries_for_jurisdiction

            with timed_step(f"Consolidated meeting summaries | {label}"):
                run_consolidated_summaries_for_jurisdiction(
                    jurisdiction_root=inv.jurisdiction.root,
                    raw_root=ctx.raw_root,
                    gemma_json_root=ctx.gemma_json_root,
                    summaries_root=ctx.summaries_root,
                    jurisdiction_prefix=inv.jurisdiction.relative_label,
                    api_key=ctx.api_key,
                    genai_model=ctx.genai_model,
                )
                progress_tick("Consolidated summaries complete")
        except ImportError:
            pass
    finally:
        progress.finish()
        set_pipeline_progress(None)
    return reports
