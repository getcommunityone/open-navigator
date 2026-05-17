"""
Notebook demos 1–4 extracted for per-jurisdiction end-to-end runs.

Imported by ``jurisdiction_pipeline`` and optionally by ``02_run_meeting_llm.ipynb``.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from governance_meeting_llm import (
    TOKEN_BUDGET_HIGH,
    TOKEN_BUDGET_LOW,
    VIDEO_EXTS,
    MeetingInventory,
    call_google_genai_multimodal,
    chunk_meeting_media_for_demo4,
    demo2_page_output_complete,
    demo2_pdf_outputs_complete,
    demo3_thinking_json_complete,
    demo4_drift_output_complete,
    extract_pdf_digital_text,
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
    "COFOG codes belong on each decision via primary_theme_cofog / secondary_theme_cofog."
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
    "decision. The chunk_index tells you which 15-minute slice of the meeting this "
    "audio covers."
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


def run_demo1(inv: MeetingInventory, ctx: DemoContext) -> List[Dict[str, Any]]:
    j = inv.jurisdiction
    pdfs = inv.pdfs[: ctx.max_pdfs_per_jur]
    report: List[Dict[str, Any]] = []
    if not pdfs:
        return report
    print(f"\n— Demo 1 | {j.relative_label} — {len(pdfs)} PDF(s)")
    force = force_reprocess_outputs()
    for pdf in pdfs:
        out_txt = mirror_output_path(
            input_path=pdf,
            raw_root=ctx.raw_root,
            processed_root=ctx.gemma_json_root,
            suffix=".visual_ocr.txt",
        )
        if not force and text_output_complete(out_txt):
            print(f"  • {pdf.name}: reuse existing OCR → {out_txt.relative_to(ctx.processed_root)}")
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
        scanned = digital_chars < 200
        tag = "SCANNED (dark data)" if scanned else f"digital ({digital_chars} chars)"
        print(f"  • {pdf.name}: {tag}")
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
            print(f"    ! Gemma call failed: {e}")
            continue
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
        print(f"    → {out_txt.relative_to(ctx.processed_root)} ({len(result.text or '')} chars)")
    return report


def run_demo2(inv: MeetingInventory, ctx: DemoContext) -> List[Dict[str, Any]]:
    j = inv.jurisdiction
    pdfs = inv.pdfs[: ctx.max_pdfs_per_jur]
    report: List[Dict[str, Any]] = []
    if not pdfs:
        return report
    print(f"\n— Demo 2 | {j.relative_label} — {len(pdfs)} PDF(s)")
    force = force_reprocess_outputs()
    for pdf in pdfs:
        print(f"  • {pdf.name}")
        try:
            pages = render_pdf_pages(pdf, dpi=200)
        except Exception as e:
            print(f"  ! render failed: {e}")
            continue
        pages = pages[: ctx.max_pages_per_pdf]
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
            t0 = time.time()
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
                continue
            elapsed = time.time() - t0
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
            print(
                f"    page {page.page_index + 1}: {page.classification:>22}  "
                f"→ {budget:<6} ({elapsed:.1f}s)"
            )
        report_path = per_pdf_dir / "_token_budget_report.json"
        report_path.write_text(json.dumps(pdf_summary, indent=2), encoding="utf-8")
        report.append(pdf_summary)
    return report


def run_demo3(inv: MeetingInventory, ctx: DemoContext) -> List[Dict[str, Any]]:
    j = inv.jurisdiction
    pdf = pick_representative_pdf(inv.pdfs)
    report: List[Dict[str, Any]] = []
    if pdf is None:
        return report
    thinking_model = (ctx.thinking_model or ctx.genai_model).strip()
    print(f"\n— Demo 3 | {j.relative_label}: {pdf.name}  (model: {thinking_model})")
    json_out = mirror_output_path(
        input_path=pdf,
        raw_root=ctx.raw_root,
        processed_root=ctx.gemma_json_root,
        suffix=".thinking.json",
    )
    if not force_reprocess_outputs() and demo3_thinking_json_complete(json_out):
        print(f"  reuse existing → {json_out.relative_to(ctx.processed_root)}")
        report.append(
            {
                "jurisdiction": j.relative_label,
                "pdf": str(pdf.relative_to(ctx.raw_root)),
                "json_ok": True,
                "reused": True,
            }
        )
        return report
    geo_hint = (
        f"Geography hint from folder layout: state_code={j.state_code}, "
        f"scope={j.scope}, fips_or_place_id={j.fips or 'unknown'}. "
        "Use this when populating county_fips / county / postal_code in each decision."
    )
    user_text = (
        f"{ctx.policy_prompt}\n\n---\n{geo_hint}\n\n"
        "The attached PDF contains the meeting record. Apply the full deconstruction "
        "prompt to it. Stick to what is actually in the document."
    )
    try:
        result = call_google_genai_multimodal(
            api_key=ctx.api_key,
            model=thinking_model,
            system_instruction=DEMO3_SYSTEM,
            user_text=user_text,
            media=[(pdf, "application/pdf")],
            temperature=0.1,
            max_output_tokens=8192,
            media_resolution=TOKEN_BUDGET_HIGH,
            include_thoughts=True,
            thinking_budget=ctx.thinking_budget,
        )
    except Exception as e:
        print(f"  ! Gemma call failed: {e}")
        return report
    parsed = parse_policy_analysis_response(result.text or "")
    raw_out = mirror_output_path(
        input_path=pdf,
        raw_root=ctx.raw_root,
        processed_root=ctx.gemma_json_root,
        suffix=".thinking.raw.txt",
    )
    raw_out.write_text(result.text or "", encoding="utf-8")
    if parsed.get("json_analysis") is not None:
        json_out.write_text(
            json.dumps(parsed["json_analysis"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  → {json_out.relative_to(ctx.processed_root)}")
    if parsed.get("summary"):
        summary_out = mirror_output_path(
            input_path=pdf,
            raw_root=ctx.raw_root,
            processed_root=ctx.summaries_root,
            suffix=".thinking.summary.md",
        )
        summary_out.write_text(parsed["summary"], encoding="utf-8")
        print(f"  → {summary_out.relative_to(ctx.processed_root)}")
    if result.thoughts:
        thoughts_out = mirror_output_path(
            input_path=pdf,
            raw_root=ctx.raw_root,
            processed_root=ctx.gemma_json_root,
            suffix=".thinking.thoughts.md",
        )
        thoughts_out.write_text(result.thoughts, encoding="utf-8")
        print(f"  → {thoughts_out.relative_to(ctx.processed_root)} (trace: {len(result.thoughts)} chars)")
    report.append(
        {
            "jurisdiction": j.relative_label,
            "pdf": str(pdf.relative_to(ctx.raw_root)),
            "thoughts_chars": len(result.thoughts or ""),
            "json_ok": parsed.get("json_analysis") is not None
            and "_error" not in (parsed.get("json_analysis") or {}),
            "parse_error": parsed.get("parse_error"),
        }
    )
    return report


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
    audios = inv.audio[: ctx.max_audio_per_jur]
    report: List[Dict[str, Any]] = []
    if not audios:
        return report
    print(f"\n— Demo 4 | {j.relative_label}: {len(audios)} media file(s)")
    force = force_reprocess_outputs()
    for audio in audios:
        use_video = audio.suffix.lower() in VIDEO_EXTS and demo4_use_video_chunks()
        kind = "video/mp4 chunks" if use_video else "audio chunks"
        print(f"  • {audio.name}  ({kind})")
        per_audio_dir = mirror_output_path(
            input_path=audio,
            raw_root=ctx.raw_root,
            processed_root=ctx.gemma_json_root,
            suffix="",
        )
        per_audio_dir.mkdir(parents=True, exist_ok=True)
        rel = audio.resolve().relative_to(ctx.raw_root.resolve())
        scratch = ctx.scratch_audio_root / rel.with_suffix("")
        scratch.mkdir(parents=True, exist_ok=True)
        drift_out = per_audio_dir / "policy_drift.json"
        existing_chunks = find_existing_demo4_chunks(scratch, video=use_video)
        if existing_chunks and not force:
            chunk_media = [(p, "video/mp4" if use_video else mime_for(p)) for p in existing_chunks]
            print(f"    reuse {len(chunk_media)} ffmpeg chunk(s) from scratch")
        else:
            try:
                chunk_media = chunk_meeting_media_for_demo4(
                    audio, out_dir=scratch, chunk_minutes=15
                )
            except Exception as e:
                print(f"    ! ffmpeg chunking failed: {e}")
                continue
        chunk_media = chunk_media[: ctx.max_audio_chunks]
        print(f"    {len(chunk_media)} chunk(s) (cap {ctx.max_audio_chunks})")
        chunk_jsons: List[Dict[str, Any]] = []
        chunks_regenerated = False
        for idx, (chunk_path, chunk_mime) in enumerate(chunk_media):
            chunk_out = per_audio_dir / f"chunk_{idx:03d}.json"
            if not force and policy_chunk_output_complete(chunk_out):
                data = read_json_file(chunk_out) or {}
                chunk_jsons.append(data.get("json_analysis") or {})
                print(f"    chunk {idx}: reuse existing JSON")
                continue
            chunks_regenerated = True
            geo_hint = (
                f"Geography hint: state_code={j.state_code}, scope={j.scope}, "
                f"fips_or_place_id={j.fips or 'unknown'}. chunk_index={idx} of {len(chunks)}."
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
                        client=None,
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
            else:
                user_text = f"{ctx.policy_prompt}\n\n---\n{geo_hint}\n\n{chunk_hint}"
            try:
                result = call_google_genai_multimodal(
                    api_key=ctx.api_key,
                    model=ctx.genai_model,
                    system_instruction=DEMO4_SYSTEM,
                    user_text=user_text,
                    media=[(chunk_path, chunk_mime)],
                    temperature=0.1,
                    max_output_tokens=8192,
                )
            except Exception as e:
                print(f"    ! chunk {idx} failed: {e}")
                continue
            parsed = parse_policy_analysis_response(result.text or "")
            chunk_out.write_text(
                json.dumps(
                    {
                        "chunk_index": idx,
                        "audio_source": str(chunk_path.name),
                        "json_analysis": parsed.get("json_analysis"),
                        "summary": parsed.get("summary"),
                        "parse_error": parsed.get("parse_error"),
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            chunk_jsons.append(parsed.get("json_analysis") or {})
            print(f"    chunk {idx}: → {chunk_out.relative_to(ctx.processed_root)}")
        if not chunk_jsons or not any(chunk_jsons):
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
                model=ctx.genai_model,
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
    reports = JurisdictionDemoReports()
    reports.demo1 = run_demo1(inv, ctx)
    reports.demo2 = run_demo2(inv, ctx)
    reports.demo3 = run_demo3(inv, ctx)
    reports.demo4 = run_demo4(inv, ctx, brief_cache=brief_cache)
    return reports
