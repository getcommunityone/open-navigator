#!/usr/bin/env python3
"""
Gatekeeper Triage — "The Ledger of Influence" data-gating layer (2026 Gemma 4 Good Hackathon).

Walks ``<raw_root>/`` (default: ``My Drive/CommunityOne/governance_pipeline_data/01_raw_inputs/``)
recursively with :func:`os.walk`, sends each PDF / audio file to a Gemma multimodal
triage call, and routes the file based on the model's verdict:

* **PROCEED** (``is_governance_meeting=True`` and confidence ≥ threshold) — leave the
  file in place so downstream pipelines (notebook ``02_run_meeting_llm.ipynb`` / Gatekeeper
  step 2) pick it up.
* **EXCLUDE** — replicate the file's geography subtree under
  ``<raw_root>/excluded_inputs/<STATE>/<scope>/<jurisdiction>/...`` and ``shutil.move()`` the
  original there. The exclusion subtree is itself skipped on subsequent runs (idempotent).

The triage layer is intentionally cheap:

* **Audio Gatekeeper** — clips the first ``--audio-window-seconds`` of audio via
  ``ffmpeg`` and sends the bytes directly to Gemma. The prompt forces the model to
  listen for *structural audio cues* (gavel, roll call, public comment cadence) and
  return strict JSON only.
* **Visual PDF Gatekeeper** — renders the first ``--pdf-pages`` pages with
  ``pdf2image`` at 200 DPI, sends them at **HIGH** ``media_resolution`` (~1,120 image
  tokens) so layout / OCR fidelity is preserved, and asks the model to label the
  document as ``"meeting_agenda" | "meeting_minutes" | "other"``.

Every API call and every move is wrapped in ``try / except`` so a single bad file or
API timeout never aborts a batch sweep. Every action prints the file's geographic
origin (``AL/county/county_01125/2026/foo.pdf``) for live demos.

CLI::

    python scripts/colab/gatekeeper_triage.py --raw-root /content/drive/MyDrive/CommunityOne/governance_pipeline_data/01_raw_inputs
    python scripts/colab/gatekeeper_triage.py --raw-root /path --dry-run
    python scripts/colab/gatekeeper_triage.py --raw-root /path --kinds pdf
    python scripts/colab/gatekeeper_triage.py --raw-root /path --report-path /tmp/triage_report.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

PDF_EXTS = {".pdf"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".webm", ".mp4"}

# Excluded-inputs sub-folder under the raw root (per the project spec).
EXCLUDED_DIRNAME = "excluded_inputs"

# Folders the walker should never descend into. ``_contact_images`` is intentionally
# kept walk-able — image triage / enrichment happens elsewhere; only the scraper-temp
# caches and the exclusion bucket itself are pruned.
SKIP_DIR_PREFIXES: tuple[str, ...] = ()
SKIP_DIR_NAMES = {
    "__pycache__", ".ipynb_checkpoints",
    "_crawl_html", "_sitemaps",
    EXCLUDED_DIRNAME,
}

def _default_gatekeeper_model() -> str:
    try:
        from gemma_hf_backend import DEFAULT_HF_MODEL_ID, use_huggingface

        if use_huggingface():
            return (
                os.environ.get("GOVERNANCE_GATEKEEPER_MODEL", "").strip()
                or os.environ.get("GOVERNANCE_GENAI_MODEL", "").strip()
                or DEFAULT_HF_MODEL_ID
            )
    except ImportError:
        pass
    return (
        os.environ.get("GOVERNANCE_GATEKEEPER_MODEL", "").strip()
        or os.environ.get("GOVERNANCE_GENAI_MODEL", "gemma-4-26b-a4b-it").strip()
    )


# Default model — override with --model or env GOVERNANCE_GATEKEEPER_MODEL.
DEFAULT_MODEL = _default_gatekeeper_model()

# Triage cost / latency caps.
DEFAULT_AUDIO_WINDOW_SECONDS = 120          # send only the first N seconds for triage
DEFAULT_PDF_PAGES = 2                       # first N PDF pages → image bytes
DEFAULT_PDF_DPI = 200
DEFAULT_TRIAGE_MAX_OUTPUT_TOKENS = 512      # strict JSON only — keep cheap
DEFAULT_CONFIDENCE_THRESHOLD = 0.6

# Triage JSON schema (also enforced via response_schema where the SDK supports it).
TRIAGE_JSON_FIELDS = {
    "is_governance_meeting": "boolean — true iff this is the audio/document of an official local government public meeting",
    "document_or_audio_type": "string — one of: meeting_agenda, meeting_minutes, meeting_audio, meeting_video, reference_packet, invoice, brochure, correspondence, other",
    "confidence_score": "number between 0.0 and 1.0 — your confidence in is_governance_meeting",
    "reasoning": "string — short Smart-Brevity rationale: headline, colon, evidence cited from the file",
}

logger = logging.getLogger("gatekeeper")


# ─────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────


@dataclass
class TriageVerdict:
    """Strict shape returned by every triage call. Mirrors the JSON schema."""

    is_governance_meeting: bool
    document_or_audio_type: str
    confidence_score: float
    reasoning: str
    # Local routing metadata — not part of the model JSON.
    proceed: bool = False
    triage_kind: str = ""        # "pdf" | "audio"
    file_path: str = ""          # absolute path at triage time
    relative_path: str = ""      # path relative to raw_root, with forward slashes
    geography_label: str = ""    # e.g. "AL/county/county_01125/2026"
    elapsed_seconds: float = 0.0
    error: Optional[str] = None  # populated on call / parse failures
    raw_model_text: Optional[str] = None


@dataclass
class TriageReport:
    raw_root: str
    excluded_root: str
    proceed: List[TriageVerdict] = field(default_factory=list)
    excluded: List[TriageVerdict] = field(default_factory=list)
    errors: List[TriageVerdict] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)

    def add(self, v: TriageVerdict) -> None:
        if v.error:
            self.errors.append(v)
        elif v.proceed:
            self.proceed.append(v)
        else:
            self.excluded.append(v)

    def to_dict(self) -> dict:
        return {
            "raw_root": self.raw_root,
            "excluded_root": self.excluded_root,
            "counts": {
                "proceed": len(self.proceed),
                "excluded": len(self.excluded),
                "errors": len(self.errors),
                "skipped": len(self.skipped),
            },
            "proceed": [asdict(v) for v in self.proceed],
            "excluded": [asdict(v) for v in self.excluded],
            "errors": [asdict(v) for v in self.errors],
            "skipped": self.skipped,
        }


# ─────────────────────────────────────────────────────────────
# Geography helpers — relative path → state / scope / jurisdiction labels
# ─────────────────────────────────────────────────────────────


def relative_geography(file_path: Path, raw_root: Path) -> Tuple[str, str]:
    """
    Return ``(relative_path_str, geography_label)``.

    * ``relative_path_str`` — POSIX-style path of ``file_path`` relative to
      ``raw_root`` (e.g. ``AL/county/county_01125/2026/minutes.pdf``).
    * ``geography_label`` — the **parent** directory portion of that relative path,
      i.e. everything except the file name. Used in log lines so judges can read
      where in the geography tree the file came from.
    """
    rel = file_path.resolve().relative_to(raw_root.resolve())
    rel_str = rel.as_posix()
    geo = rel.parent.as_posix() if rel.parent != Path(".") else ""
    return rel_str, geo


# ─────────────────────────────────────────────────────────────
# Audio clip preparation (ffmpeg)
# ─────────────────────────────────────────────────────────────


def _ensure_ffmpeg() -> None:
    try:
        subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, check=True, timeout=10
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(
            "ffmpeg is required for audio triage. On Colab it ships by default; "
            "locally run `apt-get install -y ffmpeg` or `brew install ffmpeg`."
        ) from e


def clip_audio_window(audio_path: Path, seconds: int, out_path: Path) -> Path:
    """
    Extract the first ``seconds`` of ``audio_path`` to ``out_path`` as mono 16 kHz
    MP3. This is the *programmatic token constraint* on the audio gatekeeper —
    we cap how deeply Gemma processes the stream by clipping the input window.
    """
    _ensure_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(audio_path),
        "-t", str(max(5, int(seconds))),
        "-ac", "1", "-ar", "16000",
        "-c:a", "libmp3lame", "-q:a", "5",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, timeout=300)
    return out_path


# ─────────────────────────────────────────────────────────────
# PDF → first-N-pages PNG bytes (pdf2image)
# ─────────────────────────────────────────────────────────────


def pdf_first_pages_to_png_bytes(
    pdf_path: Path, *, pages: int = DEFAULT_PDF_PAGES, dpi: int = DEFAULT_PDF_DPI
) -> List[bytes]:
    """
    Convert the first ``pages`` pages of ``pdf_path`` to in-memory PNG bytes via
    ``pdf2image``. Requires the ``poppler`` system package and the ``pdf2image``
    Python wheel.
    """
    try:
        from pdf2image import convert_from_path  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "pdf2image is required for PDF triage. Install with "
            "`pip install pdf2image` and ensure poppler is on PATH "
            "(Colab: pre-installed; Debian/Ubuntu: apt-get install -y poppler-utils; "
            "macOS: brew install poppler)."
        ) from exc

    import io

    imgs = convert_from_path(
        str(pdf_path),
        dpi=dpi,
        first_page=1,
        last_page=max(1, int(pages)),
        fmt="png",
    )
    out: List[bytes] = []
    for im in imgs:
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        out.append(buf.getvalue())
    return out


# ─────────────────────────────────────────────────────────────
# Gemma client wrapper — strict-JSON multimodal triage call
# ─────────────────────────────────────────────────────────────


_TRIAGE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_governance_meeting": {"type": "boolean"},
        "document_or_audio_type": {"type": "string"},
        "confidence_score": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": [
        "is_governance_meeting",
        "document_or_audio_type",
        "confidence_score",
        "reasoning",
    ],
}


def _media_resolution_high():
    """Return the SDK's HIGH ``MediaResolution`` enum, or ``None`` on older SDKs."""
    try:
        from google.genai import types  # type: ignore
    except ImportError:
        return None
    enum = getattr(types, "MediaResolution", None)
    if enum is None:
        return None
    return getattr(enum, "MEDIA_RESOLUTION_HIGH", None)


def _build_genai_client(api_key: str):
    try:
        from google import genai  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is required. Install with `pip install -U \"google-genai>=1.0\"`."
        ) from exc
    return genai.Client(api_key=api_key)


# Fallback chain used when the requested model id returns 404 NOT_FOUND.
# Ordered cheapest → heaviest. The only Gemma 4 ids AI Studio currently serves
# via the public API are the 26B MoE and 31B dense checkpoints; the E2B/E4B
# "effective N" edge models are documented on the model card but not yet
# exposed as endpoints. We still keep Gemma 3 aliases at the tail for older
# accounts whose projects haven't been migrated to Gemma 4 yet.
_GEMMA_TRIAGE_FALLBACKS = (
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
    "gemma-3n-e4b-it",
    "gemma-3n-e2b-it",
    "gemma-3-4b-it",
    "gemma-3-12b-it",
)
_GEMMA_HEAVY_FALLBACKS = (
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
    "gemma-3-27b-it",
    "gemma-3-12b-it",
)


def _model_short_id(m: Any) -> str:
    raw = getattr(m, "name", None) or getattr(m, "model", None) or ""
    return raw.split("/")[-1] if raw else ""


def _model_family(short_id: str) -> str:
    n = short_id.lower()
    if n.startswith("gemma-4"):
        return "1. gemma-4"
    if n.startswith("gemma-3n"):
        return "2. gemma-3n"
    if n.startswith("gemma-3"):
        return "3. gemma-3"
    if n.startswith("gemma"):
        return "4. gemma (other)"
    if n.startswith("embeddinggemma"):
        return "5. embeddinggemma"
    if n.startswith("shieldgemma"):
        return "6. shieldgemma"
    if n.startswith("gemini"):
        return "7. gemini"
    return "8. other"


def _list_available_model_ids(client: Any) -> List[str]:
    """Return SDK-visible model ids (best effort — empty list on any error)."""
    try:
        listed = client.models.list()
    except Exception:
        return []
    ids: List[str] = []
    for m in listed or []:
        short_id = _model_short_id(m)
        if short_id:
            ids.append(short_id)
    return ids


def print_available_models(
    client: Any,
    *,
    requested: Optional[Iterable[str]] = None,
    role: str = "this API key",
) -> List[str]:
    """
    Print every model id ``client.models.list()`` returns, grouped by family.

    When ``requested`` is set, marks ids that are / are not listed *before* any
    fallback in :func:`resolve_model_id`. Returns the flat id list (empty on error).
    """
    try:
        all_models = list(client.models.list())
    except Exception as exc:
        print(f"⚠️  models.list() failed for {role}: {exc}")
        return []

    rows: List[Tuple[str, str, List[str]]] = []
    for m in all_models:
        name = _model_short_id(m)
        if not name:
            continue
        display = getattr(m, "display_name", "") or ""
        methods = list(getattr(m, "supported_generation_methods", []) or [])
        rows.append((name, display, methods))

    ids = [r[0] for r in rows]
    available_set = set(ids)

    print(f"\n── Models visible to {role} ({len(ids)} total) ──")

    requested_list = [r.strip() for r in (requested or []) if r and str(r).strip()]
    if requested_list:
        for req in requested_list:
            if req in available_set:
                print(f"  ✓ requested {req!r} is listed")
            else:
                print(f"  ✗ requested {req!r} is NOT listed (fallback may apply)")

    rows.sort(key=lambda r: (_model_family(r[0]), r[0]))
    current: Optional[str] = None
    for name, display, methods in rows:
        fam = _model_family(name)
        if fam != current:
            print(f"\n=== {fam[3:]} ===")
            current = fam
        extras = f"  [{', '.join(methods)}]" if methods else ""
        label = f"  — {display}" if display and display.lower() != name.lower() else ""
        marker = "  ← requested" if name in requested_list else ""
        print(f"  {name}{label}{extras}{marker}")

    print()
    return ids


def resolve_model_id(
    client: Any,
    requested: str,
    *,
    fallbacks: Iterable[str] = _GEMMA_TRIAGE_FALLBACKS,
    role: str = "model",
) -> str:
    """
    Resolve ``requested`` to an id the project's API actually serves.

    Lists available models via the SDK; if ``requested`` is present, returns it
    unchanged. Otherwise walks ``fallbacks`` and returns the first id that *is*
    listed. Raises :class:`RuntimeError` with the listed Gemma ids when nothing
    matches, so the user can copy a real alias into ``GOVERNANCE_GENAI_MODEL`` /
    ``GOVERNANCE_GATEKEEPER_MODEL``.
    """
    requested = (requested or "").strip()
    available = _list_available_model_ids(client)
    if not available:
        # Listing failed (offline, quota, older SDK) — assume the caller's id is
        # correct and let the downstream generate_content call surface the error.
        logger.warning(
            "Could not list models for %s id resolution; using %s as-is.",
            role, requested,
        )
        return requested

    available_set = set(available)
    if requested in available_set:
        return requested

    gemma_ids = sorted(i for i in available if "gemma" in i.lower())
    print(
        f"\n── {role}: {requested!r} not in models.list() — Gemma ids on this key ──"
    )
    if gemma_ids:
        for gid in gemma_ids:
            print(f"  {gid}")
    else:
        print("  (no Gemma ids returned — enable Gemma access in AI Studio)")
    print(f"  Fallback order: {list(fallbacks)}\n")

    # Don't re-try the requested id in the fallback walk.
    tried = [requested]
    for candidate in fallbacks:
        if candidate == requested or candidate in tried:
            continue
        tried.append(candidate)
        if candidate in available_set:
            logger.warning(
                "%s id %r not available on this API key — falling back to %r.",
                role, requested, candidate,
            )
            return candidate

    gemma_ids = sorted(i for i in available if "gemma" in i.lower())
    raise RuntimeError(
        f"{role} id {requested!r} is not available on this API project, and none "
        f"of the fallbacks {list(fallbacks)} are listed either. "
        f"Gemma ids visible to this key: {gemma_ids or '(none — your project may need Gemma 4 access enabled)'}. "
        f"Set GOVERNANCE_GATEKEEPER_MODEL / GOVERNANCE_GENAI_MODEL to one of those ids."
    )


def call_gemma_triage(
    *,
    client: Any,
    model: str,
    system_instruction: str,
    user_text: str,
    media: Iterable[Tuple[bytes, str]],
    media_resolution_high: bool = True,
    thinking_budget: int = 0,
    max_output_tokens: int = DEFAULT_TRIAGE_MAX_OUTPUT_TOKENS,
    timeout_seconds: int = 120,
) -> Tuple[Optional[dict], str]:
    """
    Single triage call. Returns ``(parsed_json_or_None, raw_text)``.

    * ``response_mime_type='application/json'`` + ``response_schema`` force strict
      JSON output where the SDK supports them.
    * ``thinking_budget=0`` disables the model's thinking pass — triage is meant
      to be cheap, not deep. The full deconstruction prompt runs *after* triage.
    * ``media_resolution=HIGH`` is set when ``media_resolution_high=True`` so PDF
      pages get the full ~1,120 image-token budget for layout / OCR fidelity.
    """
    try:
        from gemma_hf_backend import call_gemma_hf_multimodal, use_huggingface

        if use_huggingface():
            resolution = "HIGH" if media_resolution_high else "LOW"
            hf = call_gemma_hf_multimodal(
                model=model,
                system_instruction=system_instruction + "\n\nRespond with strict JSON only.",
                user_text=user_text,
                media=media,
                temperature=0.0,
                max_output_tokens=max_output_tokens,
                media_resolution=resolution,
                include_thoughts=False,
                thinking_budget=thinking_budget if thinking_budget else None,
            )
            raw_text = hf.text or ""
            return _safe_parse_triage_json(raw_text), raw_text
    except ImportError:
        pass

    from google.genai import types  # type: ignore

    parts: List[Any] = [types.Part.from_text(text=user_text)]
    for data, mime in media:
        parts.append(types.Part.from_bytes(data=data, mime_type=mime))

    config_kwargs: dict = dict(
        system_instruction=system_instruction,
        temperature=0.0,
        max_output_tokens=max_output_tokens,
        response_mime_type="application/json",
    )

    # Strict schema is supported on newer SDKs; fall back silently otherwise.
    if hasattr(types, "Schema"):
        try:
            config_kwargs["response_schema"] = _TRIAGE_RESPONSE_SCHEMA
        except Exception:
            pass

    if media_resolution_high:
        mr = _media_resolution_high()
        if mr is not None:
            config_kwargs["media_resolution"] = mr

    # Only attach thinking_config to models that accept it. Gemma 4 returns
    # 400 INVALID_ARGUMENT: "Thinking budget is not supported for this model"
    # even when budget is 0, so we have to omit the parameter entirely.
    # Override with env GOVERNANCE_FORCE_THINKING=1 if your Gemma 4 variant
    # actually supports it (e.g. the 31B Dense reasoning model).
    _force = os.environ.get("GOVERNANCE_FORCE_THINKING", "0") == "1"
    _is_gemma = (model or "").lower().startswith("gemma")
    if _force or not _is_gemma:
        ThinkingConfig = getattr(types, "ThinkingConfig", None)
        if ThinkingConfig is not None:
            try:
                config_kwargs["thinking_config"] = ThinkingConfig(thinking_budget=int(thinking_budget))
            except TypeError:
                # Older SDKs accept only include_thoughts; safe to omit.
                pass

    request_options: dict = {}
    if timeout_seconds:
        request_options["timeout"] = timeout_seconds * 1000  # SDK expects ms

    try:
        response = client.models.generate_content(
            model=model,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(**config_kwargs),
            **({"request_options": request_options} if request_options else {}),
        )
    except TypeError:
        # `request_options` kwarg not accepted by this SDK version — retry without.
        response = client.models.generate_content(
            model=model,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(**config_kwargs),
        )

    raw_bits: List[str] = []
    for cand in getattr(response, "candidates", None) or []:
        for p in getattr(getattr(cand, "content", None), "parts", None) or []:
            t = getattr(p, "text", None)
            if t and not getattr(p, "thought", False):
                raw_bits.append(t)
    raw_text = "".join(raw_bits) or (getattr(response, "text", "") or "")

    parsed = _safe_parse_triage_json(raw_text)
    return parsed, raw_text


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _safe_parse_triage_json(raw_text: str) -> Optional[dict]:
    """Tolerate stray markdown fences / leading prose by extracting the outermost {...}."""
    if not raw_text:
        return None
    txt = raw_text.strip()
    # Strip ```json … ``` fences if present.
    if txt.startswith("```"):
        m = re.search(r"```(?:json)?\s*(.*?)\s*```", txt, re.DOTALL)
        if m:
            txt = m.group(1).strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        pass
    m = _JSON_OBJECT_RE.search(txt)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _verdict_from_json(payload: Optional[dict]) -> Tuple[bool, str, float, str]:
    """Normalize a parsed JSON dict into the four triage fields with safe defaults."""
    if not isinstance(payload, dict):
        return False, "other", 0.0, "Model did not return parseable JSON."
    is_meeting = bool(payload.get("is_governance_meeting", False))
    doc_type = str(payload.get("document_or_audio_type", "other"))[:64].strip() or "other"
    try:
        confidence = float(payload.get("confidence_score", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    reasoning = str(payload.get("reasoning", ""))[:2000].strip()
    return is_meeting, doc_type, confidence, reasoning


# ─────────────────────────────────────────────────────────────
# Triage prompts
# ─────────────────────────────────────────────────────────────


AUDIO_SYSTEM = (
    "You are an audio triage gatekeeper for a local-government open-data pipeline. "
    "You only judge whether the attached audio is a recording of an official local "
    "government public meeting. You never transcribe. You return strict JSON only."
)


def audio_user_prompt(window_seconds: int) -> str:
    return (
        f"Listen to up to the first {window_seconds} seconds of the attached audio. "
        "Decide whether it is an official local government public meeting (city council, "
        "county commission, school board, planning board, fire district, special district, etc.).\n\n"
        "Listen specifically for these structural audio cues:\n"
        "  • a gavel strike or chair calling the meeting to order;\n"
        "  • a roll call of members or quorum confirmation;\n"
        "  • Pledge of Allegiance or formal invocation;\n"
        "  • motion / second / vote cadence (\"all in favor say aye\");\n"
        "  • a public-comment section with 2-3 minute speaker turns.\n\n"
        "If you hear NONE of those structural cues (e.g. the audio is music, a podcast, a "
        "news clip, a campaign speech, a private interview, an automated announcement, or "
        "is silent / corrupted), the file is NOT a governance meeting.\n\n"
        f"Return ONLY a JSON object with these keys:\n"
        f"  is_governance_meeting (bool), document_or_audio_type (string — one of "
        f"meeting_audio, meeting_video, reference_packet, invoice, brochure, correspondence, "
        f"other), confidence_score (0.0-1.0 float), reasoning (short Smart-Brevity sentence "
        f"citing the specific cue you heard or its absence)."
    )


PDF_SYSTEM = (
    "You are a visual-layout triage gatekeeper for a local-government open-data pipeline. "
    "You judge whether the attached page images depict an official meeting Agenda or "
    "official meeting Minutes for a local government body. You return strict JSON only."
)

PDF_USER = (
    "Look at the attached page image(s). Use layout analysis and visual OCR to classify "
    "the document as one of:\n"
    "  • meeting_agenda — itemized agenda with body name, date, location, list of agenda "
    "    items, often a Pledge / Roll Call / Adjournment frame;\n"
    "  • meeting_minutes — narrative or itemized minutes that record votes, motions, members "
    "    present/absent, and decisions;\n"
    "  • other — invoices, brochures, reference packets, slide decks, correspondence, "
    "    architectural drawings, financial statements without meeting context, etc.\n\n"
    "Only 'meeting_agenda' and 'meeting_minutes' count as a governance meeting document. "
    "A loose financial table, bid packet, or staff memo embedded inside a larger meeting "
    "packet does NOT by itself qualify — the first 1-2 pages must clearly show meeting "
    "framing (body name + date + agenda structure or minutes header).\n\n"
    "Return ONLY a JSON object with these keys: is_governance_meeting (bool — true iff "
    "type is meeting_agenda or meeting_minutes), document_or_audio_type (string — one of "
    "meeting_agenda, meeting_minutes, reference_packet, invoice, brochure, correspondence, "
    "other), confidence_score (0.0-1.0), reasoning (short Smart-Brevity sentence citing "
    "the visual evidence — body name, date, layout pattern)."
)


# ─────────────────────────────────────────────────────────────
# Per-file triage
# ─────────────────────────────────────────────────────────────


def triage_pdf(
    *,
    client: Any,
    model: str,
    pdf_path: Path,
    raw_root: Path,
    pages: int = DEFAULT_PDF_PAGES,
    dpi: int = DEFAULT_PDF_DPI,
) -> TriageVerdict:
    """Run the visual gatekeeper on the first ``pages`` pages of ``pdf_path``."""
    rel_str, geo = relative_geography(pdf_path, raw_root)
    verdict = TriageVerdict(
        is_governance_meeting=False,
        document_or_audio_type="other",
        confidence_score=0.0,
        reasoning="",
        triage_kind="pdf",
        file_path=str(pdf_path),
        relative_path=rel_str,
        geography_label=geo,
    )
    t0 = time.time()
    try:
        page_bytes = pdf_first_pages_to_png_bytes(pdf_path, pages=pages, dpi=dpi)
    except Exception as e:
        verdict.error = f"pdf2image failed: {e}"
        verdict.elapsed_seconds = round(time.time() - t0, 2)
        return verdict

    if not page_bytes:
        verdict.error = "pdf2image returned no pages"
        verdict.elapsed_seconds = round(time.time() - t0, 2)
        return verdict

    media = [(b, "image/png") for b in page_bytes]
    try:
        parsed, raw = call_gemma_triage(
            client=client,
            model=model,
            system_instruction=PDF_SYSTEM,
            user_text=PDF_USER,
            media=media,
            media_resolution_high=True,
            thinking_budget=0,
        )
    except Exception as e:
        verdict.error = f"Gemma triage call failed: {e}"
        verdict.elapsed_seconds = round(time.time() - t0, 2)
        return verdict

    is_m, doc_type, conf, reason = _verdict_from_json(parsed)
    verdict.is_governance_meeting = is_m
    verdict.document_or_audio_type = doc_type
    verdict.confidence_score = conf
    verdict.reasoning = reason
    verdict.raw_model_text = raw[:4000] if raw else None
    verdict.elapsed_seconds = round(time.time() - t0, 2)
    return verdict


def triage_audio(
    *,
    client: Any,
    model: str,
    audio_path: Path,
    raw_root: Path,
    window_seconds: int = DEFAULT_AUDIO_WINDOW_SECONDS,
    scratch_dir: Optional[Path] = None,
) -> TriageVerdict:
    """Run the multimodal audio gatekeeper on the first ``window_seconds`` of audio."""
    rel_str, geo = relative_geography(audio_path, raw_root)
    verdict = TriageVerdict(
        is_governance_meeting=False,
        document_or_audio_type="other",
        confidence_score=0.0,
        reasoning="",
        triage_kind="audio",
        file_path=str(audio_path),
        relative_path=rel_str,
        geography_label=geo,
    )
    t0 = time.time()

    # Clip the audio window to a temp file so we send minimal bytes.
    use_temp = scratch_dir is None
    if use_temp:
        tmpdir = Path(tempfile.mkdtemp(prefix="gatekeeper_audio_"))
    else:
        tmpdir = scratch_dir
        tmpdir.mkdir(parents=True, exist_ok=True)
    clip_path = tmpdir / f"{audio_path.stem}_triage_clip.mp3"

    try:
        try:
            clip_audio_window(audio_path, seconds=window_seconds, out_path=clip_path)
        except Exception as e:
            verdict.error = f"ffmpeg clip failed: {e}"
            verdict.elapsed_seconds = round(time.time() - t0, 2)
            return verdict

        try:
            audio_bytes = clip_path.read_bytes()
        except Exception as e:
            verdict.error = f"could not read clipped audio: {e}"
            verdict.elapsed_seconds = round(time.time() - t0, 2)
            return verdict

        media = [(audio_bytes, "audio/mpeg")]
        try:
            parsed, raw = call_gemma_triage(
                client=client,
                model=model,
                system_instruction=AUDIO_SYSTEM,
                user_text=audio_user_prompt(window_seconds),
                media=media,
                media_resolution_high=False,  # audio is unaffected by image media_resolution
                thinking_budget=0,
            )
        except Exception as e:
            verdict.error = f"Gemma triage call failed: {e}"
            verdict.elapsed_seconds = round(time.time() - t0, 2)
            return verdict

        is_m, doc_type, conf, reason = _verdict_from_json(parsed)
        verdict.is_governance_meeting = is_m
        verdict.document_or_audio_type = doc_type
        verdict.confidence_score = conf
        verdict.reasoning = reason
        verdict.raw_model_text = raw[:4000] if raw else None
    finally:
        if use_temp:
            shutil.rmtree(tmpdir, ignore_errors=True)

    verdict.elapsed_seconds = round(time.time() - t0, 2)
    return verdict


# ─────────────────────────────────────────────────────────────
# Routing — verified stays put, excluded mirrors geography under excluded_inputs/
# ─────────────────────────────────────────────────────────────


def move_to_excluded(
    *,
    file_path: Path,
    raw_root: Path,
    excluded_root: Path,
    dry_run: bool = False,
) -> Path:
    """
    Calculate the file's path relative to ``raw_root`` and replicate that geography
    subtree under ``excluded_root``, then ``shutil.move()`` the file. Returns the
    destination path (real or planned, when ``dry_run=True``).

    Filename collisions append ``_dup1``, ``_dup2``, … to keep both copies.
    """
    rel = file_path.resolve().relative_to(raw_root.resolve())
    dest = excluded_root / rel
    if not dry_run:
        os.makedirs(dest.parent, exist_ok=True)
        if dest.exists():
            stem, suffix = dest.stem, dest.suffix
            n = 1
            while True:
                candidate = dest.with_name(f"{stem}_dup{n}{suffix}")
                if not candidate.exists():
                    dest = candidate
                    break
                n += 1
        shutil.move(str(file_path), str(dest))
    return dest


# ─────────────────────────────────────────────────────────────
# Walker — os.walk over the raw root, skipping excluded_inputs and scraper internals
# ─────────────────────────────────────────────────────────────


def count_triageable_files(
    raw_root: Path, *, kinds: Iterable[str] = ("pdf", "audio")
) -> int:
    """Count PDF/audio files Gatekeeper would walk (for scope banners before a long run)."""
    return sum(1 for _ in iter_triageable_files(raw_root, kinds=kinds))


def iter_triageable_files(
    raw_root: Path, *, kinds: Iterable[str] = ("pdf", "audio")
) -> Iterable[Path]:
    """
    Yield candidate files via :func:`os.walk`. Skips any directory under the
    exclusion root, scraper-internal underscored folders, and ``__pycache__``.
    """
    kinds_set = {k.lower() for k in kinds}
    raw_root_resolved = raw_root.resolve()
    excluded_root_resolved = (raw_root / EXCLUDED_DIRNAME).resolve()

    for dirpath, dirnames, filenames in os.walk(raw_root_resolved):
        # Skip anything under excluded_inputs/ for idempotency.
        try:
            Path(dirpath).resolve().relative_to(excluded_root_resolved)
            dirnames[:] = []
            continue
        except ValueError:
            pass

        # Prune internal folders in-place so os.walk does not descend into them.
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIR_NAMES
            and not (SKIP_DIR_PREFIXES and d.startswith(SKIP_DIR_PREFIXES))
        ]
        # Stable order so demo runs read predictably.
        dirnames.sort()

        for fn in sorted(filenames):
            path = Path(dirpath) / fn
            ext = path.suffix.lower()
            if ext in PDF_EXTS and "pdf" in kinds_set:
                yield path
            elif ext in AUDIO_EXTS and "audio" in kinds_set:
                yield path


# ─────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────


def run_triage(
    *,
    raw_root: Path,
    api_key: str,
    model: str = DEFAULT_MODEL,
    kinds: Iterable[str] = ("pdf", "audio"),
    pdf_pages: int = DEFAULT_PDF_PAGES,
    pdf_dpi: int = DEFAULT_PDF_DPI,
    audio_window_seconds: int = DEFAULT_AUDIO_WINDOW_SECONDS,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    dry_run: bool = False,
    max_files: Optional[int] = None,
    preload_models: bool = True,
    progress_stdout: bool = False,
) -> TriageReport:
    """Walk ``raw_root``, triage every PDF / audio, move failures under ``excluded_inputs/``."""
    if not raw_root.is_dir():
        raise FileNotFoundError(f"Raw inputs root not found: {raw_root}")

    excluded_root = raw_root / EXCLUDED_DIRNAME
    if not dry_run:
        excluded_root.mkdir(parents=True, exist_ok=True)

    logger.info("Gatekeeper start | raw_root=%s | excluded_root=%s | model=%s",
                raw_root, excluded_root, model)
    if dry_run:
        logger.info("(dry-run: no files will be moved)")

    kinds_tuple = tuple(k.strip().lower() for k in kinds if str(k).strip())

    try:
        from gemma_hf_backend import (
            ensure_hf_ready_for_triage,
            hf_weights_cached,
            print_hf_model_catalog,
            resolve_hf_model_id,
            use_huggingface,
        )
    except ImportError:
        use_huggingface = lambda: False  # type: ignore[assignment]

    if use_huggingface():
        print_hf_model_catalog(requested=(model,), role="Gatekeeper (Hugging Face)")
        model = resolve_hf_model_id(model)
        if preload_models:
            ensure_hf_ready_for_triage(model, kinds=kinds_tuple, skip_if_cached=True)
        else:
            img_ok, aud_ok = hf_weights_cached(model)
            if not img_ok or ("audio" in kinds_tuple and not aud_ok):
                raise RuntimeError(
                    "HF weights not loaded. Run notebook §3 once per session before §4 Gatekeeper, "
                    "or call run_triage(..., preload_models=True)."
                )
            logger.info("Gatekeeper using in-memory HF weights (skipped reload)")
        client = None
    else:
        client = _build_genai_client(api_key)
        # Show the live model list before any fallback so notebook / CLI runs are auditable.
        print_available_models(client, requested=(model,), role="Gatekeeper triage")
        # Resolve the requested model against the SDK's actual model list. This
        # converts a 404 NOT_FOUND (e.g. "gemma-4-e4b-it" on a project that only
        # serves gemma-3n / gemma-3) into either a working fallback or a clear
        # error listing the Gemma ids the project actually has.
        model = resolve_model_id(client, model, role="Gatekeeper triage model")
    logger.info("Gatekeeper resolved model | model=%s", model)

    report = TriageReport(raw_root=str(raw_root), excluded_root=str(excluded_root))

    processed = 0
    for path in iter_triageable_files(raw_root, kinds=kinds):
        if max_files is not None and processed >= max_files:
            logger.info("Reached --max-files=%d, stopping.", max_files)
            if progress_stdout:
                print(f"Gatekeeper: reached max_files={max_files}, stopping.", flush=True)
            break
        processed += 1
        ext = path.suffix.lower()
        rel_str, geo = relative_geography(path, raw_root)
        if progress_stdout:
            cap = f"/{max_files}" if max_files is not None else ""
            print(f"[Gatekeeper {processed}{cap}] {rel_str}", flush=True)

        try:
            if ext in PDF_EXTS:
                verdict = triage_pdf(
                    client=client, model=model,
                    pdf_path=path, raw_root=raw_root,
                    pages=pdf_pages, dpi=pdf_dpi,
                )
            else:
                verdict = triage_audio(
                    client=client, model=model,
                    audio_path=path, raw_root=raw_root,
                    window_seconds=audio_window_seconds,
                )
        except Exception as e:
            # Defensive: any unhandled error in the triage helpers becomes a recorded error
            # rather than aborting the batch sweep.
            verdict = TriageVerdict(
                is_governance_meeting=False,
                document_or_audio_type="other",
                confidence_score=0.0,
                reasoning="",
                triage_kind="pdf" if ext in PDF_EXTS else "audio",
                file_path=str(path),
                relative_path=rel_str,
                geography_label=geo,
                error=f"unhandled triage error: {e}",
            )

        if verdict.error:
            logger.error(
                "ERROR | %s | %s | %s",
                geo or "(root)", path.name, verdict.error,
            )
            report.add(verdict)
            continue

        # PROCEED rule: model says it's a meeting AND confidence ≥ threshold.
        verdict.proceed = (
            verdict.is_governance_meeting
            and verdict.confidence_score >= confidence_threshold
        )

        if verdict.proceed:
            logger.info(
                "KEEP    | %s | %s | type=%s conf=%.2f | %s",
                geo or "(root)", path.name,
                verdict.document_or_audio_type, verdict.confidence_score,
                verdict.reasoning[:160],
            )
            report.add(verdict)
            continue

        # EXCLUDE: mirror geography under excluded_inputs/ and move.
        try:
            dest = move_to_excluded(
                file_path=path,
                raw_root=raw_root,
                excluded_root=excluded_root,
                dry_run=dry_run,
            )
            logger.info(
                "EXCLUDE | %s | %s | type=%s conf=%.2f | moved %s→ %s | %s",
                geo or "(root)", path.name,
                verdict.document_or_audio_type, verdict.confidence_score,
                "(dry-run) " if dry_run else "",
                dest.relative_to(raw_root).as_posix(),
                verdict.reasoning[:160],
            )
        except Exception as e:
            verdict.error = f"move_to_excluded failed: {e}"
            logger.error("MOVE-FAIL | %s | %s | %s", geo or "(root)", path.name, verdict.error)

        report.add(verdict)

    logger.info(
        "Gatekeeper done | processed=%d | proceed=%d | excluded=%d | errors=%d",
        processed, len(report.proceed), len(report.excluded), len(report.errors),
    )
    return report


# ─────────────────────────────────────────────────────────────
# CLI entrypoint
# ─────────────────────────────────────────────────────────────


def _default_raw_root() -> Path:
    """Best-effort default: project pipeline path on Colab, else repo data root."""
    colab_default = Path(
        "/content/drive/MyDrive/CommunityOne/governance_pipeline_data/01_raw_inputs"
    )
    if colab_default.is_dir():
        return colab_default
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "governance_pipeline_data" / "01_raw_inputs"


def _resolve_api_key(cli_value: Optional[str]) -> str:
    try:
        from gemma_hf_backend import ensure_hf_token, use_huggingface

        if use_huggingface():
            return ensure_hf_token(cli_value)
    except ImportError:
        pass
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    if cli_value:
        return cli_value
    for env in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(env)
        if val:
            return val
    # Colab Secrets fallback — only when running inside Colab.
    try:
        from google.colab import userdata  # type: ignore
        for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            val = userdata.get(name)
            if val:
                return val
    except ImportError:
        pass
    raise SystemExit(
        "No API key found. Pass --api-key, set GEMINI_API_KEY in the environment, "
        "or add a Colab Secret named GEMINI_API_KEY (https://aistudio.google.com/apikey)."
    )


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        level=logging.DEBUG if verbose else logging.INFO,
        stream=sys.stdout,
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gatekeeper Triage — route raw-input PDFs and audio for the Ledger of Influence pipeline."
    )
    parser.add_argument(
        "--raw-root", type=Path, default=None,
        help="Root of 01_raw_inputs/ (default: Colab Drive path, else repo data path).",
    )
    parser.add_argument(
        "--api-key", default=None,
        help="API key: HF_TOKEN (Hugging Face backend) or GEMINI_API_KEY (Google backend).",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Gemma 4 model id (default: {DEFAULT_MODEL}, env: GOVERNANCE_GENAI_MODEL).",
    )
    parser.add_argument(
        "--kinds", default="pdf,audio",
        help="Comma-separated kinds to triage: 'pdf', 'audio', or both (default: pdf,audio).",
    )
    parser.add_argument(
        "--pdf-pages", type=int, default=DEFAULT_PDF_PAGES,
        help=f"First N pages of each PDF to send (default: {DEFAULT_PDF_PAGES}).",
    )
    parser.add_argument(
        "--pdf-dpi", type=int, default=DEFAULT_PDF_DPI,
        help=f"DPI for pdf2image rendering (default: {DEFAULT_PDF_DPI}).",
    )
    parser.add_argument(
        "--audio-window-seconds", type=int, default=DEFAULT_AUDIO_WINDOW_SECONDS,
        help=f"Seconds of audio to send to triage (default: {DEFAULT_AUDIO_WINDOW_SECONDS}).",
    )
    parser.add_argument(
        "--confidence-threshold", type=float, default=DEFAULT_CONFIDENCE_THRESHOLD,
        help=f"Minimum confidence to keep a file (default: {DEFAULT_CONFIDENCE_THRESHOLD}).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run the triage but do not move any files.",
    )
    parser.add_argument(
        "--max-files", type=int, default=None,
        help="Stop after triaging this many files (useful for live demos).",
    )
    parser.add_argument(
        "--report-path", type=Path, default=None,
        help="Write the full triage report JSON to this path.",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="DEBUG-level logging.",
    )

    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    raw_root = (args.raw_root or _default_raw_root()).expanduser().resolve()
    api_key = _resolve_api_key(args.api_key)

    kinds = tuple(k.strip().lower() for k in args.kinds.split(",") if k.strip())
    invalid = [k for k in kinds if k not in {"pdf", "audio"}]
    if invalid:
        parser.error(f"--kinds may only contain 'pdf' or 'audio', got: {invalid}")

    try:
        report = run_triage(
            raw_root=raw_root,
            api_key=api_key,
            model=args.model,
            kinds=kinds,
            pdf_pages=args.pdf_pages,
            pdf_dpi=args.pdf_dpi,
            audio_window_seconds=args.audio_window_seconds,
            confidence_threshold=args.confidence_threshold,
            dry_run=args.dry_run,
            max_files=args.max_files,
        )
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 2
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        return 130

    if args.report_path:
        try:
            args.report_path.parent.mkdir(parents=True, exist_ok=True)
            args.report_path.write_text(
                json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Wrote triage report → %s", args.report_path)
        except Exception as e:
            logger.error("Failed to write report (%s): %s", args.report_path, e)

    return 0 if not report.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
