"""
Print a judge-friendly index of pipeline outputs (paths + optional Colab FileLink).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class OutputArtifact:
    kind: str
    path: Path
    rel: str


def _rel_to(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _scan_glob(root: Path, pattern: str, *, kind: str) -> List[OutputArtifact]:
    if not root.is_dir():
        return []
    out: List[OutputArtifact] = []
    for p in sorted(root.glob(pattern)):
        if p.is_file():
            out.append(OutputArtifact(kind=kind, path=p, rel=_rel_to(root, p)))
    return out


def collect_pipeline_outputs(
    *,
    pipe_root: Path,
    gemma_json_root: Path,
    summaries_root: Path,
    jurisdiction_prefixes: Optional[Sequence[str]] = None,
) -> List[OutputArtifact]:
    """Key artifacts under ``03_processed_outputs`` (newest paths first per kind)."""
    pipe_root = pipe_root.resolve()
    found: List[OutputArtifact] = []

    for p in sorted(summaries_root.rglob("_meeting_summary.md")):
        if p.name == "_meeting_summary_technical.md":
            continue
        if p.is_file():
            found.append(
                OutputArtifact(
                    kind="meeting_summary",
                    path=p,
                    rel=_rel_to(pipe_root, p),
                )
            )

    for p in sorted(summaries_root.rglob("_meeting_summary_technical.md")):
        if p.is_file():
            found.append(
                OutputArtifact(
                    kind="meeting_summary_technical",
                    path=p,
                    rel=_rel_to(pipe_root, p),
                )
            )

    for pattern, kind in (
        ("**/policy_drift.json", "policy_drift"),
        ("**/policy_drift.mmd", "policy_drift_mmd"),
        ("**/transcript.*.txt", "transcript"),
        ("**/chunk_*.json", "demo4_chunk"),
        ("**/*.thinking.json", "demo3_analysis"),
        ("**/*.thinking.summary.md", "demo3_summary"),
    ):
        for p in sorted(gemma_json_root.glob(pattern)):
            if not p.is_file():
                continue
            if jurisdiction_prefixes:
                rel = _rel_to(gemma_json_root, p)
                if not any(rel.startswith(j) for j in jurisdiction_prefixes):
                    continue
            found.append(
                OutputArtifact(kind=kind, path=p, rel=_rel_to(pipe_root, p))
            )

    return found


def _drive_browse_hint(pipe_root: Path) -> str:
    root = pipe_root.resolve().as_posix()
    if "/content/drive/MyDrive/" in root:
        after = root.split("/content/drive/MyDrive/", 1)[1]
        return f"My Drive/{after}"
    return root


def _try_file_links(paths: Sequence[Path]) -> bool:
    """Display Colab/Jupyter FileLink rows when available."""
    try:
        from IPython.display import FileLink, display  # type: ignore
    except ImportError:
        return False
    for p in paths[:24]:
        if p.is_file():
            display(FileLink(str(p.resolve())))
    if len(paths) > 24:
        print(f"  … and {len(paths) - 24} more (see paths above)")
    return True


def print_pipeline_output_index(
    *,
    pipe_root: Path,
    gemma_json_root: Path,
    summaries_root: Path,
    jurisdiction_prefixes: Optional[Sequence[str]] = None,
    show_file_links: bool = True,
) -> None:
    """
    End-of-run cheat sheet: where outputs live and how to open them.

    Transcripts are written by optional Demo 4a (§9a) to
    ``02_gemma_json/…/transcript.{lang}.txt``, not ``01_transcripts/``.
    """
    pipe_root = pipe_root.resolve()
    artifacts = collect_pipeline_outputs(
        pipe_root=pipe_root,
        gemma_json_root=gemma_json_root,
        summaries_root=summaries_root,
        jurisdiction_prefixes=jurisdiction_prefixes,
    )

    by_kind: dict[str, List[OutputArtifact]] = {}
    for a in artifacts:
        by_kind.setdefault(a.kind, []).append(a)

    sep = "=" * 72
    print(f"\n{sep}", flush=True)
    print("PIPELINE OUTPUTS — open these paths", flush=True)
    print(sep, flush=True)
    print(f"Pipeline root:  {pipe_root}", flush=True)
    print(f"Drive browse:   {_drive_browse_hint(pipe_root)}", flush=True)
    print(f"Gemma JSON:     {gemma_json_root}", flush=True)
    print(f"Summaries:      {summaries_root}", flush=True)
    print(
        "Transcripts:    optional §9a → "
        f"{gemma_json_root.name}/…/transcript.en.txt "
        f"(folder {pipe_root / '03_processed_outputs' / '01_transcripts'} stays empty unless you copy files there)",
        flush=True,
    )
    print("", flush=True)

    order = (
        ("meeting_summary", "Meeting summaries for judges (start here)"),
        ("meeting_summary_technical", "Technical manifests (pipeline/debug)"),
        ("policy_drift", "Policy drift JSON"),
        ("policy_drift_mmd", "Mermaid drift diagrams"),
        ("transcript", "Plain transcripts (Demo 4a only)"),
        ("demo4_chunk", "Demo 4 chunk analyses"),
        ("demo3_analysis", "Demo 3 thinking JSON"),
        ("demo3_summary", "Demo 3 human summaries"),
    )
    link_paths: List[Path] = []
    any_written = False
    for kind, title in order:
        items = by_kind.get(kind) or []
        if not items:
            continue
        any_written = True
        print(f"## {title} ({len(items)})", flush=True)
        for a in items[:12]:
            print(f"  • {a.rel}", flush=True)
            link_paths.append(a.path)
        if len(items) > 12:
            print(f"  … +{len(items) - 12} more under {gemma_json_root.name}/ or summaries/", flush=True)
        print("", flush=True)

    if not any_written:
        print(
            "  (no processed artifacts found yet — check Demo 4 / scope / "
            "GOVERNANCE_PIPELINE_DATA_ROOT)",
            flush=True,
        )
        print(
            "  Expected after §6: "
            "03_human_summaries/…/meetings/…/session/_meeting_summary.md",
            flush=True,
        )
    elif not by_kind.get("transcript"):
        print(
            "ℹ️  Transcripts: count is 0 — §6 does not run Demo 4a. "
            "Run notebook §9a (or set GOVERNANCE_RUN_TRANSCRIPTION=1 when wired) "
            "with GPU/HF_TOKEN if using Hugging Face for audio.",
            flush=True,
        )
        print("", flush=True)

    if show_file_links and link_paths and os.environ.get("GOVERNANCE_OUTPUT_FILELINKS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    ):
        print("Click to open in Colab (FileLink):", flush=True)
        _try_file_links(link_paths)

    print(sep, flush=True)
