"""
Per-meeting consolidated summary for judges: agenda, minutes, video, decisions, people.

Writes ``_meeting_summary.md`` under ``03_human_summaries/…`` and (by default) beside
the raw ``meetings/{date}/{slug}/`` folder so it appears in the same Drive tree as
agenda/minutes.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .governance_meeting_llm import (
    VIDEO_EXTS,
    mirror_output_path,
    read_json_file,
)
from .theme_audit import audit_decision_themes, format_theme_audit_markdown

_AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".opus", ".aac", ".flac"}
_MEDIA_EXTS = _AUDIO_EXTS | VIDEO_EXTS


def _rel_under(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _find_under(root: Path, pattern: str) -> List[Path]:
    if not root.is_dir():
        return []
    return sorted(root.glob(pattern))


def _meeting_calendar_date(meeting_dir: Path) -> Optional[str]:
    """``YYYY-MM-DD`` from parent ``meetings/2026_05_06/…`` folder name."""
    import re

    for part in reversed(meeting_dir.parts):
        m = re.match(r"^(20\d{2})_(\d{2})_(\d{2})$", part)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def _flat_recordings_for_meeting(
    meeting_dir: Path,
    jurisdiction_root: Path,
) -> List[Path]:
    """MP4/MP3 at jurisdiction root (pre-organize) matching this meeting's date."""
    date_s = _meeting_calendar_date(meeting_dir)
    if not date_s or not jurisdiction_root.is_dir():
        return []
    underscored = date_s.replace("-", "_")
    found: List[Path] = []
    for p in sorted(jurisdiction_root.iterdir()):
        if not p.is_file() or p.suffix.lower() not in _MEDIA_EXTS:
            continue
        stem = p.stem
        if underscored in stem or date_s in stem:
            found.append(p)
    return found


def _flat_pdfs_for_meeting(
    meeting_dir: Path,
    jurisdiction_root: Path,
) -> Tuple[List[Path], List[Path]]:
    """
    Agenda/minutes PDFs still at jurisdiction root (e.g. ``2026_05_06-Agenda.pdf``).

    Colab often leaves Drive flat while ``meetings/2026_05_06/session/`` exists empty;
    the pipeline still writes Gemma outputs keyed by those flat paths.
    """
    date_s = _meeting_calendar_date(meeting_dir)
    if not date_s or not jurisdiction_root.is_dir():
        return [], []
    underscored = date_s.replace("-", "_")
    agenda: List[Path] = []
    minutes: List[Path] = []
    for p in sorted(jurisdiction_root.iterdir()):
        if not p.is_file() or p.suffix.lower() != ".pdf":
            continue
        stem = p.stem.lower()
        if underscored not in stem and date_s not in stem:
            continue
        if "minute" in stem:
            minutes.append(p)
        elif "agenda" in stem:
            agenda.append(p)
    return agenda, minutes


def _doc_label(pdf: Path) -> str:
    name = pdf.name.lower()
    if "minute" in name:
        return "Minutes"
    if "agenda" in name:
        return "Agenda"
    return "PDF"


def format_people_markdown(
    meeting: Dict[str, Any],
    people: List[Any],
) -> str:
    lines = ["## People", ""]
    members = meeting.get("members_present") or []
    absent = meeting.get("members_absent") or []
    if members:
        lines.append("**Members present:** " + ", ".join(str(m) for m in members))
    if absent:
        lines.append("**Members absent:** " + ", ".join(str(m) for m in absent))
    if members or absent:
        lines.append("")
    if not isinstance(people, list) or not people:
        if not members and not absent:
            lines.append("_No people extracted._")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "| Name | Role | Appeared as | Party | Lobbyist |",
            "|---|---|---|---|---|",
        ]
    )
    for p in people:
        if not isinstance(p, dict):
            continue
        lines.append(
            f"| {p.get('full_name') or '—'} | {p.get('role') or '—'} | "
            f"{p.get('appeared_as') or '—'} | {p.get('party_affiliation') or '—'} | "
            f"{'yes' if p.get('is_lobbyist') else '—'} |"
        )
    lines.append("")
    return "\n".join(lines)


def _format_playback_markdown(d: Dict[str, Any]) -> List[str]:
    """Watch/listen line with markdown link when Demo 4 filled ``playback_url``."""
    citation = d.get("media_citation") if isinstance(d.get("media_citation"), dict) else {}
    ts_start = citation.get("timestamp_start") or d.get("timestamp_start")
    ts_end = citation.get("timestamp_end") or d.get("timestamp_end")
    url = citation.get("playback_url")
    note = (citation.get("playback_url_note") or "").strip()
    out: List[str] = []
    if ts_start or ts_end:
        span = str(ts_start or "?")
        if ts_end:
            span += f" – {ts_end}"
        out.append(f"- **Recording time:** {span} (elapsed from start of meeting)")
    if url:
        label = f"Jump to {ts_start}" if ts_start else "Open recording"
        out.append(f"- **Watch / listen:** [{label}]({url})")
    elif ts_start:
        out.append(
            "- **Watch / listen:** _no playback URL — ensure ``_manifest.json`` "
            "lists ``video_assets`` with ``source_mp4_url`` or YouTube URL_"
        )
    if note:
        out.append(f"- _Playback note: {note}_")
    return out


def format_decisions_markdown(decisions: List[Any], *, heading: str) -> str:
    if not isinstance(decisions, list) or not decisions:
        return f"### {heading}\n\n_No decisions extracted._\n\n"
    lines = [f"### {heading}", ""]
    for d in decisions:
        if not isinstance(d, dict):
            continue
        did = d.get("decision_id") or "?"
        topic = (d.get("topic") or d.get("agenda_item") or "—").strip()
        headline = (d.get("headline") or "").strip()
        statement = (d.get("decision_statement") or "").strip()
        theme = d.get("primary_theme") or "—"
        cofog = d.get("primary_theme_cofog") or "—"
        lines.append(f"#### {did} — {topic}")
        if headline:
            lines.append(f"- **Headline:** {headline}")
        if statement:
            lines.append(f"- **Decision:** {statement}")
        lines.append(f"- **Theme:** {theme} ({cofog})")
        rationale = (d.get("primary_theme_rationale") or "").strip()
        if rationale:
            lines.append(f"- **Why this theme:** {rationale}")
        vote = d.get("vote") or d.get("vote_result")
        if vote:
            lines.append(f"- **Vote:** {vote}")
        lines.extend(_format_playback_markdown(d))
        lines.append("")
    return "\n".join(lines)


def _gather_meeting_artifacts(
    meeting_dir: Path,
    *,
    raw_root: Path,
    gemma_json_root: Path,
    summaries_root: Path,
    jurisdiction_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Collect paths and parsed JSON for one ``meetings/{date}/{slug}/`` folder."""
    rel = _rel_under(raw_root, meeting_dir)
    out: Dict[str, Any] = {
        "meeting_dir": rel,
        "meeting_path": meeting_dir.resolve(),
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
        "thoughts_md": [],
        "meeting_brief": None,
        "pdfs_from_jurisdiction_root": 0,
    }
    for sub, key in (("agenda", "agenda_pdfs"), ("minutes", "minutes_pdfs")):
        d = meeting_dir / sub
        if d.is_dir():
            out[key] = sorted(d.glob("*.pdf"))

    if jurisdiction_root is not None:
        flat_agenda, flat_minutes = _flat_pdfs_for_meeting(meeting_dir, jurisdiction_root)
        seen = {p.resolve() for p in out["agenda_pdfs"] + out["minutes_pdfs"]}
        for p in flat_agenda:
            if p.resolve() not in seen:
                out["agenda_pdfs"].append(p)
                seen.add(p.resolve())
        for p in flat_minutes:
            if p.resolve() not in seen:
                out["minutes_pdfs"].append(p)
                seen.add(p.resolve())
        out["pdfs_from_jurisdiction_root"] = len(flat_agenda) + len(flat_minutes)

    av = meeting_dir / "audio"
    if av.is_dir():
        out["audio_video"] = sorted(
            p for p in av.rglob("*") if p.is_file() and p.suffix.lower() in _MEDIA_EXTS
        )

    if jurisdiction_root is not None:
        for p in _flat_recordings_for_meeting(meeting_dir, jurisdiction_root):
            if p.resolve() not in {x.resolve() for x in out["audio_video"]}:
                out["audio_video"].append(p)

    brief_path = meeting_dir / "meeting_brief.txt"
    if brief_path.is_file():
        out["meeting_brief"] = brief_path

    for pdf in out["agenda_pdfs"] + out["minutes_pdfs"]:
        label = _doc_label(pdf)
        stem = mirror_output_path(
            input_path=pdf,
            raw_root=raw_root,
            processed_root=gemma_json_root,
            suffix=".thinking.json",
        )
        if stem.is_file():
            data = read_json_file(stem) or {}
            out["demo3"].append(
                {"pdf": pdf, "label": label, "json_path": stem, "analysis": data}
            )
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
            out["human_summaries"].append({"path": sm, "label": label})

        thoughts = mirror_output_path(
            input_path=pdf,
            raw_root=raw_root,
            processed_root=gemma_json_root,
            suffix=".thinking.thoughts.md",
        )
        if thoughts.is_file():
            out["thoughts_md"].append({"path": thoughts, "label": label})

    for media in out["audio_video"]:
        per = mirror_output_path(
            input_path=media,
            raw_root=raw_root,
            processed_root=gemma_json_root,
            suffix="",
        )
        for chunk_path in _find_under(per, "chunk_*.json"):
            chunk_data = read_json_file(chunk_path) or {}
            out["demo4_chunks"].append({"path": chunk_path, "data": chunk_data})
        drift = per / "policy_drift.json"
        if drift.is_file() and out["drift_json"] is None:
            out["drift_json"] = drift
        mmd = per / "policy_drift.mmd"
        if mmd.is_file() and out["drift_mmd"] is None:
            out["drift_mmd"] = mmd
        out["transcripts"].extend(_find_under(per, "transcript.*.txt"))

    return out


def _read_text(path: Path, *, max_chars: int) -> str:
    try:
        body = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return f"_Could not read {path.name}_"
    if len(body) <= max_chars:
        return body
    return body[:max_chars] + "\n\n… _(truncated)_"


def _parse_brief_txt(path: Path) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            val = val.strip()
            if key and val:
                fields[key] = val
    except OSError:
        pass
    return fields


def resolve_meeting_identity(
    artifacts: Dict[str, Any],
    *,
    jurisdiction_label: str = "",
) -> Dict[str, Any]:
    """
    Best available meeting title / body / date for the judge summary.

    Priority: Demo 3 JSON → ``meeting_brief.txt`` → calendar folder name → audio JSON (flagged).
    """
    meeting_path = artifacts.get("meeting_path")
    date_from_folder = (
        _meeting_calendar_date(meeting_path) if isinstance(meeting_path, Path) else None
    )
    identity: Dict[str, Any] = {
        "title": "",
        "body": "",
        "date": date_from_folder or "",
        "location": jurisdiction_label.replace("/", ", ") if jurisdiction_label else "",
        "source": "unknown",
        "warnings": [],
    }

    for item in artifacts.get("demo3") or []:
        analysis = item.get("analysis") or {}
        meeting = analysis.get("meeting") if isinstance(analysis, dict) else {}
        if not isinstance(meeting, dict) or not (
            meeting.get("body_name") or meeting.get("meeting_title")
        ):
            continue
        identity["body"] = str(meeting.get("body_name") or identity["body"] or "").strip()
        identity["title"] = str(
            meeting.get("meeting_title") or meeting.get("body_name") or identity["title"] or ""
        ).strip()
        identity["date"] = str(meeting.get("meeting_date") or identity["date"] or "").strip()
        loc = meeting.get("location") or meeting.get("county") or meeting.get("city")
        if loc:
            identity["location"] = str(loc).strip()
        identity["source"] = "agenda_minutes_analysis"
        break

    brief = artifacts.get("meeting_brief")
    if isinstance(brief, Path) and brief.is_file():
        fields = _parse_brief_txt(brief)
        if identity["source"] != "agenda_minutes_analysis":
            identity["title"] = fields.get("meeting_title") or identity["title"]
            identity["body"] = fields.get("governing_body") or identity["body"]
            identity["date"] = fields.get("meeting_date") or identity["date"]
            if identity["title"] or identity["body"]:
                identity["source"] = "meeting_brief"
        elif not identity["title"]:
            identity["title"] = fields.get("meeting_title") or identity["title"]

    if not identity["title"] and identity["date"]:
        identity["title"] = f"Meeting {identity['date']}"
    if not identity["body"] and jurisdiction_label:
        parts = jurisdiction_label.split("/")
        if len(parts) >= 3:
            identity["body"] = f"{parts[1].title()} — {parts[2].replace('_', ' ').title()}"

    has_demo3 = bool(artifacts.get("demo3"))
    has_audio = bool(artifacts.get("demo4_chunks"))
    if has_audio and not has_demo3 and (artifacts.get("agenda_pdfs") or artifacts.get("minutes_pdfs")):
        identity["warnings"].append(
            "Agenda/minutes PDFs are on file but were not analyzed (Demo 3). "
            "Names, body, and location below may be wrong if taken from audio only. "
            "Re-run §6 with scope `all` or `GOVERNANCE_RUN_DEMO3_WITH_VIDEO=1` (default)."
        )
    elif has_audio and not has_demo3:
        identity["warnings"].append(
            "Audio analysis only — no agenda/minutes policy JSON. "
            "Verify body name, officials, and location against source PDFs."
        )

    return identity


def _collect_all_decisions(artifacts: Dict[str, Any]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for item in artifacts.get("demo3") or []:
        analysis = item.get("analysis") or {}
        for d in analysis.get("decisions") or []:
            if not isinstance(d, dict):
                continue
            did = str(d.get("decision_id") or "")
            key = did or str(d.get("topic") or len(out))
            if key in seen:
                continue
            seen.add(key)
            out.append(d)
    for entry in artifacts.get("demo4_chunks") or []:
        analysis = (entry.get("data") or {}).get("json_analysis")
        if not isinstance(analysis, dict):
            continue
        for d in analysis.get("decisions") or []:
            if not isinstance(d, dict):
                continue
            did = str(d.get("decision_id") or "")
            key = f"audio:{did or d.get('topic') or len(out)}"
            if key in seen:
                continue
            seen.add(key)
            out.append(d)
    return out


def build_judge_summary_markdown(
    artifacts: Dict[str, Any],
    *,
    jurisdiction_label: str = "",
) -> str:
    """Judge-facing narrative: no pipeline jargon or raw model chunk dumps."""
    identity = resolve_meeting_identity(artifacts, jurisdiction_label=jurisdiction_label)
    title = identity.get("title") or "Meeting summary"
    body = identity.get("body") or "Governing body"
    date_s = identity.get("date") or "Date unknown"
    location = identity.get("location") or ""

    lines: List[str] = [
        f"# {title}",
        "",
        f"**{body}** · {date_s}"
        + (f" · {location}" if location else ""),
        "",
    ]
    for w in identity.get("warnings") or []:
        lines.append(f"> ⚠ {w}")
        lines.append("")

    drift = (
        read_json_file(artifacts["drift_json"])
        if artifacts.get("drift_json")
        else None
    )
    mls = (drift or {}).get("meeting_level_summary") or {} if isinstance(drift, dict) else {}
    if mls.get("headline"):
        lines.append("## At a glance")
        lines.append("")
        lines.append(f"**{mls['headline']}**")
        lines.append("")
    if mls.get("summary"):
        lines.append(str(mls["summary"]).strip())
        lines.append("")

    all_decisions = _collect_all_decisions(artifacts)
    meeting_meta: Dict[str, Any] = {}
    all_people: List[Any] = []
    for item in artifacts.get("demo3") or []:
        analysis = item.get("analysis") or {}
        meeting = analysis.get("meeting") if isinstance(analysis, dict) else {}
        if isinstance(meeting, dict) and meeting and not meeting_meta:
            meeting_meta = meeting
        for p in analysis.get("people") or []:
            if isinstance(p, dict):
                all_people.append(p)

    if all_decisions:
        lines.append(format_theme_audit_markdown(audit_decision_themes(all_decisions)))
        lines.append(
            format_decisions_markdown(all_decisions, heading="Decisions (agenda, minutes, and recording)")
        )
    elif artifacts.get("audio_video"):
        lines.append("## Decisions")
        lines.append("")
        lines.append(
            "_No structured decisions in Demo 3/4 JSON yet. See technical manifest or re-run §6._"
        )
        lines.append("")

    if meeting_meta or all_people:
        lines.append(format_people_markdown(meeting_meta, all_people))
    elif isinstance(artifacts.get("meeting_brief"), Path) and artifacts["meeting_brief"].is_file():
        brief_fields = _parse_brief_txt(artifacts["meeting_brief"])
        names = brief_fields.get("individual_names", "")
        if names:
            lines.append("## People (from agenda + minutes brief)")
            lines.append("")
            lines.append(names)
            lines.append("")

    subjects = []
    if isinstance(drift, dict):
        subjects = drift.get("subjects") or drift.get("drifted_subjects") or []
    if subjects or mls.get("emergent_value_tensions"):
        lines.append("## Themes across the recording")
        lines.append("")
        tensions = mls.get("emergent_value_tensions") or []
        if tensions:
            lines.append("- **Tensions:** " + "; ".join(str(t) for t in tensions[:12]))
        for s in subjects[:12]:
            if not isinstance(s, dict):
                continue
            label = s.get("subject_label") or s.get("subject_id") or "subject"
            headline = (s.get("drift_headline") or s.get("drift_summary") or "").strip()
            narrative = (s.get("narrative_summary") or s.get("summary") or "").strip()
            text = headline or narrative
            if text:
                lines.append(f"- **{label}:** {text[:1200]}")
        lines.append("")

    doc_lines: List[str] = []
    for p in artifacts.get("agenda_pdfs") or []:
        doc_lines.append(f"- Agenda: `{p.name}`")
    for p in artifacts.get("minutes_pdfs") or []:
        doc_lines.append(f"- Minutes: `{p.name}`")
    for p in artifacts.get("audio_video") or []:
        doc_lines.append(f"- Recording: `{p.name}`")
    if doc_lines:
        lines.append("## Source documents")
        lines.append("")
        lines.extend(doc_lines)
        lines.append("")

    lines.append(
        "_Pipeline status, chunk file paths, and troubleshooting: "
        "see companion file `_meeting_summary_technical.md` in this folder._"
    )
    lines.append("")
    return "\n".join(lines)


def build_technical_manifest_markdown(artifacts: Dict[str, Any]) -> str:
    """Operator-facing: counts, gaps, file paths, and full Demo 3/4 artifacts."""
    max_body = int(os.environ.get("GOVERNANCE_CONSOLIDATED_MAX_CHARS", "80000"))
    meeting_dir = artifacts.get("meeting_dir", "")

    lines: List[str] = [
        f"# Technical manifest — `{meeting_dir}`",
        "",
        "Pipeline inventory for this session. The judge-facing summary is "
        "`_meeting_summary.md` in this folder.",
        "",
        "## Sources on disk",
        "",
        f"- **Agenda PDFs:** {len(artifacts.get('agenda_pdfs') or [])}",
        f"- **Minutes PDFs:** {len(artifacts.get('minutes_pdfs') or [])}",
        f"- **Audio / video:** {len(artifacts.get('audio_video') or [])}",
        f"- **Demo 3 analyses:** {len(artifacts.get('demo3') or [])}",
        f"- **Demo 4 chunks:** {len(artifacts.get('demo4_chunks') or [])}",
        f"- **Transcripts (Demo 4a / §9a):** {len(artifacts.get('transcripts') or [])}",
        "",
    ]
    n_flat = int(artifacts.get("pdfs_from_jurisdiction_root") or 0)
    if n_flat:
        lines.append(
            f"- **Layout:** {n_flat} PDF(s) still referenced from county root "
            f"(organize moves them into `meetings/…/session/agenda|minutes/` on §6)"
        )
        lines.append("")

    missing: List[str] = []
    if artifacts.get("agenda_pdfs") and not any(
        (i.get("label") == "Agenda" for i in (artifacts.get("demo3") or []))
    ):
        missing.append("agenda PDF present but no Demo 3 analysis for it")
    if artifacts.get("minutes_pdfs") and not any(
        (i.get("label") == "Minutes" for i in (artifacts.get("demo3") or []))
    ):
        missing.append("minutes PDF present but no Demo 3 analysis")
    if artifacts.get("audio_video") and not artifacts.get("demo4_chunks"):
        missing.append("recording present but no Demo 4 chunk JSON")
    if artifacts.get("demo4_chunks") and not artifacts.get("drift_json"):
        missing.append("chunks exist but no `policy_drift.json`")
    if artifacts.get("audio_video") and not artifacts.get("transcripts"):
        missing.append(
            "no `transcript.en.txt` — optional notebook §9a (Demo 4a); not run in §6"
        )
    if missing:
        lines.append("## Gaps")
        lines.append("")
        for m in missing:
            lines.append(f"- ⚠ {m}")
        lines.append("")

    return build_consolidated_summary_markdown(artifacts, _lines_prefix=lines, max_body=max_body)


def build_consolidated_summary_markdown(
    artifacts: Dict[str, Any],
    *,
    _lines_prefix: Optional[List[str]] = None,
    max_body: Optional[int] = None,
) -> str:
    max_body = max_body if max_body is not None else int(
        os.environ.get("GOVERNANCE_CONSOLIDATED_MAX_CHARS", "80000")
    )

    lines: List[str] = list(_lines_prefix or [])

    brief = artifacts.get("meeting_brief")
    if brief and isinstance(brief, Path) and brief.is_file():
        lines.append("## Meeting brief (agenda + minutes → names & topics)")
        lines.append("")
        lines.append(_read_text(brief, max_chars=min(8000, max_body // 10)))
        lines.append("")

    all_decisions: List[Dict[str, Any]] = []
    meeting_meta: Dict[str, Any] = {}
    all_people: List[Any] = []

    for item in artifacts.get("demo3") or []:
        analysis = item.get("analysis") or {}
        if not isinstance(analysis, dict):
            continue
        meeting = analysis.get("meeting") if isinstance(analysis.get("meeting"), dict) else {}
        if meeting and not meeting_meta:
            meeting_meta = meeting
        people = analysis.get("people") or []
        if isinstance(people, list):
            all_people.extend(people)
        decisions = analysis.get("decisions") or []
        if isinstance(decisions, list):
            all_decisions.extend(decisions)

    if meeting_meta or all_people:
        lines.append("## Meeting metadata")
        lines.append("")
        if meeting_meta:
            lines.append(
                f"- **Body:** {meeting_meta.get('body_name') or '—'} | "
                f"**Date:** {meeting_meta.get('meeting_date') or '—'} | "
                f"**Type:** {meeting_meta.get('meeting_type') or '—'}"
            )
            loc = meeting_meta.get("location")
            if loc:
                lines.append(f"- **Location:** {loc}")
        lines.append("")
        lines.append(format_people_markdown(meeting_meta, all_people))

    if all_decisions:
        lines.append(format_theme_audit_markdown(audit_decision_themes(all_decisions)))
        lines.append(format_decisions_markdown(all_decisions, heading="All decisions (agenda + minutes)"))

    for item in artifacts.get("demo3") or []:
        pdf = item.get("pdf")
        label = item.get("label") or "PDF"
        analysis = item.get("analysis") or {}
        lines.append(f"## Policy analysis — {label}: `{pdf.name if pdf else '?'}`")
        lines.append("")
        meeting = analysis.get("meeting") if isinstance(analysis, dict) else {}
        if isinstance(meeting, dict) and meeting.get("body_name"):
            lines.append(
                f"- **Body:** {meeting.get('body_name')} | "
                f"**Modality:** {meeting.get('input_modality') or '—'}"
            )
            lines.append("")
        decisions = analysis.get("decisions") if isinstance(analysis, dict) else []
        if isinstance(decisions, list) and decisions:
            lines.append(
                format_decisions_markdown(decisions, heading=f"Decisions ({label})")
            )

    for entry in artifacts.get("human_summaries") or []:
        sm = entry.get("path")
        label = entry.get("label") or "PDF"
        lines.append(f"## Narrative summary — {label} (Demo 3 markdown)")
        lines.append("")
        if sm and isinstance(sm, Path):
            lines.append(_read_text(sm, max_chars=max_body // 4))
        lines.append("")

    for entry in artifacts.get("thoughts_md") or []:
        th = entry.get("path")
        label = entry.get("label") or "PDF"
        lines.append(f"## Reasoning trace — {label} (Demo 3 thinking)")
        lines.append("")
        if th and isinstance(th, Path):
            lines.append(_read_text(th, max_chars=max_body // 6))
        lines.append("")

    media_sources: List[Dict[str, Any]] = []
    for entry in artifacts.get("demo4_chunks") or []:
        analysis = (entry.get("data") or {}).get("json_analysis")
        if isinstance(analysis, dict):
            meeting = analysis.get("meeting")
            if isinstance(meeting, dict):
                for src in meeting.get("media_sources") or []:
                    if isinstance(src, dict) and src not in media_sources:
                        media_sources.append(src)
    if media_sources:
        lines.append("## Recordings (playback sources)")
        lines.append("")
        for src in media_sources:
            ms_id = src.get("media_source_id") or "—"
            plat = src.get("platform") or "—"
            canon = (src.get("canonical_url") or "").strip()
            page = (src.get("page_url") or "").strip()
            lines.append(f"- **{ms_id}** ({plat})")
            if canon:
                lines.append(f"  - Stream: [{canon}]({canon})")
            if page and page != canon:
                lines.append(f"  - Event page: [{page}]({page})")
        lines.append(
            "_Per-decision **[Jump to HH:MM](url)** links appear below when Demo 4 "
            "returned ``timestamp_start`` in ``media_citation``._"
        )
        lines.append("")

    if artifacts.get("demo4_chunks"):
        lines.append("## Audio / video — chunk analyses (Demo 4)")
        lines.append("")
        for entry in artifacts.get("demo4_chunks") or []:
            chunk_path = entry.get("path")
            data = entry.get("data") or {}
            idx = data.get("chunk_index", "?")
            lines.append(f"### Chunk {idx} — `{chunk_path.name if chunk_path else '?'}`")
            lines.append("")
            analysis = data.get("json_analysis")
            if isinstance(analysis, dict):
                ch_decisions = analysis.get("decisions") or []
                if ch_decisions:
                    lines.append(
                        format_decisions_markdown(
                            ch_decisions,
                            heading=f"Decisions in chunk {idx}",
                        )
                    )
                ch_people = analysis.get("people") or []
                if ch_people:
                    ch_meeting = analysis.get("meeting") if isinstance(analysis.get("meeting"), dict) else {}
                    lines.append(format_people_markdown(ch_meeting, ch_people))
            elif data.get("parse_error"):
                lines.append(f"_Parse error: {data.get('parse_error')}_")
            lines.append("")

    if artifacts.get("drift_json"):
        drift = read_json_file(artifacts["drift_json"]) or {}
        mls = drift.get("meeting_level_summary") or {}
        lines.append("## Audio / video — policy drift (Demo 4 consolidated)")
        lines.append("")
        if mls.get("headline"):
            lines.append(f"**{mls['headline']}**")
            lines.append("")
        if mls.get("summary"):
            lines.append(str(mls["summary"]))
            lines.append("")
        lines.append(
            f"- Subjects tracked: {mls.get('subjects_tracked', '—')} | "
            f"with drift: {mls.get('subjects_with_drift', '—')}"
        )
        tensions = mls.get("emergent_value_tensions") or []
        if tensions:
            lines.append("- Emergent tensions: " + "; ".join(str(t) for t in tensions[:12]))
        subjects = drift.get("subjects") or drift.get("drifted_subjects") or []
        for s in subjects[:12]:
            if not isinstance(s, dict):
                continue
            label = s.get("subject_label") or s.get("subject_id") or "subject"
            narrative = (s.get("narrative_summary") or s.get("summary") or "").strip()
            if narrative:
                lines.append(f"\n**{label}:** {narrative[:2000]}")
        lines.append("")

    if artifacts.get("drift_mmd"):
        lines.append("## Mermaid — narrative drift timelines")
        lines.append("")
        lines.append(
            f"Full diagram: `{artifacts['drift_mmd'].name}` "
            "(copied next to this summary). Paste into https://mermaid.live"
        )
        lines.append("")
        lines.append("```mermaid")
        lines.append(_read_text(artifacts["drift_mmd"], max_chars=20_000))
        lines.append("```")
        lines.append("")

    for tr in artifacts.get("transcripts") or []:
        lines.append(f"## Transcript — `{tr.name}`")
        lines.append("")
        lines.append(_read_text(tr, max_chars=max_body // 5))
        lines.append("")

    return "\n".join(lines)


def _ensure_meeting_brief(
    meeting_dir: Path,
    *,
    jurisdiction_root: Optional[Path],
    api_key: str,
    genai_model: str,
) -> None:
    if not api_key or not genai_model:
        return
    brief_path = meeting_dir / "meeting_brief.txt"
    if brief_path.is_file() and len(brief_path.read_text(encoding="utf-8").strip()) > 80:
        return
    try:
        from .meeting_grouping import build_meeting_collateral_brief, collect_meeting_pdf_texts
    except ImportError:
        return
    agenda, minutes = collect_meeting_pdf_texts(
        meeting_dir, jurisdiction_root=jurisdiction_root
    )
    if not agenda and not minutes:
        return
    build_meeting_collateral_brief(
        meeting_dir,
        api_key=api_key,
        model=genai_model,
        jurisdiction_root=jurisdiction_root,
    )


def write_meeting_consolidated_summary(
    meeting_dir: Path,
    *,
    raw_root: Path,
    gemma_json_root: Path,
    summaries_root: Path,
    jurisdiction_root: Optional[Path] = None,
    jurisdiction_label: str = "",
    api_key: str = "",
    genai_model: str = "",
) -> Tuple[Path, Optional[Path]]:
    """Write judge ``_meeting_summary.md`` + operator ``_meeting_summary_technical.md``."""
    _ensure_meeting_brief(
        meeting_dir,
        jurisdiction_root=jurisdiction_root,
        api_key=api_key,
        genai_model=genai_model,
    )
    artifacts = _gather_meeting_artifacts(
        meeting_dir,
        raw_root=raw_root,
        gemma_json_root=gemma_json_root,
        summaries_root=summaries_root,
        jurisdiction_root=jurisdiction_root,
    )
    judge_body = build_judge_summary_markdown(
        artifacts, jurisdiction_label=jurisdiction_label
    )
    technical_body = build_technical_manifest_markdown(artifacts)
    rel = Path(artifacts["meeting_dir"])
    out_dir = summaries_root / rel
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "_meeting_summary.md"
    technical_path = out_dir / "_meeting_summary_technical.md"
    summary_path.write_text(judge_body, encoding="utf-8")
    technical_path.write_text(technical_body, encoding="utf-8")

    if os.environ.get("GOVERNANCE_CONSOLIDATED_SUMMARY_IN_RAW", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    ):
        (meeting_dir / "_meeting_summary.md").write_text(judge_body, encoding="utf-8")
        (meeting_dir / "_meeting_summary_technical.md").write_text(
            technical_body, encoding="utf-8"
        )

    mmd_copy: Optional[Path] = None
    src_mmd = artifacts.get("drift_mmd")
    if src_mmd and src_mmd.is_file():
        mmd_copy = out_dir / "policy_drift.mmd"
        shutil.copy2(src_mmd, mmd_copy)
        if os.environ.get("GOVERNANCE_CONSOLIDATED_SUMMARY_IN_RAW", "1").strip().lower() not in (
            "0",
            "false",
            "no",
        ):
            shutil.copy2(src_mmd, meeting_dir / "policy_drift.mmd")
    return summary_path, mmd_copy


def run_consolidated_summaries_for_jurisdiction(
    *,
    jurisdiction_root: Path,
    raw_root: Path,
    gemma_json_root: Path,
    summaries_root: Path,
    jurisdiction_prefix: str = "",
    api_key: str = "",
    genai_model: str = "",
) -> List[Path]:
    """Build one consolidated summary per ``meetings/{date}/{slug}/`` session."""
    if os.environ.get("GOVERNANCE_CONSOLIDATED_SUMMARY", "1").strip().lower() in (
        "0",
        "false",
        "no",
    ):
        return []
    try:
        from .meeting_grouping import (
            iter_meeting_dirs,
            jurisdiction_prefix_from_relative,
            repair_duplicate_date_session_folders,
        )
    except ImportError:
        return []

    try:
        rel = jurisdiction_root.resolve().relative_to(raw_root.resolve())
        jur_prefix = jurisdiction_prefix or rel.as_posix()
    except ValueError:
        jur_prefix = jurisdiction_prefix or jurisdiction_prefix_from_relative(
            str(jurisdiction_root)
        )

    repair_duplicate_date_session_folders(raw_root, jur_prefix)

    written: List[Path] = []
    for meeting_dir in iter_meeting_dirs(raw_root, jur_prefix):
        summary_path, _ = write_meeting_consolidated_summary(
            meeting_dir,
            raw_root=raw_root,
            gemma_json_root=gemma_json_root,
            summaries_root=summaries_root,
            jurisdiction_root=jurisdiction_root,
            jurisdiction_label=jur_prefix,
            api_key=api_key,
            genai_model=genai_model,
        )
        written.append(summary_path)
        raw_copy = meeting_dir / "_meeting_summary.md"
        dest = raw_copy if raw_copy.is_file() else summary_path
        tech = meeting_dir / "_meeting_summary_technical.md"
        print(
            f"  → judge summary: {dest.relative_to(raw_root)} "
            f"(mirror: {summary_path.relative_to(summaries_root)})",
            flush=True,
        )
        if tech.is_file():
            print(
                f"  → technical manifest: {tech.relative_to(raw_root)}",
                flush=True,
            )
    return written
