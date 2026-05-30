"""
Helpers for governance meeting analysis → structured JSON (policy_analysis prompt).

Designed for the **2026 Gemma 4 Good Hackathon** demo notebook
(`02_run_meeting_llm.ipynb`). The four headline Gemma 4 capabilities the
demo exercises:

1. **Native multimodality / visual document parsing** — `call_google_genai_multimodal`
   sends PDFs and audio as bytes; `extract_pdf_digital_text` + `is_scanned_pdf`
   surface the "dark data" case where traditional text extractors return nothing.
2. **Adjustable visual token budget** — `classify_pdf_page_heuristic` decides
   per-page whether to spend HIGH (≈1,120 tokens) or LOW (≈64 tokens) per image.
3. **Built-in thinking mode** — `call_google_genai_multimodal` accepts
   `include_thoughts=True` and returns the reasoning trace alongside the answer.
4. **Alternating local sliding-window + global attention** — `chunk_audio_ffmpeg`
   slices long meetings into 15–20 minute chunks; `policy_drift_summarize`
   threads them back together with a follow-up "drift detector" pass.

Tree walking (`walk_raw_inputs`, `mirror_output_path`) preserves the
`<STATE>/<scope>/<jurisdiction>/…` geography encoded in the raw-input folders
so downstream consumers can re-derive FIPS codes from the path.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple


DOCUMENT_BREAK = "---DOCUMENT_BREAK---"

# File-type sets shared by the walker and the demo cells.
PDF_EXTS = {".pdf"}
_PURE_AUDIO_EXTS = {
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
}
# Video containers discovered in inventory; transcoded to Opus before chunking / API calls.
VIDEO_EXTS = frozenset({".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"})
VIDEO_CONTAINER_EXTS = VIDEO_EXTS  # backwards-compatible alias
AUDIO_EXTS = _PURE_AUDIO_EXTS | VIDEO_EXTS
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

# Folders inside a jurisdiction directory that hold scraper-temp artifacts and
# are unsafe to send to the model. ``_contact_images`` is intentionally NOT in
# this list — Demo 5 enriches contact photos with perceived demographics.
SKIP_DIR_PREFIXES: tuple[str, ...] = ()
SKIP_DIR_NAMES = {"__pycache__", ".ipynb_checkpoints", "_crawl_html", "_sitemaps", "excluded_inputs"}

# Scrape SuiteOne downloads write ``_video_assets/<hash>_suiteone.{opus,mp4}`` plus ``*.asset.json``.
VIDEO_ASSETS_DIRNAME = "_video_assets"

# Token-budget tiers we expose to judges. Names match Gemma 4 media-resolution levels.
TOKEN_BUDGET_HIGH = "HIGH"   # ~1,120 tokens per image — financial tables, ledgers, bids
TOKEN_BUDGET_MEDIUM = "MEDIUM"
TOKEN_BUDGET_LOW = "LOW"     # ~64 tokens per image — standard text-heavy minutes


def model_supports_thinking(model: str) -> bool:
    """Whether to attach any ``thinking_config`` (``include_thoughts`` / budget)."""
    import os
    if os.environ.get("GOVERNANCE_FORCE_THINKING", "0") == "1":
        return True
    mid = (model or "").lower()
    if mid.startswith("gemma"):
        return "31b" in mid
    return True


def model_supports_thinking_budget(model: str) -> bool:
    """
    Whether ``thinking_budget`` may be set on ``thinking_config``.

    AI Studio Gemma 4 ids (including ``gemma-4-31b-it`` on many keys) return
    ``400 Thinking budget is not supported for this model`` — use
    ``include_thoughts`` only, or omit thinking entirely.
    """
    import os
    if os.environ.get("GOVERNANCE_FORCE_THINKING", "0") == "1":
        return True
    mid = (model or "").lower()
    if mid.startswith("gemma"):
        return False
    return True


def _demo4_allow_a4b_audio() -> bool:
    """Opt-in: try ``gemma-4-26b-a4b-it`` for meeting audio on AI Studio (often rejected)."""
    return os.environ.get("GOVERNANCE_DEMO4_TRY_A4B_AUDIO", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def model_supports_audio_video_input(model: str) -> bool:
    """Whether ``generate_content`` may accept audio/video bytes (not PDF-only MoE)."""
    mid = (model or "").lower()
    if mid.startswith("gemini"):
        return True
    # AI Studio: 26B A4B MoE is PDF/image-first; audio works on some keys when opted in.
    if "26b" in mid and "a4b" in mid:
        return _demo4_allow_a4b_audio()
    if "gemma-3n" in mid or "gemma-4-e2b" in mid or "gemma-4-e4b" in mid:
        return True
    if "3n-e2b" in mid or "3n-e4b" in mid or "e2b-it" in mid or "e4b-it" in mid:
        return True
    if "gemma-4-31b" in mid or mid.endswith("31b-it"):
        return _demo4_allow_31b_audio()
    return False


def demo4_prefer_gemma_for_audio() -> bool:
    """Prefer Gemma (incl. 31B) for meeting audio per Gemma multimodal docs; Gemini as fallback."""
    return os.environ.get("GOVERNANCE_DEMO4_PREFER_GEMMA_AUDIO", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _demo4_allow_31b_audio() -> bool:
    """31B handles Demo 3 PDFs; also used for Demo 4 Opus when Gemma audio is preferred."""
    raw = os.environ.get("GOVERNANCE_DEMO4_ALLOW_31B_AUDIO", "").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if raw in ("1", "true", "yes"):
        return True
    return demo4_prefer_gemma_for_audio()


def model_accepts_demo4_audio_chunks(model: str) -> bool:
    """Models to use for Demo 4 meeting recordings (excludes 31B unless opted in)."""
    if not model_supports_audio_video_input(model):
        return False
    mid = (model or "").lower()
    if ("31b" in mid or "gemma-4-31b" in mid) and not _demo4_allow_31b_audio():
        return False
    return True


def model_supports_video_input(model: str) -> bool:
    """Whether ``video/mp4`` chunks are accepted (vs audio-only extraction)."""
    mid = (model or "").lower()
    if mid.startswith("gemini"):
        return True
    try:
        from .gemma_hf_backend import _repo_supports_audio, resolve_hf_model_id

        repo = resolve_hf_model_id(model or "")
        if _repo_supports_audio(repo):
            return True
    except ImportError:
        pass
    return False


def demo4_uses_huggingface() -> bool:
    try:
        from .gemma_hf_backend import demo4_use_huggingface

        return demo4_use_huggingface()
    except ImportError:
        return False


def resolve_demo4_model(
    genai_model: str,
    *,
    gatekeeper_model: str = "",
    thinking_model: str = "",
    client: Any = None,
    api_key: str = "",
) -> str:
    """Demo 4 model: Hugging Face E2B/E4B by default, else Google AI Studio."""
    if demo4_uses_huggingface():
        try:
            from .gemma_hf_backend import resolve_demo4_hf_model

            return resolve_demo4_hf_model()
        except ImportError as exc:
            raise RuntimeError(
                "Demo 4 requires gemma_hf_backend (transformers>=5.5.0). "
                "Re-run notebook §4 install, then Runtime → Restart session."
            ) from exc
    return resolve_demo4_genai_model(
        genai_model,
        gatekeeper_model=gatekeeper_model,
        thinking_model=thinking_model,
        client=client,
        api_key=api_key,
    )


def demo4_media_work_dir(scratch_root: Path, raw_root: Path, source_path: Path) -> Path:
    """Drive-backed ffmpeg / Opus cache for one source file (reused across runs)."""
    rel = source_path.resolve().relative_to(raw_root.resolve())
    work = (scratch_root / rel).with_suffix("")
    work.mkdir(parents=True, exist_ok=True)
    return work


def resolve_scraped_opus_for_media(
    source_path: Path,
    *,
    min_bytes: int = 1024,
) -> Optional[Path]:
    """
    Reuse scrape Opus without re-transcoding: sibling ``.opus`` or ``_video_assets`` sidecar.
    """
    source_path = source_path.resolve()
    sibling = source_path.with_suffix(".opus")
    if sibling.is_file() and sibling.stat().st_size >= min_bytes:
        return sibling.resolve()

    root = source_path.parent
    assets = root / VIDEO_ASSETS_DIRNAME
    if not assets.is_dir():
        return None

    source_name = source_path.name
    for meta_path in sorted(assets.glob("*.asset.json")):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        rel = (data.get("opus_relative_path") or "").strip()
        if not rel:
            continue
        opus_path = (root / rel).resolve()
        try:
            opus_path.relative_to(root.resolve())
        except ValueError:
            continue
        if not opus_path.is_file() or opus_path.stat().st_size < min_bytes:
            continue
        mp4_rel = (data.get("mp4_relative_path") or "").strip()
        if mp4_rel and (root / mp4_rel).resolve() == source_path.resolve():
            return opus_path
    return None


def _demo4_model_preference_order(
    available: Optional[set[str]] = None,
    *,
    thinking_model: str = "",
) -> List[str]:
    """Gemma first when ``GOVERNANCE_DEMO4_PREFER_GEMMA_AUDIO=1`` (default); else Gemini first."""
    try:
        from .gatekeeper_triage import (
            _GEMINI_DEMO4_AUDIO_FALLBACKS,
            _GEMMA_DEMO4_AUDIO_FALLBACKS,
        )
    except ImportError:
        return ["gemma-4-31b-it", "gemini-2.0-flash"]

    order: List[str] = []
    if _demo4_allow_a4b_audio():
        order.append("gemma-4-26b-a4b-it")
    if demo4_prefer_gemma_for_audio():
        tm = (thinking_model or os.environ.get("GOVERNANCE_THINKING_MODEL", "")).strip()
        if tm:
            order.append(tm)
        order.append("gemma-4-31b-it")
        order.extend(_GEMMA_DEMO4_AUDIO_FALLBACKS)
        order.extend(_GEMINI_DEMO4_AUDIO_FALLBACKS)
    else:
        order.extend(_GEMINI_DEMO4_AUDIO_FALLBACKS)
        order.extend(_GEMMA_DEMO4_AUDIO_FALLBACKS)
        if thinking_model.strip():
            order.append(thinking_model.strip())
        order.append("gemma-4-31b-it")
    if available:
        for gid in sorted(available):
            low = gid.lower()
            if gid not in order and (
                low.startswith("gemini") or "gemma" in low
            ):
                order.append(gid)
    return order


def pick_demo4_model_from_available(
    available: Iterable[str],
    *,
    thinking_model: str = "",
) -> Optional[str]:
    """First audio-capable id on this API key (from ``models.list()``)."""
    avail = {str(a).strip() for a in available if str(a).strip()}
    explicit = os.environ.get("GOVERNANCE_DEMO4_MODEL", "").strip()
    if explicit and explicit in avail and model_accepts_demo4_audio_chunks(explicit):
        return explicit
    for mid in _demo4_model_preference_order(avail, thinking_model=thinking_model):
        if mid in avail and model_accepts_demo4_audio_chunks(mid):
            return mid
    return None


def format_demo4_no_audio_model_error(available: Iterable[str]) -> str:
    avail = sorted({str(a).strip() for a in available if str(a).strip()})
    gemini = [m for m in avail if m.lower().startswith("gemini")]
    gemma = [m for m in avail if "gemma" in m.lower()]
    return (
        "Demo 4: no audio-capable model on this API key. "
        f"Gemma ids on key: {gemma or '(none)'}. "
        f"Gemini ids on key: {gemini or '(none)'}. "
        "Set GOVERNANCE_DEMO4_MODEL, GOVERNANCE_DEMO4_TRY_A4B_AUDIO=1 for gemma-4-26b-a4b-it, "
        "or GOVERNANCE_DEMO4_USE_HF=1 (default) for Hugging Face E2B/E4B."
    )


def list_demo4_capable_models_on_key(
    api_key: str,
    *,
    thinking_model: str = "",
) -> List[str]:
    """Ids on this key that Demo 4 may use for meeting audio (for §3 printout)."""
    try:
        from .gatekeeper_triage import _build_genai_client, _list_available_model_ids

        client = _build_genai_client(api_key)
        available = set(_list_available_model_ids(client))
    except Exception:
        return []
    return [
        m
        for m in _demo4_model_preference_order(available, thinking_model=thinking_model)
        if m in available and model_accepts_demo4_audio_chunks(m)
    ]


def resolve_demo4_genai_model(
    genai_model: str,
    *,
    gatekeeper_model: str = "",
    thinking_model: str = "",
    client: Any = None,
    api_key: str = "",
) -> str:
    """
    Model for Demo 4 meeting audio/video chunks.

    Picks from ``models.list()``: **Gemma** (31B / Edge) when
    ``GOVERNANCE_DEMO4_PREFER_GEMMA_AUDIO=1`` (default), else Gemini first.
    Override with ``GOVERNANCE_DEMO4_MODEL``. Set ``GOVERNANCE_DEMO4_ALLOW_31B_AUDIO=0``
    to block 31B for audio.
    """
    if client is None and api_key:
        try:
            from .gatekeeper_triage import _build_genai_client

            client = _build_genai_client(api_key)
        except Exception:
            client = None

    if client is not None:
        try:
            from .gatekeeper_triage import _list_available_model_ids

            available = set(_list_available_model_ids(client))
            picked = pick_demo4_model_from_available(
                available, thinking_model=thinking_model
            )
            if picked:
                return picked
            raise RuntimeError(format_demo4_no_audio_model_error(available))
        except RuntimeError:
            raise
        except Exception:
            pass

    explicit = os.environ.get("GOVERNANCE_DEMO4_MODEL", "").strip()
    if explicit and model_accepts_demo4_audio_chunks(explicit):
        return explicit
    env_fb = os.environ.get("GOVERNANCE_DEMO4_FALLBACK_MODEL", "").strip()
    if env_fb and model_accepts_demo4_audio_chunks(env_fb):
        return env_fb
    tm = (thinking_model or os.environ.get("GOVERNANCE_THINKING_MODEL", "")).strip()
    if demo4_prefer_gemma_for_audio() and tm and model_accepts_demo4_audio_chunks(tm):
        return tm
    return "gemini-2.0-flash"


def _genai_error_text(exc: BaseException) -> str:
    return str(exc).lower()


def is_audio_modality_rejected(exc: BaseException) -> bool:
    return "audio input modality" in _genai_error_text(exc)


def demo4_models_to_try(
    primary: str,
    *,
    api_key: str = "",
    thinking_model: str = "",
    chunk_mime: str = "",
) -> List[str]:
    """Ordered models for Demo 4 retries (HF: single E2B/E4B; Google: ids on API key)."""
    if demo4_uses_huggingface():
        try:
            from .gemma_hf_backend import resolve_demo4_hf_model

            return [resolve_demo4_hf_model(primary)]
        except ImportError:
            return [primary] if primary else []

    try:
        from .gatekeeper_triage import _build_genai_client, _list_available_model_ids
    except ImportError:
        return [primary] if primary and model_accepts_demo4_audio_chunks(primary) else []

    available: set[str] = set()
    if api_key:
        try:
            available = set(_list_available_model_ids(_build_genai_client(api_key)))
        except Exception:
            available = set()

    if not available:
        return [primary] if primary and model_accepts_demo4_audio_chunks(primary) else []

    prefer_gemma = demo4_prefer_gemma_for_audio() or "opus" in (chunk_mime or "").lower()
    ordered: List[str] = []
    if primary and primary in available and model_accepts_demo4_audio_chunks(primary):
        ordered.append(primary)
    if prefer_gemma:
        tm = (thinking_model or os.environ.get("GOVERNANCE_THINKING_MODEL", "")).strip()
        for mid in (tm, "gemma-4-31b-it"):
            if (
                mid
                and mid in available
                and mid not in ordered
                and model_accepts_demo4_audio_chunks(mid)
            ):
                ordered.append(mid)
    for mid in _demo4_model_preference_order(available, thinking_model=thinking_model):
        if mid in available and mid not in ordered and model_accepts_demo4_audio_chunks(mid):
            ordered.append(mid)
    return ordered


# ─────────────────────────────────────────────────────────────
# Basic text / JSON utilities (kept from the prior helper)
# ─────────────────────────────────────────────────────────────


def load_text_file(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def chunk_text(text: str, max_chars: int = 14_000, overlap: int = 800) -> List[str]:
    """Character-based windowing fallback when audio chunking is not available."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def _extract_json_object(text: str) -> str:
    s = text.strip()
    if "```json" in s:
        m = re.search(r"```json\s*(.*?)\s*```", s, re.DOTALL)
        if m:
            s = m.group(1).strip()
    elif s.startswith("```"):
        lines = s.split("\n")
        if len(lines) > 2:
            s = "\n".join(lines[1:-1]).strip()
    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last != -1 and last > first:
        s = s[first : last + 1]
    return s.strip()


def parse_policy_analysis_response(raw: str) -> Dict[str, Any]:
    """
    Split model output into JSON analysis, markdown summary, optional mermaid block.

    Canonical format (see `prompts/policy_analysis_v1.md`):
      JSON
      ---DOCUMENT_BREAK---
      summary markdown
      ---DOCUMENT_BREAK---
      mermaid / extra
    """
    parts = raw.split(DOCUMENT_BREAK)
    out: Dict[str, Any] = {
        "json_analysis": None,
        "summary": None,
        "extra": None,
        "raw": raw,
        "parse_error": None,
    }
    if not parts:
        return out
    try:
        json_text = _extract_json_object(parts[0])
        out["json_analysis"] = json.loads(json_text)
    except (json.JSONDecodeError, ValueError) as e:
        out["parse_error"] = str(e)
        out["json_analysis"] = {"_error": str(e), "_raw_preview": parts[0][:2000]}
    if len(parts) >= 2:
        out["summary"] = parts[1].strip()
    if len(parts) >= 3:
        out["extra"] = parts[2].strip()
    return out


# ─────────────────────────────────────────────────────────────
# Jurisdiction-aware tree walking
# ─────────────────────────────────────────────────────────────


# Scope labels we accept under `01_raw_inputs/<STATE>/`. The repo sync script writes
# `county` and `municipality`; user-staged trees sometimes use `city` synonyms.
SCOPE_LABELS = {
    "county", "municipality", "city", "town", "village",
    "township", "borough", "parish", "special_district",
}


@dataclass(frozen=True)
class JurisdictionDir:
    """Geography parsed from `<STATE>/<scope>/<slug>` under `01_raw_inputs`."""

    state_code: str          # e.g. "AL", "MT"
    scope: str               # "county" | "municipality" | …
    slug: str                # e.g. "county_01125", "municipality_0177256"
    fips: Optional[str]      # e.g. "01125" (county) or "0177256" (place)
    root: Path               # absolute path to the jurisdiction directory

    @property
    def relative_label(self) -> str:
        return f"{self.state_code}/{self.scope}/{self.slug}"

    @property
    def jurisdiction_id(self) -> str:
        """
        Canonical cross-reference key — used to look up Orbis registry rows and
        link analyses across notebooks. Lower-snake-case, deterministic from the
        folder layout: ``jurisdiction_<state>_<scope>_<id-tail>``.

        Strips the redundant ``<scope>_`` prefix from the slug when present so
        we don't emit ``jurisdiction_al_county_county_01125``.

        Examples:
          ``AL/county/county_01125`` → ``jurisdiction_al_county_01125``
          ``MT/municipality/municipality_3006475`` → ``jurisdiction_mt_municipality_3006475``
          ``AL/county/tuscaloosa_county`` → ``jurisdiction_al_county_tuscaloosa_county``
        """
        slug = (self.slug or "").lower()
        scope = self.scope.lower()
        scope_prefix = f"{scope}_"
        if slug.startswith(scope_prefix):
            tail = slug[len(scope_prefix):]
        else:
            tail = slug
        return f"jurisdiction_{self.state_code.lower()}_{scope}_{tail}"


_FIPS_SUFFIX_RE = re.compile(r"^[a-z_]+_(\d{3,9})$")


def parse_jurisdiction_dir(root: Path, state_code: str, scope: str) -> JurisdictionDir:
    """Pull the FIPS / place id off the trailing digits of the directory name."""
    slug = root.name
    m = _FIPS_SUFFIX_RE.match(slug)
    fips = m.group(1) if m else None
    return JurisdictionDir(
        state_code=state_code.upper(),
        scope=scope.lower(),
        slug=slug,
        fips=fips,
        root=root,
    )


@dataclass
class MeetingInventory:
    """Files of interest discovered under a single jurisdiction directory."""

    jurisdiction: JurisdictionDir
    pdfs: List[Path] = field(default_factory=list)
    audio: List[Path] = field(default_factory=list)
    images: List[Path] = field(default_factory=list)

    @property
    def has_media(self) -> bool:
        return bool(self.pdfs or self.audio or self.images)


def format_inventory_media_line(inv: MeetingInventory) -> str:
    """
    One-line inventory summary for pipeline logs.

    ``inv.audio`` holds both video containers (``.mp4``, …) and pure audio;
    label them separately when helpful.
    """
    n_video = sum(1 for p in inv.audio if p.suffix.lower() in VIDEO_EXTS)
    n_audio_only = len(inv.audio) - n_video
    parts = [f"pdfs={len(inv.pdfs)}"]
    if n_video:
        parts.append(f"video={n_video}")
    if n_audio_only:
        parts.append(f"audio={n_audio_only}")
    parts.append(f"images={len(inv.images)}")
    return " ".join(parts)


def _iter_files(jurisdiction_root: Path) -> Iterator[Path]:
    """
    Recursive walk that skips scraper-temp folders (`_crawl_html`, `_sitemaps`)
    and the exclusion bucket, but DOES descend into `_contact_images/` so the
    image-enrichment demo can see contact photos.
    """
    for path in sorted(jurisdiction_root.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(jurisdiction_root).parts
        if any(
            (SKIP_DIR_PREFIXES and part.startswith(SKIP_DIR_PREFIXES))
            or part in SKIP_DIR_NAMES
            for part in rel_parts[:-1]
        ):
            continue
        yield path


def walk_raw_inputs(raw_root: Path) -> Iterator[MeetingInventory]:
    """
    Yield one `MeetingInventory` per `<STATE>/<scope>/<jurisdiction_dir>` found
    under `raw_root` (typically `…/01_raw_inputs`). Directories without any PDFs,
    audio, or images are still yielded — callers can filter on `.has_media`.
    The ``excluded_inputs/`` subtree (Gatekeeper rejects) is always skipped.
    """
    if not raw_root.is_dir():
        return
    for state_dir in sorted(p for p in raw_root.iterdir() if p.is_dir()):
        if state_dir.name in SKIP_DIR_NAMES:
            continue
        if SKIP_DIR_PREFIXES and state_dir.name.startswith(SKIP_DIR_PREFIXES):
            continue
        for scope_dir in sorted(p for p in state_dir.iterdir() if p.is_dir()):
            if scope_dir.name.lower() not in SCOPE_LABELS:
                continue
            for jur_dir in sorted(p for p in scope_dir.iterdir() if p.is_dir()):
                jur = parse_jurisdiction_dir(jur_dir, state_dir.name, scope_dir.name)
                inv = MeetingInventory(jurisdiction=jur)
                for f in _iter_files(jur_dir):
                    ext = f.suffix.lower()
                    if ext in PDF_EXTS:
                        inv.pdfs.append(f)
                    elif ext in VIDEO_EXTS:
                        # Scrape often keeps sibling ``.opus`` and drops the container.
                        if f.with_suffix(".opus").is_file():
                            continue
                        inv.audio.append(f)
                    elif ext in _PURE_AUDIO_EXTS:
                        inv.audio.append(f)
                    elif ext in IMAGE_EXTS:
                        inv.images.append(f)
                enrich_inventory_video_assets(inv)
                yield inv


def inventory_video_assets_enabled() -> bool:
    """When true, register on-disk ``_video_assets`` paths from ``*.asset.json`` sidecars."""
    return os.environ.get("GOVERNANCE_INVENTORY_VIDEO_ASSETS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def discover_media_from_video_asset_manifests(jurisdiction_root: Path) -> List[Path]:
    """
    Paths listed in scrape ``_video_assets/*.asset.json`` when the file exists.

    Reads ``opus_relative_path`` and ``mp4_relative_path`` (relative to the
    jurisdiction root). Skips missing bytes — JSON alone is not enough.
    """
    root = jurisdiction_root.resolve()
    video_dir = root / VIDEO_ASSETS_DIRNAME
    if not video_dir.is_dir():
        return []
    found: List[Path] = []
    seen: set[str] = set()
    for meta_path in sorted(video_dir.glob("*.asset.json")):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for rel_key in ("opus_relative_path", "mp4_relative_path"):
            rel = (data.get(rel_key) or "").strip()
            if not rel:
                continue
            path = (root / rel).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                continue
            if not path.is_file():
                continue
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            found.append(path)
    return found


def select_demo4_media(
    audio_paths: List[Path],
    raw_root: Path,
    *,
    max_files: int,
) -> List[Path]:
    """
    Choose up to ``max_files`` recordings for Demo 4.

  Prefer **one file per distinct meeting date** (newest dates first) so
    ``SCOPE=fast`` with two dates processes two videos (e.g. ``2026_02_18.mp4``
    and ``2026_05_06.mp4``), not two copies from the same session.
    """
    if max_files <= 0 or not audio_paths:
        return []
    if len(audio_paths) <= max_files:
        return list(audio_paths)

    try:
        from .meeting_date_scope import infer_meeting_date_for_file
    except ImportError:
        return sorted(audio_paths, key=lambda p: p.name)[:max_files]

    by_date: Dict[str, List[Path]] = {}
    undated: List[Path] = []
    for path in audio_paths:
        date_s = infer_meeting_date_for_file(path, raw_root) or ""
        if date_s:
            by_date.setdefault(date_s, []).append(path)
        else:
            undated.append(path)

    selected: List[Path] = []
    seen: set[str] = set()

    def _pick_one(group: List[Path]) -> Path:
        videos = [p for p in group if p.suffix.lower() in VIDEO_EXTS]
        pool = videos or group
        return sorted(pool, key=lambda p: p.name)[0]

    for date_s in sorted(by_date.keys(), reverse=True):
        if len(selected) >= max_files:
            break
        pick = _pick_one(by_date[date_s])
        key = str(pick.resolve())
        if key not in seen:
            seen.add(key)
            selected.append(pick)

    remainder = sorted(
        undated + [p for group in by_date.values() for p in group],
        key=lambda p: p.name,
    )
    for path in remainder:
        if len(selected) >= max_files:
            break
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        selected.append(path)

    return selected[:max_files]


def enrich_inventory_video_assets(inv: MeetingInventory) -> int:
    """
    Append scrape-sidecar media not already in ``inv.audio``.

    Flat jurisdiction MP4s (e.g. ``2026_05_06.mp4`` at the county root) are
    already discovered by the normal walk; this hook only adds ``_video_assets``
    paths referenced in ``*.asset.json``.

    Returns the number of paths newly added.
    """
    if not inventory_video_assets_enabled():
        return 0
    extra = discover_media_from_video_asset_manifests(inv.jurisdiction.root)
    if not extra:
        return 0
    existing = {p.resolve() for p in inv.audio}
    added = 0
    for path in extra:
        resolved = path.resolve()
        if resolved in existing:
            continue
        inv.audio.append(path)
        existing.add(resolved)
        added += 1
    return added


def inventory_for_jurisdiction(
    raw_root: Path, jurisdiction_root: Path
) -> Optional[MeetingInventory]:
    """Return a fresh :class:`MeetingInventory` for one jurisdiction directory."""
    target = jurisdiction_root.resolve()
    for inv in walk_raw_inputs(raw_root):
        if inv.jurisdiction.root.resolve() == target:
            return inv
    # Jurisdiction dir exists but had no walk match — still try sidecars only.
    if target.is_dir():
        jur = parse_jurisdiction_dir(
            target,
            target.parent.parent.name if len(target.parents) >= 2 else "",
            target.parent.name if target.parent else "",
        )
        inv = MeetingInventory(jurisdiction=jur)
        enrich_inventory_video_assets(inv)
        if inv.has_media:
            return inv
    return None


def mirror_output_path(
    *,
    input_path: Path,
    raw_root: Path,
    processed_root: Path,
    suffix: str,
) -> Path:
    """
    Translate `…/01_raw_inputs/AL/county/county_01125/2026/minutes.pdf` →
    `…/<processed_root>/AL/county/county_01125/2026/minutes<suffix>`, creating
    any missing parent directories. Geography is preserved verbatim.
    """
    rel = input_path.resolve().relative_to(raw_root.resolve())
    out = processed_root / rel.with_suffix("").as_posix()
    out = Path(str(out) + suffix)
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


# ─────────────────────────────────────────────────────────────
# Processed-output idempotency (skip when JSON exists; re-run when deleted)
# ─────────────────────────────────────────────────────────────


def force_reprocess_outputs() -> bool:
    """When true, ignore existing Gemma JSON / text artifacts and call the API again."""
    return os.environ.get("GOVERNANCE_FORCE_REPROCESS", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def read_json_file(path: Path) -> Optional[Any]:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def text_output_complete(path: Path, *, min_chars: int = 50) -> bool:
    if not path.is_file():
        return False
    try:
        return len(path.read_text(encoding="utf-8").strip()) >= min_chars
    except OSError:
        return False


def policy_analysis_json_complete(data: Any) -> bool:
    """True when parsed ``json_analysis`` is usable for import (see policy_analysis_v1.md)."""
    if not isinstance(data, dict) or not data or "_error" in data:
        return False
    decisions = data.get("decisions")
    if not isinstance(decisions, list):
        return False
    for decision in decisions:
        if not isinstance(decision, dict):
            return False
        cofog = decision.get("primary_theme_cofog")
        if not isinstance(cofog, str) or not cofog.startswith("COFOG-"):
            return False
    return True


def policy_chunk_output_complete(path: Path) -> bool:
    """True when a Demo 4 ``chunk_NNN.json`` has usable ``json_analysis``."""
    data = read_json_file(path)
    if not isinstance(data, dict):
        return False
    return policy_analysis_json_complete(data.get("json_analysis"))


def demo2_page_output_complete(path: Path) -> bool:
    data = read_json_file(path)
    if not isinstance(data, dict):
        return False
    extracted = data.get("extracted")
    if not isinstance(extracted, dict) or extracted.get("_parse_error"):
        return False
    return bool(extracted.get("raw_text") or extracted.get("page_type"))


def demo2_pdf_outputs_complete(per_pdf_dir: Path, *, expected_pages: int) -> bool:
    report = read_json_file(per_pdf_dir / "_token_budget_report.json")
    if not isinstance(report, dict):
        return False
    if int(report.get("page_count") or 0) != expected_pages:
        return False
    for i in range(1, expected_pages + 1):
        if not demo2_page_output_complete(per_pdf_dir / f"page_{i:03d}.json"):
            return False
    return True


def demo3_thinking_json_complete(path: Path) -> bool:
    return policy_analysis_json_complete(read_json_file(path))


def demo4_drift_output_complete(path: Path) -> bool:
    data = read_json_file(path)
    if not isinstance(data, dict):
        return False
    if data.get("subjects") or data.get("drifted_subjects"):
        return True
    return isinstance(data.get("meeting_level_summary"), dict) and bool(
        data["meeting_level_summary"]
    )


def load_demo4_chunk_analyses(per_audio_dir: Path, chunk_count: int) -> List[Dict[str, Any]]:
    """Load ``json_analysis`` dicts from existing chunk JSON (missing chunks → empty dict)."""
    out: List[Dict[str, Any]] = []
    for idx in range(chunk_count):
        path = per_audio_dir / f"chunk_{idx:03d}.json"
        data = read_json_file(path)
        if isinstance(data, dict) and policy_analysis_json_complete(data.get("json_analysis")):
            out.append(data["json_analysis"])
        else:
            out.append({})
    return out


def find_existing_audio_chunks(scratch_dir: Path) -> List[Path]:
    """Reuse ffmpeg segment files when JSON was deleted but scratch MP3 chunks remain."""
    if not scratch_dir.is_dir():
        return []
    return sorted(scratch_dir.glob("*_chunk_*.mp3"))


def demo4_use_video_chunks() -> bool:
    """When true, ``.mp4`` / video containers are segmented and sent as ``video/mp4``."""
    return os.environ.get("GOVERNANCE_DEMO4_VIDEO_CHUNKS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "audio",
    )


def find_existing_demo4_chunks(scratch_dir: Path, *, video: bool) -> List[Path]:
    """Reuse ffmpeg segment files under scratch (``.opus`` / ``.mp3`` / ``.mp4``), including subdirs."""
    if not scratch_dir.is_dir():
        return []
    if video:
        return sorted(scratch_dir.rglob("*_chunk_*.mp4"))
    for ext in ("opus", "mp3", "m4a", "aac"):
        found = sorted(scratch_dir.rglob(f"*_chunk_*.{ext}"))
        if found:
            return found
    return []


def _chunk_video_ffmpeg(
    video_path: Path,
    *,
    out_dir: Path,
    chunk_minutes: int = 15,
) -> List[Path]:
    """Split a video container into ``.mp4`` segments (video+audio) for multimodal API."""
    if not _ffmpeg_available():
        raise RuntimeError(
            "ffmpeg not found on PATH. On Colab it ships by default; locally run "
            "`apt-get install -y ffmpeg` or `brew install ffmpeg`."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    video_path = video_path.resolve()
    stem = video_path.stem
    pattern = out_dir / f"{stem}_chunk_%03d.mp4"
    seconds = max(60, int(chunk_minutes * 60))
    base_cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-f",
        "segment",
        "-segment_time",
        str(seconds),
        "-reset_timestamps",
        "1",
    ]
    for extra in (["-c", "copy"], ["-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac"]):
        cmd = base_cmd + extra + [str(pattern)]
        try:
            subprocess.run(cmd, check=True, timeout=7200)
            chunks = sorted(out_dir.glob(f"{stem}_chunk_*.mp4"))
            if chunks:
                return chunks
        except subprocess.CalledProcessError:
            continue
    raise RuntimeError(f"ffmpeg could not segment video: {video_path.name}")


def demo4_prefer_opus_chunks() -> bool:
    """When true (default), MP4/WebM → full Opus transcode → 15‑min ``.opus`` slices before MP3."""
    return os.environ.get("GOVERNANCE_DEMO4_PREFER_OPUS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "mp3_only",
    )


def _chunk_audio_segments(
    source_path: Path,
    *,
    out_dir: Path,
    chunk_minutes: int,
    fmt: str,
) -> List[Tuple[Path, str]]:
    paths = chunk_audio_ffmpeg(
        source_path,
        out_dir=out_dir,
        chunk_minutes=chunk_minutes,
        fmt=fmt,
    )
    return [(p, mime_for(p)) for p in paths]


def iter_demo4_ingest_strategies(
    source_path: Path,
    *,
    out_dir: Path,
    chunk_minutes: int = 15,
    prefer_video: Optional[bool] = None,
    demo4_model: str = "",
) -> Iterator[Tuple[str, List[Tuple[Path, str]]]]:
    """
    Yield ``(strategy_label, [(path, mime), …])`` until one produces API JSON.

    Order: **Opus slices first** (MP4→Opus→segment; matches ``_video_assets/*.opus``) →
    optional ``video/mp4`` (Gemini only) → MP3 slices.
    """
    source_path = source_path.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    use_video = (
        demo4_use_video_chunks()
        if prefer_video is None
        else bool(prefer_video)
    )
    is_video_container = source_path.suffix.lower() in VIDEO_EXTS
    is_opus_file = source_path.suffix.lower() == ".opus"

    if demo4_prefer_opus_chunks() and (is_video_container or is_opus_file):
        try:
            chunks = _chunk_audio_segments(
                source_path,
                out_dir=out_dir / "opus_seg",
                chunk_minutes=chunk_minutes,
                fmt="opus",
            )
            if chunks:
                label = "opus_file" if is_opus_file else "opus_15min"
                yield label, chunks
        except Exception as exc:
            print(
                f"   ℹ️  {source_path.name}: Opus slice failed ({exc}) — "
                "trying video/mp4 or MP3.",
                flush=True,
            )

    try_video_mp4 = (
        is_video_container
        and use_video
        and model_supports_video_input(demo4_model)
    )
    if demo4_prefer_opus_chunks() and demo4_uses_huggingface():
        try_video_mp4 = False
    if try_video_mp4:
        try:
            paths = _chunk_video_ffmpeg(
                source_path, out_dir=out_dir / "video_seg", chunk_minutes=chunk_minutes
            )
            if paths:
                yield "video_mp4", [(p, "video/mp4") for p in paths]
        except RuntimeError as exc:
            print(
                f"   ℹ️  {source_path.name}: video/mp4 segment failed ({exc}) — "
                "trying MP3 audio slices.",
                flush=True,
            )

    chunks = _chunk_audio_segments(
        source_path,
        out_dir=out_dir / "mp3_seg",
        chunk_minutes=chunk_minutes,
        fmt="mp3",
    )
    if chunks:
        yield "mp3_15min", chunks


def chunk_meeting_media_for_demo4(
    source_path: Path,
    *,
    out_dir: Path,
    chunk_minutes: int = 15,
    prefer_video: Optional[bool] = None,
    demo4_model: str = "",
) -> List[Tuple[Path, str]]:
    """First ingest strategy only (prefer :func:`iter_demo4_ingest_strategies` for fallbacks)."""
    for _label, media in iter_demo4_ingest_strategies(
        source_path,
        out_dir=out_dir,
        chunk_minutes=chunk_minutes,
        prefer_video=prefer_video,
        demo4_model=demo4_model,
    ):
        return media
    return []


def discover_demo4_chunk_media(
    scratch_dir: Path,
    *,
    video: bool,
) -> List[Tuple[Path, str]]:
    """Reuse ffmpeg segments under scratch (opus before mp3 when not video)."""
    paths = find_existing_demo4_chunks(scratch_dir, video=video)
    if not video and demo4_prefer_opus_chunks():
        opus_only = [p for p in paths if p.suffix.lower() == ".opus"]
        if opus_only:
            paths = opus_only
    return [(p, mime_for(p)) for p in paths]


# ─────────────────────────────────────────────────────────────
# PDF rendering + digital-text probing (visual-OCR demo)
# ─────────────────────────────────────────────────────────────


@dataclass
class PdfPageRender:
    page_index: int          # 0-based
    image_bytes: bytes       # PNG bytes
    digital_text: str        # empty string if scanned
    classification: str      # "scanned" | "financial_or_tabular" | "text_heavy"
    token_budget: str        # one of TOKEN_BUDGET_*


_FINANCIAL_HINT_PATTERNS = (
    re.compile(r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?"),       # $12,345.67
    re.compile(r"\b\d{1,3}(?:,\d{3}){1,}\b"),                 # 1,234,567
    re.compile(r"\b(?:bid|levy|appropriation|contract|grant|award)\b", re.IGNORECASE),
    re.compile(r"\b(?:total|subtotal|balance|fund)\b", re.IGNORECASE),
)
_TABLE_HINT_RUN = re.compile(r"(?:\S+\s{2,}){3,}\S+")  # 4+ whitespace-aligned columns


def classify_pdf_page_heuristic(digital_text: str) -> Tuple[str, str]:
    """
    Decide token budget tier from the digital-text shadow of a single PDF page.

    Returns ``(classification, token_budget)``:
      - no extractable text → ``("scanned", HIGH)`` — needs visual OCR.
      - financial / tabular hits → ``("financial_or_tabular", HIGH)``.
      - otherwise text-heavy → ``("text_heavy", LOW)``.
    """
    stripped = (digital_text or "").strip()
    if len(stripped) < 40:
        return "scanned", TOKEN_BUDGET_HIGH

    fin_hits = sum(bool(p.search(stripped)) for p in _FINANCIAL_HINT_PATTERNS)
    table_hits = len(_TABLE_HINT_RUN.findall(stripped))
    if fin_hits >= 2 or table_hits >= 3:
        return "financial_or_tabular", TOKEN_BUDGET_HIGH
    return "text_heavy", TOKEN_BUDGET_LOW


def render_pdf_pages(pdf_path: Path, dpi: int = 200) -> List[PdfPageRender]:
    """
    Render each page of ``pdf_path`` to PNG bytes and probe for digital text.

    Requires ``pymupdf`` (``pip install pymupdf``). Falls back to a clear error
    rather than a silent empty list so the demo cells can surface install issues.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - install-time error
        raise RuntimeError(
            "render_pdf_pages requires PyMuPDF — `pip install pymupdf`."
        ) from exc

    out: List[PdfPageRender] = []
    with fitz.open(pdf_path) as doc:
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            png = pix.tobytes("png")
            text = page.get_text("text") or ""
            classification, budget = classify_pdf_page_heuristic(text)
            out.append(
                PdfPageRender(
                    page_index=i,
                    image_bytes=png,
                    digital_text=text,
                    classification=classification,
                    token_budget=budget,
                )
            )
    return out


def extract_pdf_digital_text(pdf_path: Path) -> str:
    """Concat digital-text layer of every page; empty string for scanned PDFs."""
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "extract_pdf_digital_text requires PyMuPDF — `pip install pymupdf`."
        ) from exc

    parts: List[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            parts.append(page.get_text("text") or "")
    return "\n".join(parts).strip()


def is_scanned_pdf(pdf_path: Path, min_chars: int = 200) -> bool:
    """True when the PDF carries effectively no digital text layer."""
    return len(extract_pdf_digital_text(pdf_path)) < min_chars


def demo3_input_mode() -> str:
    """
    How Demo 3 supplies meeting document content to the policy model.

    - ``auto`` / ``text``: PyMuPDF digital text when present; otherwise one light OCR
      pass (LOW vision, Demo 1-style transcription) then **text-only** policy call.
    - ``vision``: legacy full-PDF multimodal + ``GOVERNANCE_DEMO3_MEDIA_RESOLUTION``.
    """
    raw = os.environ.get("GOVERNANCE_DEMO3_INPUT", "auto").strip().lower()
    aliases = {
        "text_only": "text",
        "text-only": "text",
        "multimodal": "vision",
        "pdf": "vision",
        "full_pdf": "vision",
    }
    key = aliases.get(raw, raw)
    if key in ("vision", "text"):
        return key
    return "auto"


def demo3_text_first_enabled() -> bool:
    """True when Demo 3 should prefer extracted/OCR text over attaching the PDF."""
    return demo3_input_mode() in ("auto", "text")


def demo1_skip_when_digital() -> bool:
    """When True, Demo 1 writes PyMuPDF text and skips sending the PDF to the API."""
    return os.environ.get("GOVERNANCE_DEMO1_SKIP_WHEN_DIGITAL", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def demo2_skip_when_digital() -> bool:
    """When True, Demo 2 skips per-page PNG vision for PDFs with a text layer."""
    return os.environ.get("GOVERNANCE_DEMO2_SKIP_WHEN_DIGITAL", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def demo3_min_digital_chars() -> int:
    try:
        return max(0, int(os.environ.get("GOVERNANCE_DEMO3_MIN_DIGITAL_CHARS", "200")))
    except ValueError:
        return 200


def demo3_max_document_chars() -> int:
    try:
        return max(1000, int(os.environ.get("GOVERNANCE_DEMO3_MAX_DOCUMENT_CHARS", "60000")))
    except ValueError:
        return 60000


def truncate_demo3_document_text(
    text: str,
    *,
    max_chars: Optional[int] = None,
) -> str:
    """Cap meeting-document text embedded in the Demo 3 user prompt."""
    cap = demo3_max_document_chars() if max_chars is None else max(1, int(max_chars))
    t = (text or "").strip()
    if len(t) <= cap:
        return t
    note = "\n\n[… document truncated for demo input cap …]"
    keep = max(0, cap - len(note))
    return t[:keep] + note


# ─────────────────────────────────────────────────────────────
# Audio chunking (long-meeting attention demo)
# ─────────────────────────────────────────────────────────────


def _ffmpeg_available() -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, check=True, timeout=10
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _ffmpeg_audio_only_output_flags(path: Path) -> List[str]:
    """Strip video/subtitles; keep the first audio track from MP4/WebM containers."""
    if path.suffix.lower() in VIDEO_EXTS:
        return ["-vn", "-sn", "-map", "0:a:0?"]
    return []


def transcode_video_to_opus(
    video_path: Path,
    *,
    out_path: Optional[Path] = None,
    bitrate: str = "96k",
    timeout_s: int = 7200,
) -> Path:
    """
    Encode the audio track of a video container to Opus (``.opus``).

    Raises if ffmpeg is missing or the output file is empty.
    """
    if not _ffmpeg_available():
        raise RuntimeError(
            "ffmpeg not found on PATH. On Colab it ships by default; locally run "
            "`apt-get install -y ffmpeg` or `brew install ffmpeg`."
        )
    dest = (out_path or video_path.with_suffix(".opus")).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        from .colab_timed_steps import format_file_size, log_phase

        ctx: Any = log_phase(
            f"ffmpeg → Opus {video_path.name}",
            detail=format_file_size(video_path),
        )
    except ImportError:
        from contextlib import nullcontext

        ctx = nullcontext()
    with ctx:
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(video_path),
                *_ffmpeg_audio_only_output_flags(video_path),
                "-c:a",
                "libopus",
                "-b:a",
                bitrate,
                str(dest),
            ],
            check=True,
            capture_output=True,
            timeout=timeout_s,
        )
    if not dest.is_file() or dest.stat().st_size < 1024:
        raise RuntimeError(f"Opus transcode produced empty or tiny output: {dest}")
    return dest


def prepare_meeting_audio_for_processing(
    source_path: Path,
    *,
    work_dir: Path,
    bitrate: str = "96k",
    min_opus_bytes: int = 1024,
) -> Path:
    """
    Return an audio path ready for chunking / transcription.

    Video containers (``.mp4``, ``.webm``, …) are transcoded to Opus first — reusing a
    sibling ``<stem>.opus`` from scrape when present, otherwise writing under ``work_dir``.
    """
    source_path = source_path.resolve()
    if source_path.suffix.lower() not in VIDEO_EXTS:
        return source_path

    scraped = resolve_scraped_opus_for_media(source_path, min_bytes=min_opus_bytes)
    if scraped is not None:
        return scraped

    work_dir.mkdir(parents=True, exist_ok=True)
    cached = (work_dir / f"{source_path.stem}.opus").resolve()
    if cached.is_file() and cached.stat().st_size >= min_opus_bytes:
        return cached

    return transcode_video_to_opus(source_path, out_path=cached, bitrate=bitrate)


def chunk_audio_ffmpeg(
    audio_path: Path,
    *,
    out_dir: Path,
    chunk_minutes: int = 15,
    fmt: str = "mp3",
) -> List[Path]:
    """
    Split ``audio_path`` into ``chunk_minutes``-minute pieces via ffmpeg's segmenter.
    Call :func:`prepare_meeting_audio_for_processing` first when the source is a video
    container so chunking runs on Opus. Returns the sorted list of chunk paths under
    ``out_dir``. Raises if ffmpeg is not on PATH — Colab ships with it by default.
    """
    if not _ffmpeg_available():
        raise RuntimeError(
            "ffmpeg not found on PATH. On Colab it ships by default; locally run "
            "`apt-get install -y ffmpeg` or `brew install ffmpeg`."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_path = prepare_meeting_audio_for_processing(
        audio_path, work_dir=out_dir / "_opus"
    )
    stem = audio_path.stem
    pattern = out_dir / f"{stem}_chunk_%03d.{fmt}"
    seconds = max(60, int(chunk_minutes * 60))
    fmt_l = (fmt or "mp3").lower().lstrip(".")
    if fmt_l == "opus":
        codec = "copy" if audio_path.suffix.lower() == ".opus" else "libopus"
    elif fmt_l == "mp3":
        codec = "libmp3lame"
    else:
        codec = "copy"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(audio_path),
        *_ffmpeg_audio_only_output_flags(audio_path),
        "-f", "segment", "-segment_time", str(seconds),
        "-c:a", codec,
        str(pattern),
    ]
    try:
        from .colab_timed_steps import format_file_size, log_phase

        seg_ctx: Any = log_phase(
            f"ffmpeg {chunk_minutes}min {fmt_l} slices",
            detail=f"{audio_path.name} {format_file_size(audio_path)}",
        )
    except ImportError:
        from contextlib import nullcontext

        seg_ctx = nullcontext()
    with seg_ctx:
        subprocess.run(cmd, check=True)
    chunks = sorted(out_dir.glob(f"{stem}_chunk_*.{fmt}"))
    try:
        from .colab_timed_steps import log_line

        log_line(f"ffmpeg produced {len(chunks)} {fmt_l} chunk(s) under {out_dir.name}/")
    except ImportError:
        pass
    return chunks


# ─────────────────────────────────────────────────────────────
# Google GenAI client wrapper (multimodal + thinking + media_resolution)
# ─────────────────────────────────────────────────────────────


@dataclass
class _StreamGenAIResponse:
    """Collected text from ``generate_content_stream`` (AI Studio streaming hack)."""

    text: str
    last_chunk: Any = None


@dataclass
class GenAIResult:
    text: str                                  # answer-text concatenated across parts
    thoughts: str                              # reasoning trace when include_thoughts=True
    raw_response: Any                          # full SDK response, for debugging


def _media_resolution_value(budget: Optional[str]):
    """Map our budget tier to the SDK enum; tolerate older SDKs that lack it."""
    if not budget:
        return None
    try:
        from google.genai import types
    except ImportError:
        return None
    enum = getattr(types, "MediaResolution", None)
    if enum is None:
        return None
    mapping = {
        TOKEN_BUDGET_LOW: getattr(enum, "MEDIA_RESOLUTION_LOW", None),
        TOKEN_BUDGET_MEDIUM: getattr(enum, "MEDIA_RESOLUTION_MEDIUM", None),
        TOKEN_BUDGET_HIGH: getattr(enum, "MEDIA_RESOLUTION_HIGH", None),
    }
    return mapping.get(budget)


def _media_has_audio_or_video(media: Iterable[Tuple[str | Path | bytes, str]]) -> bool:
    for _, mime in media:
        mime_l = (mime or "").lower()
        if mime_l.startswith("audio/") or mime_l.startswith("video/"):
            return True
    return False


def call_google_genai_multimodal(
    *,
    api_key: str,
    model: str,
    system_instruction: str,
    user_text: str,
    media: Iterable[Tuple[str | Path | bytes, str]] = (),
    temperature: float = 0.1,
    max_output_tokens: int = 8192,
    media_resolution: Optional[str] = None,
    include_thoughts: bool = False,
    thinking_budget: Optional[int] = None,
    demo4: bool = False,
) -> GenAIResult:
    """
    Single-turn Gemma 4 / Gemini call with optional thinking and visual token budget.

    ``media`` is a sequence of ``(path_or_bytes, mime_type)``. Paths are read off
    disk; raw ``bytes`` (used by the per-page demo cell after `render_pdf_pages`)
    are passed straight through to ``Part.from_bytes``.

    ``media_resolution`` accepts ``"HIGH"`` / ``"MEDIUM"`` / ``"LOW"`` and maps to
    the SDK's ``MediaResolution`` enum when available; older SDKs silently fall
    back to the model default. ``include_thoughts=True`` asks the model for its
    reasoning trace, which is returned in ``GenAIResult.thoughts``.

    Hybrid default: AI Studio (``google-genai``) for models listed on your API key.
    Hugging Face is used automatically for E2B-only checkpoints (see
    ``gemma_hf_backend.model_requires_huggingface``). Set
    ``GOVERNANCE_LLM_BACKEND=huggingface`` to force all calls local.
    """
    media_list = list(media)
    if not demo4 and demo4_uses_huggingface() and _media_has_audio_or_video(media_list):
        demo4 = True

    try:
        from .gemma_hf_backend import call_gemma_hf_multimodal, use_huggingface_for_model

        if use_huggingface_for_model(model, demo4=demo4):
            hf = call_gemma_hf_multimodal(
                model=model,
                system_instruction=system_instruction,
                user_text=user_text,
                media=media,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                media_resolution=media_resolution,
                include_thoughts=include_thoughts,
                thinking_budget=thinking_budget,
            )
            return GenAIResult(
                text=hf.text,
                thoughts=hf.thoughts,
                raw_response=hf.raw_response,
            )
    except ImportError:
        pass

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    parts: List[Any] = [types.Part.from_text(text=user_text)]
    for item, mime in media:
        if isinstance(item, (bytes, bytearray)):
            data = bytes(item)
        else:
            data = Path(item).read_bytes()
        parts.append(types.Part.from_bytes(data=data, mime_type=mime))

    config_kwargs: Dict[str, Any] = dict(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )

    mr = _media_resolution_value(media_resolution)
    if mr is not None:
        config_kwargs["media_resolution"] = mr

    if (include_thoughts or thinking_budget is not None) and model_supports_thinking(model):
        ThinkingConfig = getattr(types, "ThinkingConfig", None)
        if ThinkingConfig is not None:
            tc_kwargs: Dict[str, Any] = {}
            if include_thoughts:
                tc_kwargs["include_thoughts"] = True
            if (
                thinking_budget is not None
                and model_supports_thinking_budget(model)
            ):
                tc_kwargs["thinking_budget"] = thinking_budget
            if tc_kwargs:
                config_kwargs["thinking_config"] = ThinkingConfig(**tc_kwargs)
    elif include_thoughts or thinking_budget is not None:
        print(
            f"   ℹ️  Skipping thinking_config: {model!r} does not support it. "
            "Demo 3's `.thoughts.md` may be empty — set "
            "`GOVERNANCE_THINKING_MODEL=gemma-4-31b-it` (default) or "
            "`GOVERNANCE_FORCE_THINKING=1` for other Gemma ids."
        )

    from .genai_quota_retry import call_with_genai_quota_retry

    use_stream = os.environ.get("GOVERNANCE_GENAI_STREAM", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    def _generate(cfg: Dict[str, Any]):
        contents = [types.Content(role="user", parts=parts)]
        gen_cfg = types.GenerateContentConfig(**cfg)
        if use_stream:
            stream = client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=gen_cfg,
            )
            answer_stream: List[str] = []
            last_chunk: Any = None
            for chunk in stream:
                last_chunk = chunk
                if getattr(chunk, "text", None):
                    answer_stream.append(chunk.text)
            text_joined = "".join(answer_stream)
            if text_joined:
                return _StreamGenAIResponse(text_joined, last_chunk)
        return client.models.generate_content(
            model=model,
            contents=contents,
            config=gen_cfg,
        )

    def _generate_with_thinking_fallback() -> Any:
        try:
            return _generate(config_kwargs)
        except Exception as exc:
            if "thinking budget" not in _genai_error_text(exc):
                raise
            stripped = {
                k: v
                for k, v in config_kwargs.items()
                if k != "thinking_config"
            }
            print(
                f"   ℹ️  {model!r}: thinking_budget rejected — retrying without "
                "thinking_config.",
                flush=True,
            )
            return _generate(stripped)

    response = call_with_genai_quota_retry(
        _generate_with_thinking_fallback, label=f"genai {model}"
    )

    if isinstance(response, _StreamGenAIResponse):
        return GenAIResult(
            text=response.text,
            thoughts="",
            raw_response=response.last_chunk,
        )

    answer_bits: List[str] = []
    thought_bits: List[str] = []
    for cand in getattr(response, "candidates", None) or []:
        content = getattr(cand, "content", None)
        for p in getattr(content, "parts", None) or []:
            text = getattr(p, "text", None)
            if not text:
                continue
            if getattr(p, "thought", False):
                thought_bits.append(text)
            else:
                answer_bits.append(text)

    text_out = "".join(answer_bits) or (getattr(response, "text", "") or "")
    return GenAIResult(
        text=text_out,
        thoughts="\n".join(thought_bits).strip(),
        raw_response=response,
    )


def probe_google_gemma_studio(
    api_key: str,
    *,
    models: Optional[List[str]] = None,
    audio_path: Optional[Path] = None,
    stream_text: bool = True,
) -> Dict[str, Dict[str, str]]:
    """
    Colab diagnostic: text ``generate_content_stream`` (the common blog "hack") plus
    optional ``Part.from_bytes`` audio on the same model ids.

    Returns ``{model_id: {"text_stream": "ok"|"fail:…", "audio": "ok"|"skip"|"fail:…"}}``.
    """
    from google import genai
    from google.genai import types

    try:
        from .gatekeeper_triage import _list_available_model_ids, _build_genai_client

        client = _build_genai_client(api_key)
        available = set(_list_available_model_ids(client))
    except Exception:
        client = genai.Client(api_key=api_key)
        available = set()

    candidates = models or [
        "gemma-4-26b-a4b-it",
        "gemma-4-e2b-it",
        "gemma-4-e4b-it",
        "gemma-4-31b-it",
        "gemini-2.0-flash",
    ]
    if available:
        candidates = [m for m in candidates if m in available] + [
            m for m in sorted(available) if "gemma" in m.lower() and m not in candidates
        ][:3]

    audio_bytes: Optional[bytes] = None
    audio_mime = ""
    if audio_path and Path(audio_path).is_file():
        audio_bytes = Path(audio_path).read_bytes()
        audio_mime = mime_for(audio_path)

    out: Dict[str, Dict[str, str]] = {}
    for model in candidates:
        row: Dict[str, str] = {}
        if stream_text:
            try:
                stream = client.models.generate_content_stream(
                    model=model,
                    contents="Reply with exactly: OK",
                )
                text = "".join(getattr(c, "text", None) or "" for c in stream)
                row["text_stream"] = "ok" if text.strip() else "ok (empty)"
            except Exception as exc:
                row["text_stream"] = f"fail: {exc}"
        if audio_bytes:
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=[
                        types.Content(
                            role="user",
                            parts=[
                                types.Part.from_text(
                                    text="One sentence: what is heard in this clip?"
                                ),
                                types.Part.from_bytes(
                                    data=audio_bytes, mime_type=audio_mime
                                ),
                            ],
                        )
                    ],
                )
                snippet = (getattr(resp, "text", None) or "")[:120]
                row["audio"] = f"ok: {snippet!r}"
            except Exception as exc:
                row["audio"] = f"fail: {exc}"
        else:
            row["audio"] = "skip (no audio_path)"
        out[model] = row
    return out


def print_probe_google_gemma_studio(
    api_key: str,
    *,
    audio_path: Optional[Path] = None,
    models: Optional[List[str]] = None,
) -> Dict[str, Dict[str, str]]:
    """Pretty-print :func:`probe_google_gemma_studio` results."""
    results = probe_google_gemma_studio(
        api_key, models=models, audio_path=audio_path
    )
    print("Google AI Studio Gemma probe (text stream + optional audio bytes)")
    for model, row in results.items():
        print(f"\n  {model}")
        for key, val in row.items():
            print(f"    {key}: {val}")
    return results


# ─────────────────────────────────────────────────────────────
# Plain-transcription pass — provenance artifact for the Ledger of Influence.
# Distinct from Demo 4's policy_analysis_v1 pass: this returns *only* the literal
# transcribed text, with no analysis, no JSON, no chunk metadata. The output is
# the citable raw audio-to-text that downstream demos / human reviewers can
# anchor against.
# ─────────────────────────────────────────────────────────────


# Display name → BCP-47-ish language tag used in the output file suffix.
TRANSCRIPTION_SUPPORTED_LANGUAGES: Dict[str, str] = {
    "English": "en",
    "Spanish": "es",
}


def _resolve_language_display(language: str) -> Tuple[str, str]:
    """Accept ``"en"`` / ``"es"`` / ``"English"`` / ``"Spanish"`` (any case) and
    return ``(display_name, short_tag)`` — display goes into the prompt, short
    tag goes into the output file suffix."""
    if not language:
        raise ValueError("language is required (one of: en, es, English, Spanish)")
    key = language.strip()
    # Short tag → display
    for display, tag in TRANSCRIPTION_SUPPORTED_LANGUAGES.items():
        if key.lower() == tag.lower() or key.lower() == display.lower():
            return display, tag
    raise ValueError(
        f"Unsupported transcription language {language!r}. "
        f"Supported: {list(TRANSCRIPTION_SUPPORTED_LANGUAGES)} (or short tags en/es)."
    )


def transcribe_audio_with_gemma(
    *,
    api_key: str,
    model: str,
    audio_path: str | Path | bytes,
    language: str = "English",
    mime_type: Optional[str] = None,
    max_output_tokens: int = 8192,
) -> str:
    """
    Transcribe one audio file / chunk to literal text in ``language``.

    Uses the exact prompt template requested for the 2026 Gemma 4 Good Hackathon:

        Transcribe the following speech segment in {LANGUAGE} into {LANGUAGE} text.

        Follow these specific instructions for formatting the answer:
        *   Only output the transcription, with no newlines.
        *   When transcribing numbers, write the digits, i.e. write 1.7 and not
            one point seven, and write 3 instead of three.

    ``language`` accepts ``"en"`` / ``"es"`` (short tag) or ``"English"`` /
    ``"Spanish"`` (display name). ``audio_path`` accepts a path *or* raw bytes
    (handy for piping the in-memory chunks ffmpeg already produced). Returns the
    raw transcript string with any stray newlines collapsed to spaces (the model
    is told not to emit newlines, but we enforce it defensively).
    """
    display, _tag = _resolve_language_display(language)

    user_text = (
        f"Transcribe the following speech segment in {display} into {display} text.\n\n"
        "Follow these specific instructions for formatting the answer:\n"
        "*   Only output the transcription, with no newlines.\n"
        "*   When transcribing numbers, write the digits, i.e. write 1.7 and not "
        "one point seven, and write 3 instead of three."
    )

    # System prompt is intentionally minimal: we want a literal transcription,
    # not a political-science analysis layered on top.
    system_instruction = (
        "You are a precise speech-to-text transcriber. Return only the literal "
        "spoken words, in the requested language, on a single line."
    )

    if isinstance(audio_path, (bytes, bytearray)):
        media: List[Tuple[Any, str]] = [
            (bytes(audio_path), mime_type or "audio/mpeg"),
        ]
    else:
        p = Path(audio_path)
        media = [(p, mime_type or mime_for(p))]

    use_hf = demo4_uses_huggingface()
    tx_model = model
    if use_hf:
        try:
            from .gemma_hf_backend import resolve_transcription_hf_model

            tx_model = resolve_transcription_hf_model()
        except ImportError:
            pass
    else:
        explicit = os.environ.get("GOVERNANCE_TRANSCRIPTION_MODEL", "").strip()
        if explicit:
            tx_model = explicit

    result = call_google_genai_multimodal(
        api_key=api_key,
        model=tx_model,
        system_instruction=system_instruction,
        user_text=user_text,
        media=media,
        temperature=0.0,
        max_output_tokens=max_output_tokens,
        # Don't request thinking — transcription is mechanical, and Gemma 4 returns
        # 400 INVALID_ARGUMENT if thinking_config is attached to non-thinking variants.
        include_thoughts=False,
        thinking_budget=None,
        demo4=use_hf,
    )

    text = (result.text or "").strip()
    # The prompt forbids newlines; collapse any the model still produced so the
    # output file is a single-line transcript ready for downstream concat.
    text = " ".join(text.split())
    return text


# ─────────────────────────────────────────────────────────────
# EmbeddingGemma — semantic vectors for cross-jurisdiction clustering
# ─────────────────────────────────────────────────────────────


def embed_text_with_gemma(
    *,
    api_key: str,
    model: str,
    texts: List[str],
    batch_size: int = 32,
) -> List[List[float]]:
    """Return one embedding vector per input string. Batches under the SDK limit."""
    from google import genai

    client = genai.Client(api_key=api_key)
    out: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i + batch_size]
        result = client.models.embed_content(model=model, contents=chunk)
        for emb in getattr(result, "embeddings", None) or []:
            values = getattr(emb, "values", None) or []
            out.append(list(values))
    return out


def cosine_similarity_matrix(vectors: List[List[float]]) -> List[List[float]]:
    """Pairwise cosine similarity. Small-N pure-Python implementation — fine for
    the demo's hundreds-of-items scale; switch to numpy/sklearn for production."""
    import math

    norms = [math.sqrt(sum(x * x for x in v)) or 1.0 for v in vectors]
    n = len(vectors)
    out = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            dot = sum(a * b for a, b in zip(vectors[i], vectors[j]))
            sim = dot / (norms[i] * norms[j])
            out[i][j] = out[j][i] = sim
    return out


# ─────────────────────────────────────────────────────────────
# ShieldGemma — safety / policy-violation review on free-text outputs
# ─────────────────────────────────────────────────────────────


SHIELD_HARM_CATEGORIES = (
    "dangerous_content",
    "harassment",
    "hate_speech",
    "sexually_explicit",
)


def shield_review_text(
    *,
    api_key: str,
    model: str,
    content: str,
    user_prompt: str = "(none — automated pipeline output)",
    harm_categories: Iterable[str] = SHIELD_HARM_CATEGORIES,
) -> Dict[str, Any]:
    """Run a ShieldGemma-style policy review on ``content``.

    Returns a dict shaped like::

        {
          "flagged": bool,
          "categories": {"hate_speech": "No", "harassment": "No", ...},
          "raw": "<model output>"
        }

    The same pattern works against ShieldGemma proper and against general Gemma
    instruction-tuned models — it's just a structured Yes/No prompt.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    category_blocks = []
    for cat in harm_categories:
        category_blocks.append(
            f"- `{cat}`: does the chatbot response contain or promote {cat.replace('_', ' ')}?"
        )
    policy_prompt = (
        "You are a policy reviewer for an automated municipal-records pipeline.\n"
        "Decide whether the chatbot response below violates any of the safety policies "
        "listed. Answer with strict JSON only — no prose, no markdown fences.\n\n"
        f"Human question: {user_prompt}\n"
        f"Chatbot response:\n<<<\n{content}\n>>>\n\n"
        "Categories:\n"
        + "\n".join(category_blocks)
        + "\n\n"
        'Return JSON: {"verdicts": {"<category>": "Yes" | "No"}, "rationale": "<one short sentence>"}'
    )

    from .genai_quota_retry import call_with_genai_quota_retry

    def _generate():
        return client.models.generate_content(
            model=model,
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=policy_prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=512,
                response_mime_type="application/json",
            ),
        )

    response = call_with_genai_quota_retry(_generate, label=f"shield {model}")

    raw = ""
    for cand in getattr(response, "candidates", None) or []:
        for p in getattr(getattr(cand, "content", None), "parts", None) or []:
            t = getattr(p, "text", None)
            if t:
                raw += t

    import json as _json

    try:
        parsed = _json.loads(raw.strip().lstrip("`"))
    except Exception:
        parsed = {"verdicts": {}, "rationale": "(parse error)", "_raw": raw}

    verdicts = parsed.get("verdicts", {}) or {}
    flagged = any(str(v).strip().lower().startswith("y") for v in verdicts.values())
    return {
        "flagged": flagged,
        "categories": verdicts,
        "rationale": parsed.get("rationale", ""),
        "raw": raw,
    }


# ─────────────────────────────────────────────────────────────
# Policy Drift Detector (alternating-attention demo)
# ─────────────────────────────────────────────────────────────


_DRIFT_INSTRUCTION = """\
You are a Policy Drift Detector for one governance meeting that was split into
~15-minute audio chunks. Each chunk's analysis follows the
`prompts/policy_analysis_v1.md` schema verbatim — same field names, same slug
rules, same controlled vocabularies. Honor that schema; do not invent new
field names, do not collapse structure into a generic "framing" string.

==================== GROUPING ====================
Group everything by `subject_id` — the canonical cross-chunk key.

- The `subject_id` slug rule is fixed by the prompt: `subject_<descriptive_name>_<jurisdiction>`,
  all lowercase, underscores, no punctuation. The SAME real-world matter must
  collapse to the SAME slug regardless of which chunk it appears in.
- Pull subjects from each chunk's `subjects[]` array and from
  `decisions[].subject_id`.
- If two chunks reference the same matter with near-duplicate slugs (case,
  trailing words), canonicalize them to a single slug and note the merge in
  `slug_canonicalization` (see output shape).
- Include a subject if EITHER (a) it appears in 2+ chunks, OR (b) it appears in
  one chunk but shows internal contest (dissenting_interpretations non-empty,
  causal_interpretations Contested, or value_conflicts present). Skip
  uncontested single-chunk subjects.

==================== WHAT TO DETECT ====================
For every kept subject, trace drift along the SAME five dimensions used inside
`decisions[].narrative_analysis`. Emit one entry per chunk where that dimension
shifts materially — NOT every chunk. If a dimension is stable across the
meeting, omit it for that subject.

1. dominant_narrative_drift — chunk-to-chunk shifts in:
     narrative_label, problem_diagnosis, causal_story, blame_assignment,
     moral_foundation, proposed_remedy, narrative_champions[].
   A "material shift" means the diagnosis, blame, moral foundation, or remedy
   changed — not just rewording.

2. dissenting_emergence — moments when `dissenting_interpretations` first
   surface, gain ground, fade, or are co-opted. Capture:
     narrative_label, problem_diagnosis, moral_foundation,
     whose_interests_constrained[], narrative_champions[].

3. causal_interpretation_shifts — rival diagnoses moving across the
   accepted_or_rejected axis (Accepted by majority / Rejected by majority /
   Contested without resolution). Capture:
     causal_interpretation, evidence_cited, sponsored_by[], accepted_or_rejected.

4. value_conflict_arc — entries from `value_conflicts` keyed to the chunk where
   each tension first surfaces and how it resolves later. Capture:
     value_tension (format "X vs Y"), proponent_priority, opponent_priority,
     resolution_method.

5. tradeoff_evolution — shifts in `tradeoff_analysis`:
     tradeoff_statement (format "Advancing X by constraining Y"),
     interests_advanced[], interests_constrained[], acknowledged_explicitly,
     mitigation_proposed.

==================== NARRATIVE STABILITY (per subject) ====================
Produce one `narrative_stability_assessment` mirroring the prompt's
`narrative_analysis.narrative_stability`:
  - narrative_novelty — one of: "New interpretation introduced", "Extension of
    prior interpretation", "Continuation of established narrative",
    "Narrative reversal", "Unknown".
  - locks_in_narrative — bool.
  - durability_assessment — Smart Brevity headline: colon: detail.
  - future_decisions_constrained — list of subject slugs or topic areas.
  - narrative_evolution_note — null or short string describing the arc.

==================== WRITING STYLE ====================
Smart Brevity on every text field: headline, colon, essential detail, cut the
rest. No filler clauses. No "the council discussed…" framing.

==================== MERMAID TIMELINE (per subject) ====================
Per subject produce a `diagram_timeline` that obeys the prompt's diagram rules:
  - first line: `timeline` keyword.
  - one section labeled `Across Meeting Chunks`.
  - entries keyed by `"chunk_<n>"` (quoted), one colon per entry.
  - 10 words or fewer per entry.
  - newlines escaped as \\n for JSON.

==================== OUTPUT SHAPE ====================
Return one JSON object. No markdown fences. No prose. No trailing commentary.

{
  "subjects": [
    {
      "subject_id": "string — canonical slug per the prompt's rule",
      "subject_label": "string",
      "first_chunk_index": int,
      "last_chunk_index": int,
      "appeared_in_chunks": [int, ...],
      "drift_observed": bool,
      "drift_headline": "Smart Brevity: headline: detail",
      "slug_canonicalization": [
        {"raw_slug": "string", "merged_into": "string"}
      ],
      "dominant_narrative_drift": [
        {
          "chunk_index": int,
          "narrative_label": "string",
          "problem_diagnosis": "string",
          "causal_story": "string",
          "blame_assignment": "string",
          "moral_foundation": "string",
          "proposed_remedy": "string",
          "narrative_champions": ["string"]
        }
      ],
      "dissenting_emergence": [
        {
          "chunk_index": int,
          "narrative_label": "string",
          "problem_diagnosis": "string",
          "moral_foundation": "string",
          "whose_interests_constrained": ["string"],
          "narrative_champions": ["string"]
        }
      ],
      "causal_interpretation_shifts": [
        {
          "chunk_index": int,
          "causal_interpretation": "string — format: X caused Y",
          "evidence_cited": "string or null",
          "sponsored_by": ["string"],
          "accepted_or_rejected": "Accepted by majority | Rejected by majority | Contested without resolution"
        }
      ],
      "value_conflict_arc": [
        {
          "chunk_index": int,
          "value_tension": "string — format: X vs Y",
          "proponent_priority": "string",
          "opponent_priority": "string",
          "resolution_method": "string"
        }
      ],
      "tradeoff_evolution": [
        {
          "chunk_index": int,
          "tradeoff_statement": "string — format: Advancing X by constraining Y",
          "interests_advanced": ["string"],
          "interests_constrained": ["string"],
          "acknowledged_explicitly": bool,
          "mitigation_proposed": "string or null"
        }
      ],
      "narrative_stability_assessment": {
        "narrative_novelty": "string — controlled vocabulary above",
        "locks_in_narrative": bool,
        "durability_assessment": "string",
        "future_decisions_constrained": ["string"],
        "narrative_evolution_note": "string or null"
      },
      "diagram_timeline": "string — valid Mermaid timeline with \\n escapes"
    }
  ],
  "meeting_level_summary": {
    "headline": "Smart Brevity: meeting-wide drift takeaway",
    "subjects_tracked": int,
    "subjects_with_drift": int,
    "emergent_value_tensions": ["string — X vs Y"],
    "locked_in_narratives": ["string — subject_id"],
    "reversed_narratives": ["string — subject_id"]
  }
}
"""


def resolve_drift_model(
    demo4_chunk_model: str,
    *,
    thinking_model: str = "",
) -> Tuple[str, bool]:
    """
    Model for policy drift (text-only JSON merge).

    Default: **thinking / reasoning** model on Google AI Studio (``GOVERNANCE_THINKING_MODEL``),
    not E2B/E4B. Edge models are for transcription and native audio chunks only.
    Set ``GOVERNANCE_DRIFT_USE_HF=1`` to run drift on local E2B weights.
    """
    explicit = os.environ.get("GOVERNANCE_DRIFT_MODEL", "").strip()
    if explicit:
        try:
            from .gemma_hf_backend import use_huggingface_for_model

            return explicit, use_huggingface_for_model(explicit, demo4=False)
        except ImportError:
            return explicit, False
    if os.environ.get("GOVERNANCE_DRIFT_USE_HF", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        try:
            from .gemma_hf_backend import resolve_demo4_hf_model

            return resolve_demo4_hf_model(demo4_chunk_model), True
        except ImportError:
            pass
    tm = (
        thinking_model
        or os.environ.get("GOVERNANCE_THINKING_MODEL", "gemma-4-31b-it")
    ).strip()
    return tm, False


def policy_drift_summarize(
    chunk_jsons: List[Dict[str, Any]],
    *,
    api_key: str,
    model: str,
    thinking_model: str = "",
    focus_hint: Optional[str] = None,
    max_output_tokens: int = 8192,
    instruction_override: Optional[str] = None,
    canonical_prompt_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run a follow-up Gemma pass that consumes per-chunk policy-analysis JSON
    (each chunk already conforms to ``prompts/policy_analysis_v1.md``) and
    surfaces, per ``subject_id``, how the meeting's narrative evolved across
    chunks along the five ``narrative_analysis`` dimensions defined in the
    canonical prompt: dominant_narrative, dissenting_interpretations,
    causal_interpretations, value_conflicts, tradeoff_analysis — plus a
    per-subject narrative_stability_assessment.

    The default instruction is :data:`_DRIFT_INSTRUCTION`, which is kept in
    lockstep with the canonical prompt's schema. Pass ``instruction_override``
    to swap it wholesale. Pass ``canonical_prompt_text`` to additionally pin
    the canonical prompt body into context (useful if the prompt has been
    edited and you want the model to honor the latest field set verbatim
    without changing this module).
    """
    payload = {
        "focus_hint": focus_hint,
        "chunks": [
            {"chunk_index": i, "analysis": ja}
            for i, ja in enumerate(chunk_jsons)
            if isinstance(ja, dict) and "_error" not in ja
        ],
    }
    if not payload["chunks"]:
        return {
            "_error": "no parseable chunk analyses",
            "subjects": [],
            "meeting_level_summary": {},
        }

    instruction = instruction_override or _DRIFT_INSTRUCTION
    sections = [instruction]
    if canonical_prompt_text:
        sections.append(
            "=== CANONICAL_PROMPT (policy_analysis_v1.md) ===\n"
            + canonical_prompt_text.strip()
        )
    sections.append(
        "=== CHUNK_ANALYSES ===\n"
        + json.dumps(payload, ensure_ascii=False)[:180_000]
    )
    user_text = "\n\n".join(sections)

    drift_model, use_hf = resolve_drift_model(model, thinking_model=thinking_model)
    try:
        from .colab_timed_steps import log_line

        backend = "Hugging Face" if use_hf else "Google AI Studio"
        log_line(f"drift pass: {drift_model!r} ({backend})", prefix="    ")
    except ImportError:
        pass

    result = call_google_genai_multimodal(
        api_key=api_key,
        model=drift_model,
        system_instruction=(
            "You are a Policy Drift Detector. Honor the policy_analysis_v1.md "
            "schema exactly — preserve subject_id slug rules and the five "
            "narrative_analysis dimensions (dominant_narrative, "
            "dissenting_interpretations, causal_interpretations, "
            "value_conflicts, tradeoff_analysis). Return only valid JSON in "
            "the requested shape; no markdown fences, no prose."
        ),
        user_text=user_text,
        media=(),
        temperature=0.1,
        max_output_tokens=max_output_tokens,
        include_thoughts=False,
        demo4=use_hf,
    )
    try:
        return json.loads(_extract_json_object(result.text))
    except (json.JSONDecodeError, ValueError) as e:
        return {
            "_error": str(e),
            "_raw_preview": result.text[:2000],
            "subjects": [],
            "meeting_level_summary": {},
        }


# ─────────────────────────────────────────────────────────────
# Per-jurisdiction reference data enrichment
#
# Two parallel buckets live under ``02_reference_data/``:
#   - ``meeting_data_by_jurisdiction_id/`` — Orbis exports, registry rows, any
#     other per-jurisdiction reference material (JSON lookups + PDFs). The JSON
#     merge step picks up files matching ``*_lookup_by_jurisdiction_id.json``.
#   - ``contacts_by_jurisdiction_id/`` — scraped / curated contact rosters,
#     keyed by ``jurisdiction_id`` (NOT ``org_id``). Same lookup-file convention.
#
# Both buckets attach to ``analysis`` under named profile fields so downstream
# consumers can tell where each blob came from.
# ─────────────────────────────────────────────────────────────


def _load_lookup_dir(reference_dir: Path) -> Dict[str, Any]:
    """
    Merge every ``*_lookup_by_jurisdiction_id.json`` file under ``reference_dir``
    into one dict keyed by ``jurisdiction_id``. Later files win on key collisions.
    PDFs and other non-lookup files in the directory are ignored here — they
    live alongside the lookups as human-readable reference material.
    """
    if not reference_dir.is_dir():
        return {}
    combined: Dict[str, Any] = {}
    for path in sorted(reference_dir.glob("*_lookup_by_jurisdiction_id.json")):
        try:
            combined.update(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return combined


def load_meeting_data_lookup(meeting_data_dir: Path) -> Dict[str, Any]:
    """
    Load every ``*_lookup_by_jurisdiction_id.json`` file under
    ``02_reference_data/meeting_data_by_jurisdiction_id/`` (Orbis exports plus any
    other per-jurisdiction registry data) into one combined lookup.
    """
    return _load_lookup_dir(meeting_data_dir)


def load_contacts_lookup(contacts_dir: Path) -> Dict[str, Any]:
    """
    Load every ``*_lookup_by_jurisdiction_id.json`` file under
    ``02_reference_data/contacts_by_jurisdiction_id/`` into one combined lookup.
    Contacts are referenced by ``jurisdiction_id`` — never by ``org_id``.
    """
    return _load_lookup_dir(contacts_dir)


def merge_meeting_data_by_jurisdiction(
    analysis: Dict[str, Any],
    meeting_data_by_jurisdiction_id: Dict[str, Any],
    jurisdiction_id: str,
) -> Dict[str, Any]:
    """
    Attach the per-jurisdiction reference row (Orbis registry, etc.) to the
    top-level analysis under ``meeting_data_profile``. Mutates and returns
    ``analysis``.

    The jurisdiction id is the canonical cross-reference key for this project
    (``JurisdictionDir.jurisdiction_id``, e.g. ``jurisdiction_al_county_01125``).
    """
    if not isinstance(analysis, dict):
        return analysis
    if not jurisdiction_id or jurisdiction_id not in meeting_data_by_jurisdiction_id:
        return analysis
    payload = meeting_data_by_jurisdiction_id[jurisdiction_id]
    analysis["jurisdiction_id"] = jurisdiction_id
    analysis["meeting_data_profile"] = payload
    meeting = analysis.get("meeting")
    if isinstance(meeting, dict):
        meeting.setdefault("jurisdiction_id", jurisdiction_id)
    return analysis


def merge_contacts_by_jurisdiction(
    analysis: Dict[str, Any],
    contacts_by_jurisdiction_id: Dict[str, Any],
    jurisdiction_id: str,
) -> Dict[str, Any]:
    """
    Attach the per-jurisdiction contact roster to the top-level analysis under
    ``contacts_profile``. Mutates and returns ``analysis``. Contacts are keyed
    by ``jurisdiction_id`` — never by ``org_id`` — so the same roster covers
    every committee / department / board within a jurisdiction.
    """
    if not isinstance(analysis, dict):
        return analysis
    if not jurisdiction_id or jurisdiction_id not in contacts_by_jurisdiction_id:
        return analysis
    payload = contacts_by_jurisdiction_id[jurisdiction_id]
    analysis["jurisdiction_id"] = jurisdiction_id
    analysis["contacts_profile"] = payload
    meeting = analysis.get("meeting")
    if isinstance(meeting, dict):
        meeting.setdefault("jurisdiction_id", jurisdiction_id)
    return analysis


# ─────────────────────────────────────────────────────────────
# Mime helpers (used by the per-jurisdiction processing cell)
# ─────────────────────────────────────────────────────────────


def mime_for(path: Path) -> str:
    """Cheap, deterministic mime resolution for the file types we accept."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "application/pdf"
    if ext in IMAGE_EXTS:
        return "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    if ext in AUDIO_EXTS:
        if ext == ".mp3":
            return "audio/mpeg"
        if ext == ".wav":
            return "audio/wav"
        if ext == ".webm":
            return "audio/webm"
        if ext == ".mp4":
            return "video/mp4"
        if ext == ".opus":
            return "audio/opus"
        return f"audio/{ext.lstrip('.')}"
    return "application/octet-stream"


# ─────────────────────────────────────────────────────────────
# Backwards-compatibility: legacy OpenAI-compatible call kept for the
# `02_run_meeting_llm.ipynb` Together.ai cell in the prior notebook revision.
# Not used by the Gemma 4 demo cells.
# ─────────────────────────────────────────────────────────────


@dataclass
class OpenAICompatibleConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.1
    max_tokens: int = 8192


def call_openai_compatible_chat(
    *,
    config: OpenAICompatibleConfig,
    system_prompt: str,
    user_content: str,
) -> str:
    from openai import OpenAI

    client = OpenAI(base_url=config.base_url, api_key=config.api_key)
    resp = client.chat.completions.create(
        model=config.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    choice = resp.choices[0]
    if not choice.message or not choice.message.content:
        return ""
    return choice.message.content


__all__ = [
    "DOCUMENT_BREAK",
    "PDF_EXTS", "AUDIO_EXTS", "VIDEO_EXTS", "VIDEO_CONTAINER_EXTS", "IMAGE_EXTS",
    "TOKEN_BUDGET_HIGH", "TOKEN_BUDGET_MEDIUM", "TOKEN_BUDGET_LOW",
    "JurisdictionDir", "MeetingInventory", "format_inventory_media_line",
    "PdfPageRender", "GenAIResult",
    "load_text_file", "chunk_text",
    "parse_policy_analysis_response",
    "parse_jurisdiction_dir", "walk_raw_inputs", "mirror_output_path",
    "VIDEO_ASSETS_DIRNAME",
    "inventory_video_assets_enabled",
    "discover_media_from_video_asset_manifests",
    "enrich_inventory_video_assets",
    "select_demo4_media",
    "classify_pdf_page_heuristic", "render_pdf_pages",
    "extract_pdf_digital_text", "is_scanned_pdf",
    "demo3_input_mode", "demo3_text_first_enabled",
    "demo1_skip_when_digital", "demo2_skip_when_digital",
    "demo3_min_digital_chars", "demo3_max_document_chars",
    "truncate_demo3_document_text",
    "transcode_video_to_opus",
    "prepare_meeting_audio_for_processing",
    "chunk_audio_ffmpeg",
    "call_google_genai_multimodal",
    "transcribe_audio_with_gemma", "TRANSCRIPTION_SUPPORTED_LANGUAGES",
    "embed_text_with_gemma", "cosine_similarity_matrix",
    "shield_review_text", "SHIELD_HARM_CATEGORIES",
    "model_supports_thinking",
    "model_supports_thinking_budget",
    "model_supports_audio_video_input",
    "model_supports_video_input",
    "resolve_demo4_genai_model",
    "resolve_demo4_model",
    "demo4_uses_huggingface",
    "demo4_media_work_dir",
    "resolve_scraped_opus_for_media",
    "probe_google_gemma_studio",
    "print_probe_google_gemma_studio",
    "_demo4_allow_a4b_audio",
    "resolve_drift_model",
    "policy_drift_summarize",
    "load_meeting_data_lookup", "load_contacts_lookup",
    "merge_meeting_data_by_jurisdiction", "merge_contacts_by_jurisdiction",
    "mime_for",
    "force_reprocess_outputs",
    "read_json_file",
    "text_output_complete",
    "policy_chunk_output_complete",
    "demo2_page_output_complete",
    "demo2_pdf_outputs_complete",
    "demo3_thinking_json_complete",
    "demo4_drift_output_complete",
    "load_demo4_chunk_analyses",
    "find_existing_audio_chunks",
    "demo4_use_video_chunks",
    "find_existing_demo4_chunks",
    "discover_demo4_chunk_media",
    "demo4_prefer_opus_chunks",
    "demo4_prefer_gemma_for_audio",
    "iter_demo4_ingest_strategies",
    "chunk_meeting_media_for_demo4",
    "OpenAICompatibleConfig", "call_openai_compatible_chat",
]
