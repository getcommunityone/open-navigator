"""
Per-meeting consolidated summary for judges: agenda/minutes/video/audio in one place.

Writes ``03_human_summaries/.../meetings/{date}/{slug}/_meeting_summary.md`` plus
copies ``policy_drift.mmd`` beside it when Demo 4 ran on that meeting's recording.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from governance_meeting_llm import mirror_output_path, read_json_file
from theme_audit import audit_decision_themes, format_theme_audit_markdown


def _rel_under(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _find_under(root: Path, pattern: str) -> List[Path]:
    if not root.is_dir():
        return []
    return sorted(root.glob(pattern))


def _gather_meeting_artifacts(
    meeting_dir: Path,
    *,
    raw_root: Path,
    gemma_json_root: Path,
    summaries_root: Path,
) -> Dict[str, Any]:
    """Collect paths and parsed JSON for one ``meetings/{date}/{slug}/`` folder."""
    rel = _rel_under(raw_root, meeting_dir)
    out: Dict[str, Any] = {
        "meeting_dir": rel,
        "agenda_pdfs": [],
        "minutes_pdfs": [],
        "audio_video": [],
        "demo3": [],
        "demo2_pages": [],
        "demo1_ocr": [],
        "demo4_chunks": [],
        "drift_json": None,
        "drift_mmd": None,
        "transcripts": [],
        "human_summaries": [],
    }
    for sub, key in (("agenda", "agenda_pdfs"), ("minutes", "minutes_pdfs")):
        d = meeting_dir / sub
        if d.is_dir():
            out[key] = sorted(d.glob("*.pdf"))
    av = meeting_dir / "audio"
    if av.is_dir():
        exts = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".mov", ".mkv", ".opus"}
        out["audio_video"] = sorted(
            p for p in av.rglob("*") if p.is_file() and p.suffix.lower() in exts
        )

    for pdf in out["agenda_pdfs"] + out["minutes_pdfs"]:
        stem = mirror_output_path(
            input_path=pdf,
            raw_root=raw_root,
            processed_root=gemma_json_root,
            suffix=".thinking.json",
        )
        if stem.is_file():
            data = read_json_file(stem) or {}
            out["demo3"].append({"pdf": pdf, "json_path": stem, "analysis": data})
        ocr = mirror_output_path(
            input_path=pdf,
            raw_root=raw_root,
            processed_root=gemma_json_root,
            suffix=".visual_ocr.txt",
        )
        if ocr.is_file():
            out["demo1_ocr"].append(ocr)
        page_dir = mirror_output_path(
            input_path=pdf,
            raw_root=raw_root,
            processed_root=gemma_json_root,
            suffix="",
        )
        out["demo2_pages"].extend(_find_under(page_dir, "page_*.json"))

        sm = mirror_output_path(
            input_path=pdf,
            raw_root=raw_root,
            processed_root=summaries_root,
            suffix=".thinking.summary.md",
        )
        if sm.is_file():
            out["human_summaries"].append(sm)

    for media in out["audio_video"]:
        per = mirror_output_path(
            input_path=media,
            raw_root=raw_root,
            processed_root=gemma_json_root,
            suffix="",
        )
        out["demo4_chunks"].extend(_find_under(per, "chunk_*.json"))
        drift = per / "policy_drift.json"
        if drift.is_file():
            out["drift_json"] = drift
        mmd = per / "policy_drift.mmd"
        if mmd.is_file():
            out["drift_mmd"] = mmd

    for media in out["audio_video"]:
        per = mirror_output_path(
            input_path=media,
            raw_root=raw_root,
            processed_root=gemma_json_root,
            suffix="",
        )
        out["transcripts"].extend(_find_under(per, "transcript.*.txt"))

    return out


def build_consolidated_summary_markdown(artifacts: Dict[str, Any]) -> str:
    lines: List[str] = [
        f"# Meeting summary — `{artifacts.get('meeting_dir', '')}`",
        "",
        "Consolidated view of pipeline outputs for this session "
        "(agenda, minutes, recordings, drift). Re-run with "
        "`GOVERNANCE_FORCE_REPROCESS=1` after prompt or scope changes.",
        "",
        "## Sources on disk",
        "",
    ]
    lines.append(f"- **Agenda PDFs:** {len(artifacts.get('agenda_pdfs') or [])}")
    lines.append(f"- **Minutes PDFs:** {len(artifacts.get('minutes_pdfs') or [])}")
    lines.append(f"- **Audio / video:** {len(artifacts.get('audio_video') or [])}")
    lines.append(f"- **Demo 3 analyses:** {len(artifacts.get('demo3') or [])}")
    lines.append(f"- **Demo 4 chunks:** {len(artifacts.get('demo4_chunks') or [])}")
    lines.append(f"- **Transcripts:** {len(artifacts.get('transcripts') or [])}")
    lines.append("")

    missing: List[str] = []
    if artifacts.get("agenda_pdfs") and not artifacts.get("demo3"):
        missing.append("agenda present but no Demo 3 `.thinking.json` (policy analysis not run or failed)")
    if artifacts.get("minutes_pdfs") and len(artifacts.get("demo3") or []) < 2:
        missing.append(
            "minutes PDF present but not analyzed — Demo 3 defaults to one PDF per jurisdiction "
            "(agenda first); set `GOVERNANCE_DEMO3_MAX_PDFS=2` or run medium/full scope"
        )
    if artifacts.get("audio_video") and not artifacts.get("demo4_chunks"):
        missing.append(
            "recording present but no Demo 4 chunks — check `GOVERNANCE_DEMO_MAX_AUDIO_PER_JUR`, "
            "429 quota, or Gatekeeper exclusions"
        )
    if artifacts.get("demo4_chunks") and not artifacts.get("drift_json"):
        missing.append("chunks exist but no `policy_drift.json` (drift pass failed or skipped)")
    if missing:
        lines.append("## Gaps")
        lines.append("")
        for m in missing:
            lines.append(f"- ⚠ {m}")
        lines.append("")

    for item in artifacts.get("demo3") or []:
        pdf = item.get("pdf")
        analysis = item.get("analysis") or {}
        lines.append(f"## Policy analysis — `{pdf.name if pdf else '?'}`")
        lines.append("")
        meeting = analysis.get("meeting") if isinstance(analysis, dict) else {}
        if isinstance(meeting, dict):
            lines.append(
                f"- **Body:** {meeting.get('body_name') or '—'} | "
                f"**Date:** {meeting.get('meeting_date') or '—'} | "
                f"**Modality:** {meeting.get('input_modality') or '—'}"
            )
            sources = meeting.get("media_sources") or []
            if sources:
                lines.append("- **Media sources:**")
                for ms in sources[:6]:
                    if isinstance(ms, dict):
                        lines.append(
                            f"  - {ms.get('media_source_id')}: {ms.get('platform') or '—'} "
                            f"{ms.get('canonical_url') or ms.get('page_url') or ''}"
                        )
        lines.append("")
        decisions = analysis.get("decisions") if isinstance(analysis, dict) else []
        if isinstance(decisions, list) and decisions:
            lines.append(format_theme_audit_markdown(audit_decision_themes(decisions)))
        lines.append("")

    for sm in artifacts.get("human_summaries") or []:
        lines.append(f"## Narrative summary (Demo 3 markdown)")
        lines.append("")
        try:
            body = sm.read_text(encoding="utf-8").strip()
            lines.append(body[:12_000] + ("…" if len(body) > 12_000 else ""))
        except OSError:
            lines.append(f"_Could not read {sm.name}_")
        lines.append("")

    if artifacts.get("drift_json"):
        drift = read_json_file(artifacts["drift_json"]) or {}
        mls = drift.get("meeting_level_summary") or {}
        lines.append("## Audio / video — policy drift (Demo 4)")
        lines.append("")
        if mls.get("headline"):
            lines.append(f"**{mls['headline']}**")
            lines.append("")
        lines.append(
            f"- Subjects tracked: {mls.get('subjects_tracked', '—')} | "
            f"with drift: {mls.get('subjects_with_drift', '—')}"
        )
        tensions = mls.get("emergent_value_tensions") or []
        if tensions:
            lines.append("- Emergent tensions: " + "; ".join(str(t) for t in tensions[:8]))
        lines.append("")

    if artifacts.get("drift_mmd"):
        lines.append("## Mermaid — narrative drift timelines")
        lines.append("")
        lines.append(
            f"Full diagram file: `{artifacts['drift_mmd'].name}` "
            "(also copied next to this summary). Paste into https://mermaid.live or a Mermaid preview."
        )
        lines.append("")
        lines.append("```mermaid")
        try:
            mmd_body = artifacts["drift_mmd"].read_text(encoding="utf-8").strip()
            lines.append(mmd_body[:14_000])
        except OSError:
            lines.append("%% unreadable")
        lines.append("```")
        lines.append("")

    for tr in artifacts.get("transcripts") or []:
        lines.append(f"## Transcript — `{tr.name}`")
        lines.append("")
        try:
            t = tr.read_text(encoding="utf-8", errors="replace").strip()
            lines.append(t[:4000] + ("…" if len(t) > 4000 else ""))
        except OSError:
            lines.append("_unreadable_")
        lines.append("")

    return "\n".join(lines)


def write_meeting_consolidated_summary(
    meeting_dir: Path,
    *,
    raw_root: Path,
    gemma_json_root: Path,
    summaries_root: Path,
) -> Tuple[Path, Optional[Path]]:
    """Write ``_meeting_summary.md`` and copy ``policy_drift.mmd`` under summaries mirror."""
    artifacts = _gather_meeting_artifacts(
        meeting_dir,
        raw_root=raw_root,
        gemma_json_root=gemma_json_root,
        summaries_root=summaries_root,
    )
    rel = Path(artifacts["meeting_dir"])
    out_dir = summaries_root / rel
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "_meeting_summary.md"
    summary_path.write_text(
        build_consolidated_summary_markdown(artifacts), encoding="utf-8"
    )
    mmd_copy: Optional[Path] = None
    src_mmd = artifacts.get("drift_mmd")
    if src_mmd and src_mmd.is_file():
        mmd_copy = out_dir / "policy_drift.mmd"
        shutil.copy2(src_mmd, mmd_copy)
    return summary_path, mmd_copy


def run_consolidated_summaries_for_jurisdiction(
    *,
    jurisdiction_root: Path,
    raw_root: Path,
    gemma_json_root: Path,
    summaries_root: Path,
) -> List[Path]:
    """Build one consolidated summary per ``meetings/{date}/{slug}/`` session."""
    if os.environ.get("GOVERNANCE_CONSOLIDATED_SUMMARY", "1").strip().lower() in (
        "0",
        "false",
        "no",
    ):
        return []
    try:
        from meeting_grouping import iter_meeting_dirs, jurisdiction_prefix_from_relative
    except ImportError:
        return []

    try:
        rel = jurisdiction_root.resolve().relative_to(raw_root.resolve())
        jur_prefix = rel.as_posix()
    except ValueError:
        jur_prefix = jurisdiction_prefix_from_relative(str(jurisdiction_root))

    written: List[Path] = []
    for meeting_dir in iter_meeting_dirs(raw_root, jur_prefix):
        summary_path, _ = write_meeting_consolidated_summary(
            meeting_dir,
            raw_root=raw_root,
            gemma_json_root=gemma_json_root,
            summaries_root=summaries_root,
        )
        written.append(summary_path)
        print(
            f"  → consolidated summary: {summary_path.relative_to(summaries_root)}",
            flush=True,
        )
    return written
