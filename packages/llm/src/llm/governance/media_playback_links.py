"""
Build deep links into meeting video/audio for policy analysis outputs.

Used by the Colab governance pipeline to pass canonical playback URLs into the
LLM prompt and to post-fill ``playback_url`` on each decision after parsing JSON.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_YOUTUBE_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:[^#]*&)?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)
_VIMEO_ID_RE = re.compile(r"vimeo\.com/(?:video/)?(\d+)")
_HHMM_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")


@dataclass(frozen=True)
class MediaSource:
    """One playable recording tied to a scraped meeting folder."""

    media_source_id: str
    platform: str
    canonical_url: str
    page_url: Optional[str] = None
    mime_type: Optional[str] = None
    is_primary: bool = True
    local_relative_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "media_source_id": self.media_source_id,
            "platform": self.platform,
            "canonical_url": self.canonical_url,
            "page_url": self.page_url,
            "mime_type": self.mime_type,
            "is_primary": self.is_primary,
            "local_relative_path": self.local_relative_path,
        }


def hhmm_to_seconds(value: Optional[str]) -> Optional[int]:
    """Parse ``HH:MM`` or ``H:MM:SS`` elapsed time to integer seconds."""
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    m = _HHMM_RE.match(s)
    if not m:
        return None
    h, mi, sec = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    return h * 3600 + mi * 60 + sec


def seconds_to_hhmm(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def detect_platform(url: str) -> str:
    u = (url or "").lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "vimeo.com" in u:
        return "vimeo"
    if "archive.org" in u:
        return "archive_org"
    if "suiteone" in u or "suiteonemedia" in u:
        return "suiteone_portal"
    if u.endswith(".mp4") or u.endswith(".m3u8") or ".mp4?" in u:
        return "direct_mp4"
    if u.endswith(".opus") or u.endswith(".mp3") or u.endswith(".m4a"):
        return "direct_audio"
    return "unknown"


def playback_url_at(
    *,
    canonical_url: str,
    platform: str,
    seconds: int,
    page_url: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """
    Return ``(playback_url, note)`` for jumping to ``seconds`` in the recording.

    ``note`` explains when the link is approximate or uses a portal page instead
    of a byte-offset into a file.
    """
    seconds = max(0, int(seconds))
    url = (canonical_url or "").strip()
    if not url:
        return "", "no canonical_url"

    plat = (platform or detect_platform(url)).lower()

    if plat == "youtube":
        m = _YOUTUBE_ID_RE.search(url)
        if m:
            vid = m.group(1)
            return (
                f"https://www.youtube.com/watch?v={vid}&t={seconds}s",
                None,
            )
        return url, "could not parse YouTube video id"

    if plat == "vimeo":
        m = _VIMEO_ID_RE.search(url)
        if m:
            vid = m.group(1)
            return (f"https://vimeo.com/{vid}#t={seconds}s", None)
        return url, "could not parse Vimeo id"

    if plat == "archive_org":
        base = url.split("#")[0].rstrip("/")
        return (f"{base}/start/{seconds}", None)

    if plat in ("suiteone_portal", "suiteone_s3_mp4"):
        portal = (page_url or "").strip()
        if portal and "suiteone" in portal.lower():
            return (
                portal,
                f"SuiteOne event page (seek to ~{seconds_to_hhmm(seconds)} in player; "
                "direct MP4 deep-link not supported)",
            )
        if seconds and url.lower().endswith(".mp4"):
            return (f"{url}#t={seconds}", "HTML5 fragment; player may ignore")
        return url, "no SuiteOne portal URL; use recording start"

    if plat in ("direct_mp4", "direct_audio", "unknown"):
        if seconds and ("." in url):
            return (f"{url}#t={seconds}", "fragment seek; depends on browser/player")
        return url, None

    return url, None


def _read_manifest(jurisdiction_root: Path) -> Dict[str, Any]:
    path = jurisdiction_root / "_manifest.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _sidecar_for_asset(jurisdiction_root: Path, sidecar_rel: str) -> Dict[str, Any]:
    path = jurisdiction_root / sidecar_rel
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _row_to_media_source(row: Dict[str, Any], index: int) -> Optional[MediaSource]:
    mp4 = (row.get("source_mp4_url") or row.get("url") or "").strip()
    page = (row.get("discovered_on") or row.get("discovered_on_page_url") or "").strip()
    platform = (row.get("platform") or detect_platform(mp4 or page)).strip()
    if not mp4 and not page:
        return None
    canonical = mp4 or page
    if platform == "suiteone_s3_mp4" and page:
        plat_out = "suiteone_s3_mp4"
    elif "suiteone" in (page or canonical).lower():
        plat_out = "suiteone_portal"
    else:
        plat_out = platform or detect_platform(canonical)
    local = row.get("opus_relative_path") or row.get("mp4_relative_path")
    return MediaSource(
        media_source_id=f"MS{index:03d}",
        platform=plat_out,
        canonical_url=canonical,
        page_url=page or None,
        mime_type="video/mp4" if mp4 and mp4.lower().endswith(".mp4") else None,
        is_primary=index == 1,
        local_relative_path=str(local).strip() if local else None,
    )


def list_media_sources(jurisdiction_root: Path) -> List[MediaSource]:
    """All video/audio sources declared in ``_manifest.json`` for a jurisdiction."""
    manifest = _read_manifest(jurisdiction_root)
    out: List[MediaSource] = []
    seen: set[str] = set()
    idx = 0
    for row in manifest.get("video_assets") or []:
        if not isinstance(row, dict):
            continue
        idx += 1
        src = _row_to_media_source(row, idx)
        if src and src.canonical_url not in seen:
            seen.add(src.canonical_url)
            out.append(src)
    for row in manifest.get("other_video_streams") or []:
        if not isinstance(row, dict):
            continue
        url = (row.get("url") or "").strip()
        if not url or url in seen:
            continue
        idx += 1
        src = _row_to_media_source(row, idx)
        if src:
            seen.add(src.canonical_url)
            out.append(src)
    for row in manifest.get("youtube") or []:
        if not isinstance(row, dict):
            continue
        url = (row.get("url") or "").strip()
        if not url or "watch" not in url and "youtu.be" not in url:
            continue
        if url in seen:
            continue
        idx += 1
        src = _row_to_media_source({"url": url, "platform": "youtube"}, idx)
        if src:
            seen.add(url)
            out.append(src)
    return out


def resolve_media_for_input_file(
    input_path: Path,
    jurisdiction_root: Path,
) -> Optional[MediaSource]:
    """
    Match a local ``.opus`` / ``.mp4`` / chunk file to one manifest ``video_assets`` row.
    """
    input_path = input_path.resolve()
    jurisdiction_root = jurisdiction_root.resolve()
    try:
        rel = input_path.relative_to(jurisdiction_root).as_posix()
    except ValueError:
        rel = input_path.name
    stem = input_path.stem
    manifest = _read_manifest(jurisdiction_root)
    for i, row in enumerate(manifest.get("video_assets") or [], start=1):
        if not isinstance(row, dict):
            continue
        opus = (row.get("opus_relative_path") or "").strip()
        mp4 = (row.get("mp4_relative_path") or "").strip()
        sidecar = (row.get("sidecar_relative_path") or "").strip()
        if rel == opus or rel == mp4 or stem in opus or stem in mp4:
            base = _row_to_media_source(row, i)
            if base:
                return MediaSource(
                    media_source_id=base.media_source_id,
                    platform=base.platform,
                    canonical_url=base.canonical_url,
                    page_url=base.page_url,
                    mime_type=base.mime_type,
                    is_primary=True,
                    local_relative_path=rel,
                )
        if sidecar:
            sc = _sidecar_for_asset(jurisdiction_root, sidecar)
            sc_opus = (sc.get("opus_relative_path") or "").strip()
            if rel == sc_opus or stem in sc_opus:
                merged = {**row, **sc}
                base = _row_to_media_source(merged, i)
                if base:
                    return MediaSource(
                        media_source_id=base.media_source_id,
                        platform=base.platform,
                        canonical_url=base.canonical_url,
                        page_url=base.page_url,
                        mime_type=base.mime_type,
                        is_primary=True,
                        local_relative_path=rel,
                    )
    # Fallback: first downloadable stream
    sources = list_media_sources(jurisdiction_root)
    return sources[0] if sources else None


def format_media_context_hint(
    *,
    primary: Optional[MediaSource],
    all_sources: Optional[List[MediaSource]] = None,
    input_modality: str = "unknown",
    chunk_index: Optional[int] = None,
    chunk_minutes: int = 15,
    local_file: Optional[Path] = None,
) -> str:
    """Block injected above the policy prompt when analyzing A/V."""
    lines = [
        "=== MEDIA CONTEXT (recording — use for timestamps and playback) ===",
        f"input_modality: {input_modality}",
    ]
    if local_file:
        lines.append(f"local_file: {local_file.name}")
    if chunk_index is not None:
        start_s = chunk_index * chunk_minutes * 60
        lines.append(f"chunk_index: {chunk_index} (0-based)")
        lines.append(f"chunk_start_seconds: {start_s} (elapsed from recording start)")
        lines.append(f"chunk_duration_seconds: {chunk_minutes * 60}")
        lines.append(
            "When this slice is a chunk of a longer file, decision timestamps must still "
            "use meeting elapsed time from the **recording start** (add chunk_start_seconds "
            "to any time heard only within this slice)."
        )
    if primary:
        lines.append(f"primary_media_source_id: {primary.media_source_id}")
        lines.append(f"platform: {primary.platform}")
        lines.append(f"canonical_url: {primary.canonical_url}")
        if primary.page_url:
            lines.append(f"page_url: {primary.page_url}")
    if all_sources and len(all_sources) > 1:
        lines.append("other_media_source_ids: " + ", ".join(s.media_source_id for s in all_sources))
    lines.append(
        "Set each decision's media_citation.media_source_id to the source where the action "
        "occurs. Use timestamp_start / timestamp_end as HH:MM elapsed from recording start. "
        "Do not invent playback_url — the pipeline fills it from timestamps."
    )
    lines.append("")
    return "\n".join(lines)


def enrich_policy_analysis_media_links(
    analysis: Dict[str, Any],
    *,
    primary: Optional[MediaSource],
    all_sources: Optional[List[MediaSource]] = None,
    chunk_start_seconds: int = 0,
) -> Dict[str, Any]:
    """Post-process Document 1 JSON: media_sources on meeting + playback URLs on decisions."""
    if not isinstance(analysis, dict) or not analysis:
        return analysis
    sources = all_sources or ([primary] if primary else [])
    meeting = analysis.setdefault("meeting", {})
    if sources and not meeting.get("media_sources"):
        meeting["media_sources"] = [s.to_dict() for s in sources]
    if primary and not meeting.get("primary_media_source_id"):
        meeting["primary_media_source_id"] = primary.media_source_id

    source_by_id = {s.media_source_id: s for s in sources}
    if primary:
        source_by_id.setdefault(primary.media_source_id, primary)

    for decision in analysis.get("decisions") or []:
        if not isinstance(decision, dict):
            continue
        citation = decision.get("media_citation")
        if not isinstance(citation, dict):
            citation = {}
            decision["media_citation"] = citation
        ms_id = citation.get("media_source_id") or meeting.get("primary_media_source_id")
        src = source_by_id.get(ms_id) if ms_id else primary
        if not src:
            continue
        if not citation.get("media_source_id"):
            citation["media_source_id"] = src.media_source_id
        start_s = hhmm_to_seconds(citation.get("timestamp_start") or decision.get("timestamp_start"))
        end_s = hhmm_to_seconds(citation.get("timestamp_end") or decision.get("timestamp_end"))
        if start_s is not None:
            abs_start = start_s + int(chunk_start_seconds)
            citation["timestamp_start_seconds"] = abs_start
            url, note = playback_url_at(
                canonical_url=src.canonical_url,
                platform=src.platform,
                seconds=abs_start,
                page_url=src.page_url,
            )
            citation["playback_url"] = url or None
            citation["playback_url_note"] = note
        if end_s is not None:
            citation["timestamp_end_seconds"] = end_s + int(chunk_start_seconds)
    return analysis
