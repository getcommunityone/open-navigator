"""
Pipeline modality scope: run PDF demos, audio-only Demo 4, or video Demo 4.

Set ``GOVERNANCE_PIPELINE_MEDIA_SCOPE`` (or pass to :func:`apply_media_scope`):

- ``all`` — Demos 1–4 on full inventory (default when unset in library code)
- ``pdf`` / ``pdf_only`` — Demos 1–3 only; no recordings
- ``audio`` / ``audio_only`` — Demo 4 on ``.mp3`` / ``.opus`` / … (not ``.mp4``)
- ``video`` / ``video_only`` — Demo 4 on video containers only; enables ``GOVERNANCE_DEMO4_VIDEO_CHUNKS=1``
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from governance_meeting_llm import (
    AUDIO_EXTS,
    PDF_EXTS,
    VIDEO_EXTS,
    MeetingInventory,
    format_inventory_media_line,
)

ENV_KEY = "GOVERNANCE_PIPELINE_MEDIA_SCOPE"


@dataclass(frozen=True)
class MediaScopeConfig:
    key: str
    label: str
    includes_pdf: bool
    includes_pure_audio: bool
    includes_video: bool
    run_demo1: bool
    run_demo2: bool
    run_demo3: bool
    run_demo4: bool
    gatekeeper_kinds: Tuple[str, ...]
    force_demo4_video_chunks: bool | None = None  # None = leave env unchanged


SCOPES: dict[str, MediaScopeConfig] = {
    "all": MediaScopeConfig(
        key="all",
        label="All modalities (PDF + audio + video)",
        includes_pdf=True,
        includes_pure_audio=True,
        includes_video=True,
        run_demo1=True,
        run_demo2=True,
        run_demo3=True,
        run_demo4=True,
        gatekeeper_kinds=("pdf", "audio"),
    ),
    "pdf": MediaScopeConfig(
        key="pdf",
        label="PDF only (Demos 1–3; no Demo 4)",
        includes_pdf=True,
        includes_pure_audio=False,
        includes_video=False,
        run_demo1=True,
        run_demo2=True,
        run_demo3=True,
        run_demo4=False,
        gatekeeper_kinds=("pdf",),
    ),
    "audio": MediaScopeConfig(
        key="audio",
        label="Audio only (Demo 4 on .mp3/.opus/…; no PDF demos)",
        includes_pdf=False,
        includes_pure_audio=True,
        includes_video=False,
        run_demo1=False,
        run_demo2=False,
        run_demo3=False,
        run_demo4=True,
        gatekeeper_kinds=("audio",),
        force_demo4_video_chunks=False,
    ),
    "video": MediaScopeConfig(
        key="video",
        label="Video only (Demo 4 on .mp4/… with video/mp4 chunks)",
        includes_pdf=False,
        includes_pure_audio=False,
        includes_video=True,
        run_demo1=False,
        run_demo2=False,
        run_demo3=False,
        run_demo4=True,
        gatekeeper_kinds=("audio",),  # gatekeeper walks AUDIO_EXTS; we filter to VIDEO_EXTS
        force_demo4_video_chunks=True,
    ),
}


_ALIASES = {
    "pdf_only": "pdf",
    "pdfs": "pdf",
    "audio_only": "audio",
    "recordings": "audio",
    "video_only": "video",
    "videos": "video",
    "mp4": "video",
}


def normalize_media_scope_key(raw: str) -> str:
    key = (raw or "all").strip().lower()
    key = _ALIASES.get(key, key)
    return key if key in SCOPES else "all"


def get_active_media_scope() -> MediaScopeConfig:
    return SCOPES[normalize_media_scope_key(os.environ.get(ENV_KEY, "all"))]


def path_matches_media_scope(path: Path, scope: MediaScopeConfig) -> bool:
    ext = path.suffix.lower()
    if ext in PDF_EXTS:
        return scope.includes_pdf
    if ext in VIDEO_EXTS:
        return scope.includes_video
    if ext in AUDIO_EXTS:
        return scope.includes_pure_audio
    return False


def filter_paths_for_media_scope(
    paths: Iterable[Path],
    scope: MediaScopeConfig | None = None,
) -> List[Path]:
    scope = scope or get_active_media_scope()
    return [p for p in paths if path_matches_media_scope(p, scope)]


def split_inventory_media(
    pdfs: Sequence[Path],
    audio: Sequence[Path],
    scope: MediaScopeConfig | None = None,
) -> Tuple[List[Path], List[Path]]:
    """Return ``(pdfs, audio)`` lists filtered for the active scope."""
    scope = scope or get_active_media_scope()
    out_pdfs = [p for p in pdfs if scope.includes_pdf]
    out_audio: List[Path] = []
    for p in audio:
        ext = p.suffix.lower()
        if ext in VIDEO_EXTS and scope.includes_video:
            out_audio.append(p)
        elif ext not in VIDEO_EXTS and scope.includes_pure_audio:
            out_audio.append(p)
    return out_pdfs, out_audio


def apply_media_scope_to_inventory(
    inv: MeetingInventory,
    scope: MediaScopeConfig | None = None,
) -> MeetingInventory:
    scope = scope or get_active_media_scope()
    inv.pdfs, inv.audio = split_inventory_media(inv.pdfs, inv.audio, scope)
    return inv


def apply_media_scope_to_environ(scope_key: str) -> MediaScopeConfig:
    """Set ``GOVERNANCE_PIPELINE_MEDIA_SCOPE`` and related env for Gatekeeper / Demo 4."""
    scope = SCOPES[normalize_media_scope_key(scope_key)]
    os.environ[ENV_KEY] = scope.key
    os.environ["GOVERNANCE_GATEKEEPER_KINDS"] = ",".join(scope.gatekeeper_kinds)
    if scope.force_demo4_video_chunks is True:
        os.environ["GOVERNANCE_DEMO4_VIDEO_CHUNKS"] = "1"
    elif scope.force_demo4_video_chunks is False:
        os.environ["GOVERNANCE_DEMO4_VIDEO_CHUNKS"] = "0"
    return scope


def apply_media_scope(scope_key: str) -> MediaScopeConfig:
    """Validate scope, push env, return config (call from notebook §2)."""
    return apply_media_scope_to_environ(scope_key)


def inventory_richness_for_scope(inv: MeetingInventory, scope_key: str) -> Tuple[int, int, int]:
    """Sort key helper: ``(primary, secondary, tertiary)`` higher is richer."""
    scope = SCOPES[normalize_media_scope_key(scope_key)]
    n_video = sum(1 for p in inv.audio if p.suffix.lower() in VIDEO_EXTS)
    n_audio = len(inv.audio) - n_video
    n_pdf = len(inv.pdfs)
    if scope.key == "video":
        return (n_video, n_audio, n_pdf)
    if scope.key == "audio":
        return (n_audio, n_video, n_pdf)
    if scope.key == "pdf":
        return (n_pdf, n_video, n_audio)
    return (n_pdf + n_video + n_audio, n_video, n_pdf)


def print_media_scope_banner(scope: MediaScopeConfig | None = None) -> None:
    scope = scope or get_active_media_scope()
    demos = []
    if scope.run_demo1:
        demos.append("1")
    if scope.run_demo2:
        demos.append("2")
    if scope.run_demo3:
        demos.append("3")
    if scope.run_demo4:
        demos.append("4")
    demo_s = ",".join(demos) if demos else "none"
    print(
        f"  Media scope: {scope.key!r} — {scope.label} "
        f"(Demos {demo_s}; Gatekeeper kinds: {','.join(scope.gatekeeper_kinds)})",
        flush=True,
    )
    if scope.force_demo4_video_chunks is True:
        print("  Demo 4: GOVERNANCE_DEMO4_VIDEO_CHUNKS=1 (video/mp4 segments)", flush=True)
    elif scope.force_demo4_video_chunks is False:
        print("  Demo 4: GOVERNANCE_DEMO4_VIDEO_CHUNKS=0 (audio/mp3 chunks)", flush=True)


def demo4_step_label(scope: MediaScopeConfig | None = None) -> str:
    """Short label for ``timed_step`` (not the ffmpeg/API detail)."""
    scope = scope or get_active_media_scope()
    if scope.key == "video":
        return "Demo 4 video recordings"
    if scope.key == "audio":
        return "Demo 4 audio recordings"
    return "Demo 4 meeting recordings"


def describe_demo4_file(path: Path, *, demo4_model: str) -> str:
    """
    Explain how a file is fed to Demo 4 (accurate for logs).

    ``GOVERNANCE_DEMO4_VIDEO_CHUNKS=1`` only sends ``video/mp4`` bytes when the
    model accepts video (Gemini). Gemma 4 on AI Studio uses **audio extracted**
    from MP4 via ffmpeg — still a video *source*, not native video modality.
    """
    from governance_meeting_llm import (
        VIDEO_EXTS,
        demo4_use_video_chunks,
        model_supports_video_input,
    )

    is_video_file = path.suffix.lower() in VIDEO_EXTS
    use_video_api = (
        is_video_file
        and demo4_use_video_chunks()
        and model_supports_video_input(demo4_model)
    )
    if use_video_api:
        return "video/mp4 segments → Gemma"
    if is_video_file:
        return "MP4 → 15‑min audio slices → Gemma (audio modality on this model)"
    return "15‑min audio slices → Gemma"


def print_scoped_inventory_line(inv: MeetingInventory, scope: MediaScopeConfig | None = None) -> None:
    scope = scope or get_active_media_scope()
    print(
        f"  Scoped inventory ({scope.key}): {format_inventory_media_line(inv)}",
        flush=True,
    )
