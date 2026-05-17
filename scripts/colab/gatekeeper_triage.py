#!/usr/bin/env python3
"""
Gatekeeper Triage — "The Ledger of Influence" data-gating layer (2026 Gemma 4 Good Hackathon).

Walks ``<raw_root>/`` (default: ``My Drive/CommunityOne/governance_pipeline_data/01_raw_inputs/``)
recursively with :func:`os.walk`, sends each PDF / audio file to a Gemma multimodal
triage call, and routes the file based on the model's verdict:

* **PROCEED** (``is_governance_meeting=True`` and confidence ≥ threshold) — leave the
  file in place so downstream pipelines (notebook ``02_run_meeting_llm.ipynb`` / Gatekeeper
  step 2) pick it up.
* **EXCLUDE** — by default files **stay in place** (logged in the triage report only).
  Set ``GOVERNANCE_GATEKEEPER_MOVE_EXCLUDED=1`` to mirror rejects under
  ``<raw_root>/excluded_inputs/…`` via ``shutil.move()`` (legacy).

The triage layer is intentionally cheap:

* **Audio Gatekeeper** — clips the first ``--audio-window-seconds`` of audio via
  ``ffmpeg`` and sends the bytes directly to Gemma. The prompt forces the model to
  listen for *structural audio cues* (gavel, roll call, public comment cadence) and
  return strict JSON only.
* **PDF Gatekeeper** — extracts the first 1–2 pages as a small PDF (PyMuPDF) plus any
  digital text layer, sends both to Gemma on AI Studio (no PNG / pdf2image render).

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
from contextlib import contextmanager
import json
import logging
import os
import re
import shutil
import signal
import threading
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

PDF_EXTS = {".pdf"}
try:
    from governance_meeting_llm import (
        AUDIO_EXTS,
        VIDEO_EXTS,
        _ffmpeg_audio_only_output_flags,
        prepare_meeting_audio_for_processing,
    )
except ImportError:
    AUDIO_EXTS = {
        ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
        ".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v",
    }
    VIDEO_EXTS = frozenset({".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"})

    def prepare_meeting_audio_for_processing(source_path, *, work_dir, bitrate="96k", min_opus_bytes=1024):
        return source_path

    def _ffmpeg_audio_only_output_flags(path: Path) -> List[str]:
        if path.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}:
            return ["-vn", "-sn", "-map", "0:a:0?"]
        return []

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
        from gemma_hf_backend import (
            _HF_GATEKEEPER_REPO_DEFAULT,
            gatekeeper_use_huggingface,
        )

        if gatekeeper_use_huggingface():
            return (
                os.environ.get("GOVERNANCE_GATEKEEPER_MODEL", "").strip()
                or os.environ.get("GOVERNANCE_HF_GATEKEEPER_MODEL", "").strip()
                or _HF_GATEKEEPER_REPO_DEFAULT
            )
    except ImportError:
        pass
    return (
        os.environ.get("GOVERNANCE_GATEKEEPER_MODEL", "").strip()
        or "gemma-4-e2b-it"
    )


# Default model — override with --model or env GOVERNANCE_GATEKEEPER_MODEL.
DEFAULT_MODEL = _default_gatekeeper_model()

# Triage cost / latency caps.
DEFAULT_AUDIO_WINDOW_SECONDS = 120          # send only the first N seconds for triage
MAX_GATEKEEPER_PDF_PAGES = 2                # triage never reads more than 2 pages
DEFAULT_PDF_PAGES = 2                       # first N pages sent as PDF bytes to the model
DEFAULT_PDF_DPI = 120                       # legacy CLI flag (PNG path removed; unused)
DEFAULT_LARGE_PDF_BYTES = 1_500_000          # above this: triage first page only
DEFAULT_TEXT_TRIAGE_MIN_CHARS = 80           # legacy; text excerpt always included when present
DEFAULT_PDF_SUBSET_MAX_BYTES = 4_000_000     # cap inlined PDF payload for the API
DEFAULT_TEXT_TRIAGE_MAX_CHARS = 12_000       # cap excerpt sent to the model

DEFAULT_TRIAGE_MAX_OUTPUT_TOKENS = 512      # strict JSON only — keep cheap
DEFAULT_SOCKET_ALARM_BUFFER_SECONDS = 30    # wall clock = API timeout + this buffer


class NetworkDeadlockError(Exception):
    """LLM HTTP client hung past SIGALRM wall clock (socket freeze)."""


def _gatekeeper_on_main_thread() -> bool:
    return threading.current_thread() is threading.main_thread()


def gatekeeper_socket_alarm_enabled() -> bool:
    """When true (default on Linux/Colab), SIGALRM aborts stuck SDK sockets (main thread only)."""
    raw = os.environ.get("GOVERNANCE_GATEKEEPER_SOCKET_ALARM", "").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if not _gatekeeper_on_main_thread() or not hasattr(signal, "SIGALRM"):
        return False
    return True


def gatekeeper_socket_alarm_seconds(api_timeout_seconds: int) -> int:
    """Hard wall-clock limit: expected SDK timeout + network buffer."""
    buffer = int(
        os.environ.get(
            "GOVERNANCE_GATEKEEPER_SOCKET_ALARM_BUFFER_SECONDS",
            str(DEFAULT_SOCKET_ALARM_BUFFER_SECONDS),
        )
    )
    return max(1, int(api_timeout_seconds) + max(0, buffer))


@contextmanager
def gatekeeper_socket_freeze_guard(api_timeout_seconds: int):
    """
    Abort if ``generate_content`` blocks the process past api_timeout + buffer.

    ThreadPoolExecutor timeouts do not always unblock a frozen HTTP socket; SIGALRM
    on the main thread does (Colab / Linux only). Off the main thread (e.g.
    ``GOVERNANCE_PARALLEL_STATES`` workers) this is a no-op — use the SDK /
    ``call_gemma_triage`` thread-pool timeout instead.
    """
    if (
        not gatekeeper_socket_alarm_enabled()
        or api_timeout_seconds <= 0
        or not hasattr(signal, "SIGALRM")
        or not _gatekeeper_on_main_thread()
    ):
        yield
        return

    alarm_sec = gatekeeper_socket_alarm_seconds(api_timeout_seconds)

    def _on_alarm(signum: int, frame: Any) -> None:
        raise NetworkDeadlockError(
            f"OS-level catch: LLM API call frozen past {alarm_sec}s wall clock "
            f"(sdk timeout={api_timeout_seconds}s)."
        )

    prev_handler = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(alarm_sec)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)


def gatekeeper_text_first_enabled() -> bool:
    """When true (default), include digital text from pages 1–N alongside the PDF subset."""
    return os.environ.get("GOVERNANCE_GATEKEEPER_TEXT_FIRST", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def gatekeeper_pdf_direct_enabled() -> bool:
    """When true (default on AI Studio), send first pages as ``application/pdf`` (no PNG render)."""
    raw = os.environ.get("GOVERNANCE_GATEKEEPER_PDF_DIRECT", "").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if raw in ("1", "true", "yes"):
        return True
    return True


def gatekeeper_move_excluded_enabled() -> bool:
    """When true, move rejects under ``raw_root/excluded_inputs/`` (off by default)."""
    return os.environ.get("GOVERNANCE_GATEKEEPER_MOVE_EXCLUDED", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def clamp_gatekeeper_pdf_pages(pages: int) -> int:
    """Gatekeeper triage: page 1 only, or pages 1–2 at most."""
    return max(1, min(int(pages), MAX_GATEKEEPER_PDF_PAGES))


def resolve_gatekeeper_page_count(pdf_path: Path, pages: int) -> int:
    """Large Drive PDFs default to page 1 only so the API payload stays small."""
    pages = clamp_gatekeeper_pdf_pages(pages)
    threshold = int(
        os.environ.get("GOVERNANCE_GATEKEEPER_LARGE_PDF_BYTES", str(DEFAULT_LARGE_PDF_BYTES))
    )
    try:
        size = pdf_path.stat().st_size
    except OSError:
        return pages
    if size < threshold:
        return pages
    large_pages = clamp_gatekeeper_pdf_pages(
        int(os.environ.get("GOVERNANCE_GATEKEEPER_LARGE_PDF_PAGES", "1"))
    )
    logger.info(
        "  large PDF %.1f MB → triage pages 1-%d only (not full document)",
        size / (1024 * 1024),
        large_pages,
    )
    return min(pages, large_pages)


def resolve_gatekeeper_render_opts(
    pdf_path: Path, pages: int, dpi: int
) -> tuple[int, int]:
    """Legacy tuple API — DPI is ignored (no pixmap render)."""
    return resolve_gatekeeper_page_count(pdf_path, pages), max(72, int(dpi))
DEFAULT_CONFIDENCE_THRESHOLD = 0.6

# Model JSON sometimes sets document_or_audio_type correctly but is_governance_meeting=false.
_MEETING_DOC_TYPES = frozenset(
    {"meeting_agenda", "meeting_minutes", "meeting_audio", "meeting_video"}
)

# Triage JSON schema (also enforced via response_schema where the SDK supports it).
TRIAGE_JSON_FIELDS = {
    "is_governance_meeting": "boolean — true iff this is the audio/document of an official local government public meeting",
    "document_or_audio_type": "string — one of: meeting_agenda, meeting_minutes, meeting_audio, meeting_video, reference_packet, invoice, brochure, correspondence, other",
    "confidence_score": "number between 0.0 and 1.0 — your confidence in is_governance_meeting",
    "reasoning": "string — short Smart-Brevity rationale: headline, colon, evidence cited from the file",
    "meeting_date": "string YYYY-MM-DD calendar date of the meeting, or null if unknown",
    "meeting_title": "string short label (e.g. City Council Regular Session, Planning Commission)",
    "meeting_instance_slug": "string snake_case slug unique per body/session on that date (e.g. city-council, planning-commission) — required when is_governance_meeting is true",
}

logger = logging.getLogger("gatekeeper")

# Opened by :func:`configure_logging` when ``log_path`` is set; closed by :func:`close_gatekeeper_logging`.
_log_file_handle: Optional[Any] = None


def gatekeeper_progress_stdout_enabled() -> bool:
    """Notebook-friendly step prints during slow Drive walks (default on)."""
    return os.environ.get("GOVERNANCE_GATEKEEPER_PROGRESS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _gatekeeper_progress(msg: str, *, also_log: bool = True) -> None:
    """Print to the Colab cell (and ``gatekeeper`` logger when configured)."""
    if gatekeeper_progress_stdout_enabled():
        print(msg, flush=True)
    if also_log and logger.handlers:
        logger.info(msg)


def _gatekeeper_progress_interval() -> int:
    try:
        return max(5, int(os.environ.get("GOVERNANCE_GATEKEEPER_PROGRESS_EVERY", "25")))
    except ValueError:
        return 25


def log_llm_catalog_enabled() -> bool:
    """When false (default), skip verbose ``models.list()`` / HF repo catalog output."""
    return os.environ.get("GOVERNANCE_LOG_LLM_CATALOG", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


class _FlushingStreamHandler(logging.StreamHandler):
    """``StreamHandler`` that flushes the underlying stream after every log record."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        try:
            self.flush()
            stream = self.stream
            if stream is not None and hasattr(stream, "flush"):
                stream.flush()
        except Exception:
            self.handleError(record)


def flush_gatekeeper_logs(*, fsync: bool = False) -> None:
    """Push buffered log lines to disk (and optionally ``fsync`` the log file)."""
    for handler in logger.handlers:
        try:
            handler.flush()
        except Exception:
            pass
        stream = getattr(handler, "stream", None)
        if stream is not None and hasattr(stream, "flush"):
            try:
                stream.flush()
            except Exception:
                pass
    if fsync and _log_file_handle is not None and hasattr(_log_file_handle, "fileno"):
        try:
            os.fsync(_log_file_handle.fileno())
        except OSError:
            pass


def configure_logging(
    *,
    verbose: bool = True,
    log_path: Optional[Path | str] = None,
    mirror_log_path: Optional[Path | str] = None,
    console: bool = True,
) -> Path | None:
    """
    Configure the ``gatekeeper`` logger for notebook / CLI runs.

    When ``log_path`` is set, each log line is written with line buffering and flushed
    immediately so ``tail -f`` on Drive/WSL sees progress without waiting for the sweep
    to finish. ``mirror_log_path`` optionally duplicates lines to a second file (e.g. a
    local copy while the primary log is on Drive under ``00_logs/``).
    """
    global _log_file_handle
    close_gatekeeper_logging()

    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    resolved_log: Path | None = None
    if log_path:
        resolved_log = Path(log_path).expanduser()
        resolved_log.parent.mkdir(parents=True, exist_ok=True)
        _log_file_handle = open(
            resolved_log,
            mode="w",
            encoding="utf-8",
            buffering=1,
        )
        file_handler = _FlushingStreamHandler(_log_file_handle)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if mirror_log_path:
        mirror = Path(mirror_log_path).expanduser()
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror_handle = open(mirror, mode="w", encoding="utf-8", buffering=1)
        mh = _FlushingStreamHandler(mirror_handle)
        mh.setLevel(level)
        mh.setFormatter(formatter)
        logger.addHandler(mh)

    if console:
        console_handler = _FlushingStreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return resolved_log


def close_gatekeeper_logging() -> None:
    """Close the on-disk log file opened by :func:`configure_logging`."""
    global _log_file_handle
    flush_gatekeeper_logs(fsync=True)
    for handler in list(logger.handlers):
        try:
            handler.close()
        except Exception:
            pass
        logger.removeHandler(handler)
    if _log_file_handle is not None:
        try:
            _log_file_handle.close()
        except Exception:
            pass
        _log_file_handle = None


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
    meeting_date: Optional[str] = None
    meeting_title: Optional[str] = None
    meeting_instance_slug: Optional[str] = None


@dataclass
class TriageReport:
    raw_root: str
    excluded_root: str
    proceed: List[TriageVerdict] = field(default_factory=list)
    excluded: List[TriageVerdict] = field(default_factory=list)
    errors: List[TriageVerdict] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    selection_note: str = ""

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
            "selection_note": self.selection_note,
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
    MP3. Video containers are transcoded to Opus first (see
    :func:`~governance_meeting_llm.prepare_meeting_audio_for_processing`). This is the
    *programmatic token constraint* on the audio gatekeeper — we cap how deeply
    Gemma processes the stream by clipping the input window.
    """
    _ensure_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    src = prepare_meeting_audio_for_processing(
        audio_path, work_dir=out_path.parent / "_opus"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        *_ffmpeg_audio_only_output_flags(audio_path),
        "-t", str(max(5, int(seconds))),
        "-ac", "1", "-ar", "16000",
        "-c:a", "libmp3lame", "-q:a", "5",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, timeout=300)
    return out_path


# ─────────────────────────────────────────────────────────────
# PDF → first-N-pages PNG bytes (PyMuPDF preferred)
# ─────────────────────────────────────────────────────────────


@contextmanager
def _local_pdf_copy(pdf_path: Path):
    """
    Copy PDF to Colab ``/tmp`` when source is on Drive FUSE (random reads are very slow).
    """
    pdf_path = pdf_path.resolve()
    use_tmp = os.environ.get("GOVERNANCE_GATEKEEPER_COPY_TO_TMP", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )
    on_drive = "/content/drive" in pdf_path.as_posix()
    if not use_tmp or not on_drive or not pdf_path.is_file():
        yield pdf_path
        return
    size_mb = pdf_path.stat().st_size / (1024 * 1024)
    logger.info("  copying %.1f MB to /tmp for fast PDF read …", size_mb)
    flush_gatekeeper_logs()
    fd, tmp_name = tempfile.mkstemp(suffix=pdf_path.suffix or ".pdf")
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        shutil.copy2(pdf_path, tmp_path)
        logger.info("  copy done → %s", tmp_path)
        flush_gatekeeper_logs()
        yield tmp_path
    finally:
        tmp_path.unlink(missing_ok=True)


def extract_first_pages_pdf_bytes(
    pdf_path: Path, *, pages: int = DEFAULT_PDF_PAGES
) -> bytes:
    """
    Build a small PDF containing only the first ``pages`` (for API ``application/pdf``).

    Uses PyMuPDF; copies to ``/tmp`` first on Colab Drive paths.
    """
    n_pages = resolve_gatekeeper_page_count(pdf_path, pages)
    max_bytes = int(
        os.environ.get(
            "GOVERNANCE_GATEKEEPER_PDF_SUBSET_MAX_BYTES",
            str(DEFAULT_PDF_SUBSET_MAX_BYTES),
        )
    )

    with _local_pdf_copy(pdf_path) as local_pdf:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError(
                "PDF triage needs PyMuPDF — `pip install pymupdf`."
            ) from exc

        with fitz.open(local_pdf) as doc:
            total = doc.page_count
            if total <= 0:
                raise RuntimeError("PDF has no pages")
            end = min(n_pages, total) - 1
            if end >= total - 1 and local_pdf.stat().st_size <= max_bytes:
                return local_pdf.read_bytes()
            subset = fitz.open()
            try:
                subset.insert_pdf(doc, from_page=0, to_page=end)
                data = subset.tobytes(garbage=4, deflate=True)
            finally:
                subset.close()
            if len(data) > max_bytes:
                raise RuntimeError(
                    f"First {n_pages} page(s) PDF subset is {len(data)} bytes "
                    f"(max {max_bytes}); try GOVERNANCE_GATEKEEPER_PDF_PAGES=1."
                )
            return data


def extract_first_pages_text(
    pdf_path: Path, *, pages: int = DEFAULT_PDF_PAGES, max_chars: int = DEFAULT_TEXT_TRIAGE_MAX_CHARS
) -> str:
    """
    Read **only** the first 1–2 pages' digital text layer (no pixmap render).

    Fast on large text PDFs; returns ``""`` when PyMuPDF is missing or pages are scanned.
    """
    n_pages = clamp_gatekeeper_pdf_pages(pages)
    cap = int(os.environ.get("GOVERNANCE_GATEKEEPER_TEXT_MAX_CHARS", str(max_chars)))
    with _local_pdf_copy(pdf_path) as local_pdf:
        try:
            import fitz
        except ImportError:
            return ""
        try:
            parts: List[str] = []
            with fitz.open(local_pdf) as doc:
                for i in range(min(n_pages, doc.page_count)):
                    parts.append(doc.load_page(i).get_text("text") or "")
            return "\n".join(parts).strip()[:cap]
        except Exception as exc:
            logger.warning("first-page text extract failed (%s)", exc)
            return ""


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


# Fallback chain when the requested Gatekeeper id is not on models.list() (AI Studio).
# Ordered cheapest → heaviest; 3n-E2B first (usual default on API keys).
_GEMMA_TRIAGE_FALLBACKS = (
    "gemma-3n-e2b-it",
    "gemma-4-e2b-it",
    "gemma-4-e4b-it",
    "gemma-3n-e4b-it",
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
    "gemma-3-4b-it",
    "gemma-3-12b-it",
)
# Gatekeeper on AI Studio: prefer small/fast ids; include 26B/31B when that is all
# the API key lists (common on Gemma-4-only AI Studio projects).
# Gatekeeper must stay fast — never fall back to 26B/31B for yes/no triage.
_GEMMA_GATEKEEPER_AI_FALLBACKS = (
    "gemma-3n-e2b-it",
    "gemma-4-e2b-it",
    "gemma-4-e4b-it",
    "gemma-3n-e4b-it",
    "gemma-3-4b-it",
    "gemma-3-12b-it",
)
_GEMMA_HEAVY_FALLBACKS = (
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
    "gemma-3-27b-it",
    "gemma-3-12b-it",
)
# Demo 3 policy deconstruction + thinking trace (prefer 31B dense).
_GEMMA_THINKING_FALLBACKS = (
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
    "gemma-3-27b-it",
)
# Demo 4 meeting audio/video chunks — must accept audio bytes on AI Studio.
# Do not use ``gemma-4-26b-a4b-it`` (PDF/image MoE) or assume ``gemma-3n-e2b-it`` exists.
# Edge / 3n only — do not put 31B here; many keys list it but reject audio at runtime.
_GEMMA_DEMO4_AUDIO_FALLBACKS = (
    "gemma-4-e4b-it",
    "gemma-4-e2b-it",
    "gemma-3n-e4b-it",
    "gemma-3n-e2b-it",
)
_DEMO4_EDGE_TRY_ALWAYS = _GEMMA_DEMO4_AUDIO_FALLBACKS


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
    msg = (
        f"{role}: {requested!r} not in models.list() — Gemma ids on this key: "
        f"{gemma_ids or '(none)'}; fallback order: {list(fallbacks)}"
    )
    if log_llm_catalog_enabled():
        print(f"\n── {msg} ──")
        for gid in gemma_ids:
            print(f"  {gid}")
        if not gemma_ids:
            print("  (no Gemma ids returned — enable Gemma access in AI Studio)")
        print()
    else:
        logger.info("%s", msg)

    # Don't re-try the requested id in the fallback walk.
    tried = [requested]
    for candidate in fallbacks:
        if candidate == requested or candidate in tried:
            continue
        tried.append(candidate)
        if candidate in available_set:
            logger.info(
                "%s: %r not on this API key — using %r (first listed fallback).",
                role, requested, candidate,
            )
            return candidate

    gemma_ids = sorted(i for i in available if "gemma" in i.lower())
    # Last resort: any listed Gemma id matching our preference order (handles alias drift).
    preference = list(fallbacks) + [g for g in gemma_ids if g not in fallbacks]
    for candidate in preference:
        if candidate in available_set:
            logger.info(
                "%s: %r not on this API key — using %r (first listed Gemma id).",
                role, requested, candidate,
            )
            return candidate
    for candidate in gemma_ids:
        if candidate in available_set:
            logger.info(
                "%s: using %r (only Gemma id on this key).",
                role, candidate,
            )
            return candidate

    raise RuntimeError(
        f"{role} id {requested!r} is not available on this API project, and none "
        f"of the fallbacks {list(fallbacks)} are listed either. "
        f"Gemma ids visible to this key: {gemma_ids or '(none — your project may need Gemma 4 access enabled)'}. "
        f"Set GOVERNANCE_GATEKEEPER_MODEL / GOVERNANCE_GENAI_MODEL to one of those ids."
    )


def _triage_backend_label(model: str) -> str:
    """Human-readable backend for logs (hybrid: E2B → HF, 26B etc. → AI Studio)."""
    try:
        from gemma_hf_backend import use_huggingface_for_model

        return (
            "Hugging Face"
            if use_huggingface_for_model(model, gatekeeper=True)
            else "Google AI Studio"
        )
    except ImportError:
        return "Google AI Studio"


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
        from gemma_hf_backend import call_gemma_hf_multimodal, use_huggingface_for_model

        if use_huggingface_for_model(model, gatekeeper=True):
            resolution = "HIGH" if media_resolution_high else "LOW"
            with gatekeeper_socket_freeze_guard(timeout_seconds):
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

    from genai_quota_retry import call_with_genai_quota_retry

    def _generate() -> Any:
        request_options: dict = {}
        if timeout_seconds:
            request_options["timeout"] = timeout_seconds * 1000  # SDK expects ms
        try:
            return client.models.generate_content(
                model=model,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(**config_kwargs),
                **({"request_options": request_options} if request_options else {}),
            )
        except TypeError:
            # `request_options` kwarg not accepted by this SDK version — retry without.
            return client.models.generate_content(
                model=model,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(**config_kwargs),
            )

    def _generate_with_quota_retry() -> Any:
        return call_with_genai_quota_retry(_generate, label=f"gatekeeper {model}")

    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

    try:
        with gatekeeper_socket_freeze_guard(timeout_seconds):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_generate_with_quota_retry)
                try:
                    response = future.result(timeout=timeout_seconds or None)
                except FuturesTimeoutError as exc:
                    raise TimeoutError(
                        f"Gemma triage timed out after {timeout_seconds}s (model={model!r}). "
                        "Try GOVERNANCE_GATEKEEPER_MODEL=gemma-3n-e2b-it or a smaller listed id."
                    ) from exc
    except NetworkDeadlockError as exc:
        raise TimeoutError(
            f"Gemma triage socket freeze (model={model!r}): {exc}"
        ) from exc

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
    is_m, doc_type, conf, reason, _, _, _ = _verdict_from_json_full(payload)
    return is_m, doc_type, conf, reason


def _verdict_from_json_full(
    payload: Optional[dict],
) -> Tuple[bool, str, float, str, Optional[str], Optional[str], Optional[str]]:
    if not isinstance(payload, dict):
        return False, "other", 0.0, "Model did not return parseable JSON.", None, None, None
    is_meeting = bool(payload.get("is_governance_meeting", False))
    doc_type = str(payload.get("document_or_audio_type", "other"))[:64].strip() or "other"
    if doc_type in _MEETING_DOC_TYPES:
        is_meeting = True
    try:
        confidence = float(payload.get("confidence_score", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    reasoning = str(payload.get("reasoning", ""))[:2000].strip()
    meeting_date = payload.get("meeting_date")
    meeting_title = payload.get("meeting_title")
    instance_slug = payload.get("meeting_instance_slug")
    if meeting_date is not None:
        meeting_date = str(meeting_date).strip()[:10] or None
    if meeting_title is not None:
        meeting_title = str(meeting_title).strip()[:200] or None
    if instance_slug is not None:
        instance_slug = str(instance_slug).strip()[:64] or None
    return is_meeting, doc_type, confidence, reasoning, meeting_date, meeting_title, instance_slug


def _apply_meeting_metadata(
    verdict: TriageVerdict,
    path: Path,
    payload: Optional[dict],
    *,
    raw_root: Optional[Path] = None,
) -> None:
    """Fill meeting_* fields from model JSON with filename/path/PDF fallbacks."""
    (
        _is_m,
        _doc,
        _conf,
        _reason,
        meeting_date,
        meeting_title,
        instance_slug,
    ) = _verdict_from_json_full(payload)
    try:
        from meeting_grouping import (
            infer_instance_slug_from_path,
            infer_meeting_date_from_path,
            slugify_meeting_label,
        )
    except ImportError:
        return
    if not meeting_date and raw_root is not None:
        try:
            from meeting_date_scope import infer_meeting_date_for_file

            meeting_date = infer_meeting_date_for_file(path, raw_root)
        except ImportError:
            pass
    if not meeting_date:
        meeting_date = infer_meeting_date_from_path(path)
    if not instance_slug:
        instance_slug = infer_instance_slug_from_path(path, verdict.document_or_audio_type)
    if not meeting_title:
        meeting_title = instance_slug.replace("-", " ").title()
    verdict.meeting_date = meeting_date
    verdict.meeting_title = meeting_title
    verdict.meeting_instance_slug = slugify_meeting_label(instance_slug or "meeting")


# ─────────────────────────────────────────────────────────────
# Rules-only triage (filename / path / manifest — no PDF read, no API)
# ─────────────────────────────────────────────────────────────

_RULES_AGENDA = re.compile(
    r"(?:^|[-_\s])(?:agenda|agendas)(?:[-_.\s]|\.pdf$|$)",
    re.I,
)
_RULES_MINUTES = re.compile(
    r"(?:^|[-_\s])(?:minutes|minute|mins)(?:[-_.\s]|\.pdf$|$)",
    re.I,
)


def gatekeeper_rules_only_enabled() -> bool:
    """
    Fast hackathon path: classify from filename, path folders, and ``_manifest.json``.

    Set ``GOVERNANCE_GATEKEEPER_RULES_ONLY=0`` to restore Gemma API triage.
    """
    raw = os.environ.get("GOVERNANCE_GATEKEEPER_RULES_ONLY", "").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if raw in ("1", "true", "yes"):
        return True
    return os.environ.get("GOVERNANCE_MODE", "").strip().upper() == "DEMO"


def _rules_classify_path(path: Path, raw_root: Path) -> Tuple[str, bool, float, str]:
    """
    Returns ``(document_or_audio_type, is_governance_meeting, confidence, reasoning)``.
    """
    ext = path.suffix.lower()
    name = path.name
    stem = path.stem
    try:
        rel = path.resolve().relative_to(raw_root.resolve())
        parts_lower = [p.lower() for p in rel.parts]
    except ValueError:
        parts_lower = []

    try:
        from meeting_date_scope import _lookup_manifest_row, jurisdiction_prefix_from_path

        jur = jurisdiction_prefix_from_path(path, raw_root)
        if jur:
            row = _lookup_manifest_row(path, raw_root / Path(*jur.split("/")))
            if row:
                dt = (row.doc_type or "").strip().lower()
                title = (row.anchor_text or "").strip()[:120]
                if dt == "agenda":
                    return (
                        "meeting_agenda",
                        True,
                        0.96,
                        f"manifest doc_type=agenda"
                        + (f"; title={title!r}" if title else ""),
                    )
                if dt == "minutes":
                    return (
                        "meeting_minutes",
                        True,
                        0.96,
                        f"manifest doc_type=minutes"
                        + (f"; title={title!r}" if title else ""),
                    )
                if dt in ("recording", "video", "audio"):
                    kind = "meeting_video" if ext in VIDEO_EXTS else "meeting_audio"
                    return (
                        kind,
                        True,
                        0.94,
                        f"manifest doc_type={dt}"
                        + (f"; title={title!r}" if title else ""),
                    )
    except ImportError:
        pass

    if ext in VIDEO_EXTS:
        return (
            "meeting_video",
            True,
            0.9,
            f"video file {name!r} under jurisdiction tree",
        )
    if ext in AUDIO_EXTS:
        return (
            "meeting_audio",
            True,
            0.9,
            f"audio file {name!r} under jurisdiction tree",
        )

    if ext in PDF_EXTS:
        if "agenda" in parts_lower or _RULES_AGENDA.search(stem) or _RULES_AGENDA.search(name):
            return (
                "meeting_agenda",
                True,
                0.93,
                f"agenda from path/filename: {name!r}",
            )
        if (
            "minutes" in parts_lower
            or _RULES_MINUTES.search(stem)
            or _RULES_MINUTES.search(name)
        ):
            return (
                "meeting_minutes",
                True,
                0.93,
                f"minutes from path/filename: {name!r}",
            )
        dated_meeting_pdf = bool(
            re.search(r"20\d{2}[-_]\d{2}[-_]\d{2}", stem, re.I)
            or re.search(r"20\d{6}", stem)
        )
        if dated_meeting_pdf and ("meetings" in parts_lower or any(
            len(p) == 4 and p.isdigit() and p.startswith("20") for p in parts_lower
        )):
            return (
                "other",
                False,
                0.55,
                f"dated pdf without agenda/minutes in name: {name!r}",
            )
        return (
            "other",
            False,
            0.75,
            f"pdf without agenda/minutes label: {name!r}",
        )

    return ("other", False, 0.5, f"unsupported extension {ext!r}")


def triage_path_by_rules(path: Path, raw_root: Path) -> TriageVerdict:
    """Instant triage from filename, folders, and manifest (no file I/O beyond manifest JSON)."""
    rel_str, geo = relative_geography(path, raw_root)
    ext = path.suffix.lower()
    doc_type, is_meeting, confidence, reasoning = _rules_classify_path(path, raw_root)
    verdict = TriageVerdict(
        is_governance_meeting=is_meeting,
        document_or_audio_type=doc_type,
        confidence_score=confidence,
        reasoning=reasoning,
        triage_kind="pdf" if ext in PDF_EXTS else "audio",
        file_path=str(path),
        relative_path=rel_str,
        geography_label=geo,
        elapsed_seconds=0.0,
        raw_model_text=None,
    )
    _apply_meeting_metadata(verdict, path, None, raw_root=raw_root)
    return verdict


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
        f"citing the specific cue you heard or its absence), "
        f"meeting_date (YYYY-MM-DD or null), meeting_title (string or null), "
        f"meeting_instance_slug (snake_case, e.g. city-council vs planning-commission on the same day)."
    )


PDF_DIRECT_SYSTEM = (
    "You are a document triage gatekeeper for a local-government open-data pipeline. "
    "You inspect the attached PDF (first pages only) and classify whether it is an "
    "official meeting Agenda or official meeting Minutes. You return strict JSON only."
)

PDF_DIRECT_USER = (
    "The attached PDF contains the first {pages} page(s) of a document.\n"
    "Digital text from those pages (empty if scanned):\n\n"
    "{excerpt}\n\n"
    "Classify the PDF as one of:\n"
    "  • meeting_agenda — itemized agenda with body name, date, location, agenda items, "
    "    often Pledge / Roll Call / Adjournment;\n"
    "  • meeting_minutes — minutes header, motions, votes, members present/absent;\n"
    "  • other — invoices, brochures, reference packets, slide decks, correspondence, "
    "    financial tables without meeting framing, etc.\n\n"
    "Only meeting_agenda and meeting_minutes count as governance meetings. "
    "The first pages must show meeting framing (body + date + agenda or minutes structure).\n\n"
    "Return ONLY JSON with keys: is_governance_meeting, document_or_audio_type, "
    "confidence_score, reasoning, meeting_date (YYYY-MM-DD or null), meeting_title, "
    "meeting_instance_slug."
)

PDF_TEXT_SYSTEM = (
    "You are a document triage gatekeeper for a local-government open-data pipeline. "
    "You classify pasted text from the first page(s) of a PDF as meeting agenda, "
    "meeting minutes, or other. You return strict JSON only."
)

PDF_TEXT_USER = (
    "The excerpt below is the digital text layer from the **first page(s)** of a PDF "
    "(not the full document). Classify it as:\n"
    "  • meeting_agenda — itemized agenda with body name, date, agenda items, Pledge / Adjournment;\n"
    "  • meeting_minutes — minutes header, motions, votes, members present;\n"
    "  • other — forms, financial tables, brochures, correspondence without meeting framing.\n\n"
    "Only meeting_agenda and meeting_minutes count as governance meetings.\n\n"
    "Return ONLY JSON with keys: is_governance_meeting, document_or_audio_type, "
    "confidence_score, reasoning, meeting_date (YYYY-MM-DD or null), meeting_title, "
    "meeting_instance_slug.\n\n"
    "=== TEXT EXCERPT ===\n"
    "{excerpt}\n"
)


def _fill_verdict_from_triage_call(
    verdict: TriageVerdict,
    pdf_path: Path,
    parsed: Optional[dict],
    raw: Optional[str],
    t0: float,
    *,
    raw_root: Optional[Path] = None,
) -> TriageVerdict:
    is_m, doc_type, conf, reason = _verdict_from_json(parsed)
    verdict.is_governance_meeting = is_m
    verdict.document_or_audio_type = doc_type
    verdict.confidence_score = conf
    verdict.reasoning = reason
    verdict.raw_model_text = raw[:4000] if raw else None
    _apply_meeting_metadata(verdict, pdf_path, parsed, raw_root=raw_root)
    verdict.elapsed_seconds = round(time.time() - t0, 2)
    return verdict


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
    """Run gatekeeper on the first ``pages`` of ``pdf_path`` (PDF bytes or text; no PNG)."""
    del dpi  # legacy CLI / notebook arg — pixmap render removed
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
    pages = resolve_gatekeeper_page_count(pdf_path, pages)
    t0 = time.time()
    _timeout = int(os.environ.get("GOVERNANCE_GATEKEEPER_API_TIMEOUT_SECONDS", "120"))

    excerpt = ""
    if gatekeeper_text_first_enabled():
        excerpt = extract_first_pages_text(pdf_path, pages=pages)

    try:
        from gemma_hf_backend import use_huggingface_for_model

        use_hf = use_huggingface_for_model(model, gatekeeper=True)
    except ImportError:
        use_hf = False

    if use_hf or not gatekeeper_pdf_direct_enabled():
        if not excerpt.strip():
            verdict.error = (
                "HF Gatekeeper needs a digital text layer on pages 1–2 "
                "(use AI Studio / GOVERNANCE_GATEKEEPER_PDF_DIRECT=1 for scanned PDFs)."
            )
            verdict.elapsed_seconds = round(time.time() - t0, 2)
            return verdict
        logger.info(
            "  text-only triage | %s | %d chars from pages 1-%d",
            pdf_path.name,
            len(excerpt),
            pages,
        )
        logger.info(
            "  gemma START (text-only) | backend=%s | model=%s | timeout=%ds",
            _triage_backend_label(model),
            model,
            _timeout,
        )
        flush_gatekeeper_logs()
        try:
            parsed, raw = call_gemma_triage(
                client=client,
                model=model,
                system_instruction=PDF_TEXT_SYSTEM,
                user_text=PDF_TEXT_USER.format(excerpt=excerpt),
                media=[],
                media_resolution_high=False,
                thinking_budget=0,
                timeout_seconds=_timeout,
            )
        except Exception as e:
            verdict.error = f"Gemma text triage failed: {e}"
            verdict.elapsed_seconds = round(time.time() - t0, 2)
            return verdict
        logger.info(
            "  gemma DONE (text-only) | %s | %.1fs",
            pdf_path.name,
            time.time() - t0,
        )
        flush_gatekeeper_logs()
        return _fill_verdict_from_triage_call(
            verdict, pdf_path, parsed, raw, t0, raw_root=raw_root
        )

    try:
        pdf_subset = extract_first_pages_pdf_bytes(pdf_path, pages=pages)
    except Exception as e:
        verdict.error = f"PDF subset extract failed: {e}"
        verdict.elapsed_seconds = round(time.time() - t0, 2)
        return verdict

    excerpt_block = excerpt.strip() if excerpt.strip() else "(no digital text layer on these pages)"
    logger.info(
        "  pdf-direct triage | %s | pages 1-%d | subset=%.1f KB | excerpt=%d chars",
        pdf_path.name,
        pages,
        len(pdf_subset) / 1024,
        len(excerpt),
    )
    logger.info(
        "  gemma START (pdf) | backend=%s | %s | model=%s | timeout=%ds",
        _triage_backend_label(model),
        pdf_path.name,
        model,
        _timeout,
    )
    flush_gatekeeper_logs()
    try:
        parsed, raw = call_gemma_triage(
            client=client,
            model=model,
            system_instruction=PDF_DIRECT_SYSTEM,
            user_text=PDF_DIRECT_USER.format(pages=pages, excerpt=excerpt_block),
            media=[(pdf_subset, "application/pdf")],
            media_resolution_high=False,
            thinking_budget=0,
            timeout_seconds=_timeout,
        )
    except Exception as e:
        verdict.error = f"Gemma PDF triage failed: {e}"
        verdict.elapsed_seconds = round(time.time() - t0, 2)
        return verdict

    logger.info(
        "  gemma DONE (pdf) | %s | %.1fs",
        pdf_path.name,
        time.time() - t0,
    )
    flush_gatekeeper_logs()
    return _fill_verdict_from_triage_call(
        verdict, pdf_path, parsed, raw, t0, raw_root=raw_root
    )


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
        _timeout = int(os.environ.get("GOVERNANCE_GATEKEEPER_API_TIMEOUT_SECONDS", "120"))
        logger.info(
            "  gemma START (audio) | backend=%s | %s | model=%s | timeout=%ds",
            _triage_backend_label(model),
            audio_path.name,
            model,
            _timeout,
        )
        flush_gatekeeper_logs()
        try:
            parsed, raw = call_gemma_triage(
                client=client,
                model=model,
                system_instruction=AUDIO_SYSTEM,
                user_text=audio_user_prompt(window_seconds),
                media=media,
                media_resolution_high=False,  # audio is unaffected by image media_resolution
                thinking_budget=0,
                timeout_seconds=_timeout,
            )
        except Exception as e:
            verdict.error = f"Gemma triage call failed: {e}"
            verdict.elapsed_seconds = round(time.time() - t0, 2)
            return verdict

        logger.info(
            "  gemma DONE (audio) | %s | %.1fs",
            audio_path.name,
            time.time() - t0,
        )
        flush_gatekeeper_logs()

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


def _path_under_jurisdiction(
    path: Path,
    *,
    jurisdiction_root: Optional[Path],
) -> bool:
    """True when ``jurisdiction_root`` is unset or ``path`` lies under it."""
    if jurisdiction_root is None:
        return True
    try:
        path.resolve().relative_to(jurisdiction_root.resolve())
        return True
    except ValueError:
        return False


def count_triageable_files(
    raw_root: Path,
    *,
    kinds: Iterable[str] = ("pdf", "audio"),
    jurisdiction_root: Optional[Path] = None,
) -> int:
    """Count PDF/audio files Gatekeeper would walk (for scope banners before a long run)."""
    return sum(
        1
        for _ in iter_triageable_files(
            raw_root, kinds=kinds, jurisdiction_root=jurisdiction_root
        )
    )


def _triage_recency_key(path: Path) -> tuple[float, int, str]:
    """Sort key: newest mtime first, then calendar folder year, then path."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    year = 0
    for part in path.parts:
        if len(part) == 4 and part.isdigit() and part.startswith("20"):
            year = max(year, int(part))
    return (mtime, year, path.as_posix())


def resolve_gatekeeper_max_files(explicit: Optional[int] = None) -> Optional[int]:
    """
    Max files to send to the Gatekeeper API after :func:`narrow_gatekeeper_candidates`.

    DEMO mode defaults to **12** when unset (hackathon-sized).
    """
    if explicit is not None:
        return explicit if explicit > 0 else None
    env = os.environ.get("GOVERNANCE_GATEKEEPER_MAX_FILES", "").strip()
    if env:
        n = int(env)
        return n if n > 0 else None
    if os.environ.get("GOVERNANCE_MODE", "").strip().upper() == "DEMO":
        return 12
    return None


def select_triageable_files(
    raw_root: Path,
    *,
    kinds: Iterable[str] = ("pdf", "audio"),
    max_files: Optional[int] = None,
    max_meeting_dates: Optional[int] = None,
    jurisdiction_root: Optional[Path] = None,
    progress_stdout: Optional[bool] = None,
) -> tuple[list[Path], int, Optional[dict], Optional[dict]]:
    """
    Choose Gatekeeper inputs.

    When date scope is enabled (DEMO default: last **3** meeting dates per
    jurisdiction, pdf + audio + collateral only), see
    :mod:`meeting_date_scope`.

    Otherwise applies optional **count** cap (newest N by mtime).

    Returns ``(selected_paths, total_walk_candidates, allowed_dates_by_jurisdiction, allowed_year_folders)``.
    """
    show_progress = (
        gatekeeper_progress_stdout_enabled()
        if progress_stdout is None
        else progress_stdout
    )
    every = _gatekeeper_progress_interval()
    t_select = time.perf_counter()
    jur_label = ""
    if jurisdiction_root is not None:
        try:
            jur_label = jurisdiction_root.resolve().relative_to(raw_root.resolve()).as_posix()
        except ValueError:
            jur_label = str(jurisdiction_root)

    allowed_year_folders: Optional[dict] = None
    try:
        from meeting_date_scope import (
            discover_year_folders_scoped,
            prune_year_folder_dirnames,
            resolve_demo_year_folder_scope,
        )

        if resolve_demo_year_folder_scope():
            if show_progress:
                _gatekeeper_progress(
                    "  Gatekeeper | resolving newest 20xx/ folder"
                    + (f" for {jur_label} …" if jur_label else " per jurisdiction …")
                )
            t_year = time.perf_counter()
            allowed_year_folders = discover_year_folders_scoped(
                raw_root, jurisdiction_root=jurisdiction_root
            )
            if show_progress:
                from colab_timed_steps import format_elapsed

                _gatekeeper_progress(
                    f"  Gatekeeper | year folders resolved — {format_elapsed(time.perf_counter() - t_year)}"
                )
            if allowed_year_folders:
                logger.info(
                    "Gatekeeper walk | DEMO year-folder scope (skip older 20xx/ trees)"
                )
                for jur, year in sorted(allowed_year_folders.items()):
                    logger.info("  %s → only %s/", jur, year)
    except ImportError:
        pass

    if show_progress:
        where = f" under {jur_label}" if jur_label else f" under {raw_root}"
        _gatekeeper_progress(
            f"  Gatekeeper | walking Drive for pdf/audio{where} (can take several minutes) …"
        )

    t_walk = time.perf_counter()
    paths: List[Path] = []
    for n, path in enumerate(
        iter_triageable_files(
            raw_root,
            kinds=kinds,
            allowed_year_folders=allowed_year_folders,
            jurisdiction_root=jurisdiction_root,
        ),
        1,
    ):
        paths.append(path)
        if show_progress and n % every == 0:
            from colab_timed_steps import format_elapsed

            _gatekeeper_progress(
                f"  Gatekeeper | … found {n} pdf/audio file(s) so far "
                f"({format_elapsed(time.perf_counter() - t_walk)})"
            )

    total = len(paths)
    if show_progress:
        from colab_timed_steps import format_elapsed

        _gatekeeper_progress(
            f"  Gatekeeper | walk done — {total} pdf/audio path(s) in "
            f"{format_elapsed(time.perf_counter() - t_walk)}; classifying agendas/minutes …"
        )
    t_classify = time.perf_counter()

    # Gatekeeper must see agenda/minutes candidates *before* dates are known.
    # Demo meeting-date caps apply to post-triage demos (filter_inventory_media), not here.
    try:
        from meeting_date_scope import (
            apply_year_folder_scope_to_candidates,
            file_media_role,
        )

        candidates: List[Path] = []
        for i, p in enumerate(paths, 1):
            if file_media_role(p, raw_root) is not None:
                candidates.append(p)
            if show_progress and (i % every == 0 or i == total):
                from colab_timed_steps import format_elapsed

                _gatekeeper_progress(
                    f"  Gatekeeper | … classified {i}/{total} paths | "
                    f"meeting-media: {len(candidates)} "
                    f"({format_elapsed(time.perf_counter() - t_classify)})"
                )
        if not candidates and paths:
            logger.warning(
                "Gatekeeper: %d pdf/audio path(s) on disk but 0 meeting-media roles "
                "(agenda/minutes/2026/ or meetings/…). Check Drive sync.",
                len(paths),
            )
        candidates = apply_year_folder_scope_to_candidates(candidates, raw_root)
        try:
            from meeting_date_scope import narrow_gatekeeper_candidates

            date_cap = max_meeting_dates
            if date_cap is None:
                try:
                    from meeting_date_scope import resolve_demo_meeting_dates_limit

                    date_cap = resolve_demo_meeting_dates_limit()
                except ImportError:
                    pass
            candidates, allowed_dates = narrow_gatekeeper_candidates(
                candidates,
                raw_root,
                max_files=max_files,
                max_dates=date_cap,
            )
        except ImportError:
            candidates.sort(key=_triage_recency_key)
            cap = resolve_gatekeeper_max_files(max_files)
            if cap is not None and len(candidates) > cap:
                candidates = candidates[-cap:]
            allowed_dates = None
        if show_progress:
            from colab_timed_steps import format_elapsed

            _gatekeeper_progress(
                f"  Gatekeeper | selection done — will_triage={len(candidates)} "
                f"(from {total} on disk) | total {format_elapsed(time.perf_counter() - t_select)}"
            )
        return candidates, total, allowed_dates, allowed_year_folders
    except ImportError:
        pass

    paths.sort(key=_triage_recency_key)
    cap = resolve_gatekeeper_max_files(max_files)
    if cap is not None and len(paths) > cap:
        paths = paths[-cap:]
    return paths, total, None, allowed_year_folders


def iter_triageable_files(
    raw_root: Path,
    *,
    kinds: Iterable[str] = ("pdf", "audio"),
    allowed_year_folders: Optional[dict] = None,
    jurisdiction_root: Optional[Path] = None,
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
        if allowed_year_folders:
            try:
                from meeting_date_scope import prune_year_folder_dirnames

                prune_year_folder_dirnames(
                    Path(dirpath), dirnames, raw_root_resolved, allowed_year_folders
                )
            except ImportError:
                pass
        # Stable order so demo runs read predictably.
        dirnames.sort()

        for fn in sorted(filenames):
            path = Path(dirpath) / fn
            if not _path_under_jurisdiction(path, jurisdiction_root=jurisdiction_root):
                continue
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
    log_path: Optional[Path | str] = None,
    flush_log_each_file: bool = True,
    organize_meetings: bool = False,
    jurisdiction_root: Optional[Path] = None,
    preselected_paths: Optional[Sequence[Path]] = None,
) -> TriageReport:
    """Walk ``raw_root``, triage every PDF / audio; optionally move rejects (see env).

    When ``jurisdiction_root`` is set, only files under that directory are triaged
    (paths still use ``raw_root`` for geography / excluded_inputs layout).

    Pass ``preselected_paths`` when the caller already ran :func:`select_triageable_files`
    (avoids a second Drive walk).
    """
    if not raw_root.is_dir():
        raise FileNotFoundError(f"Raw inputs root not found: {raw_root}")

    if log_path is not None and not logger.handlers:
        configure_logging(verbose=True, log_path=log_path, console=True)

    _fsync_logs = os.environ.get("GOVERNANCE_GATEKEEPER_FSYNC", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    move_excluded = gatekeeper_move_excluded_enabled()
    excluded_root = (raw_root / EXCLUDED_DIRNAME) if move_excluded else None
    if move_excluded and excluded_root is not None and not dry_run:
        excluded_root.mkdir(parents=True, exist_ok=True)

    excluded_label = str(excluded_root) if excluded_root else "(none — rejects stay in place)"
    logger.info(
        "Gatekeeper start | raw_root=%s | excluded_root=%s | model=%s",
        raw_root,
        excluded_label,
        model,
    )
    if dry_run:
        logger.info("(dry-run: no files will be moved)")
    elif not move_excluded:
        logger.info("(rejects are not moved; triage report records EXCLUDE verdicts)")

    kinds_tuple = tuple(k.strip().lower() for k in kinds if str(k).strip())
    pdf_pages = clamp_gatekeeper_pdf_pages(pdf_pages)
    rules_only = gatekeeper_rules_only_enabled()
    client = None

    if rules_only:
        logger.info(
            "Gatekeeper rules-only | classify from filename, path folders, and "
            "_manifest.json doc_type (no PDF read, no ffmpeg, no API)"
        )
    else:
        logger.info(
            "Gatekeeper PDF triage | first %d page(s) per file as PDF subset (max %d)",
            pdf_pages,
            MAX_GATEKEEPER_PDF_PAGES,
        )

    try:
        from gemma_hf_backend import (
            ensure_hf_ready_for_triage,
            hf_weights_cached,
            gatekeeper_use_huggingface,
            print_hf_model_catalog,
            resolve_hf_model_id,
        )
    except ImportError:
        gatekeeper_use_huggingface = lambda: False  # type: ignore[assignment]

    if not rules_only:
        if gatekeeper_use_huggingface():
            if log_llm_catalog_enabled():
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
            if log_llm_catalog_enabled():
                print_available_models(client, requested=(model,), role="Gatekeeper triage")
            model = resolve_model_id(
                client,
                model,
                fallbacks=_GEMMA_GATEKEEPER_AI_FALLBACKS,
                role="Gatekeeper triage model",
            )
        logger.info("Gatekeeper resolved model | model=%s", model)

    report = TriageReport(raw_root=str(raw_root), excluded_root=excluded_label)

    try:
        from meeting_date_scope import resolve_demo_meeting_dates_limit
    except ImportError:
        resolve_demo_meeting_dates_limit = lambda _=None: None  # type: ignore

    date_cap = resolve_demo_meeting_dates_limit()
    count_cap = resolve_gatekeeper_max_files(max_files)
    if preselected_paths is not None:
        triage_paths = list(preselected_paths)
        total_candidates = len(triage_paths)
        allowed_dates = None
        allowed_years = None
        logger.info(
            "Gatekeeper: using %d pre-selected path(s) (skip re-walk)",
            len(triage_paths),
        )
    else:
        logger.info(
            "Gatekeeper: scanning %s (DEMO = newest year folder, then last meeting dates) …",
            raw_root,
        )
        flush_gatekeeper_logs(fsync=_fsync_logs)
        triage_paths, total_candidates, allowed_dates, allowed_years = select_triageable_files(
            raw_root,
            kinds=kinds,
            max_files=max_files,
            jurisdiction_root=jurisdiction_root,
            progress_stdout=progress_stdout,
        )
    flush_gatekeeper_logs(fsync=_fsync_logs)
    if jurisdiction_root is not None:
        try:
            jur_label = jurisdiction_root.resolve().relative_to(raw_root.resolve()).as_posix()
        except ValueError:
            jur_label = str(jurisdiction_root)
        logger.info("Gatekeeper jurisdiction scope | %s", jur_label)
    if allowed_years:
        logger.info(
            "Gatekeeper year scope | walked %d pdf/audio path(s) under newest 20xx/ only",
            total_candidates,
        )
    if allowed_dates:
        logger.info(
            "Gatekeeper date scope | candidates=%d | triaging=%d unique doc(s) | "
            "last %d meeting date(s)/jurisdiction in that year",
            total_candidates,
            len(triage_paths),
            date_cap or 0,
        )
        for jur, dates in sorted(allowed_dates.items()):
            logger.info("  %s → %s", jur, ", ".join(sorted(dates)))
        for p in triage_paths[:20]:
            rel, _ = relative_geography(p, raw_root)
            logger.info("  selected: %s", rel)
        if len(triage_paths) > 20:
            logger.info("  … and %d more", len(triage_paths) - 20)
    elif count_cap is not None and total_candidates > count_cap:
        logger.info(
            "Gatekeeper file selection | candidates=%d | triaging_newest=%d",
            total_candidates,
            len(triage_paths),
        )
        for p in triage_paths:
            rel, _ = relative_geography(p, raw_root)
            logger.info("  selected (newest): %s", rel)

    if not triage_paths:
        jur_hint = ""
        if jurisdiction_root is not None:
            try:
                jur_hint = jurisdiction_root.resolve().relative_to(raw_root.resolve()).as_posix()
            except ValueError:
                jur_hint = str(jurisdiction_root)
        report.selection_note = (
            f"No files selected for triage (walked {total_candidates} pdf/audio path(s) on disk"
            + (f" under {jur_hint}" if jur_hint else "")
            + "). DEMO year/date filters removed every candidate before any Gemma call — "
            "this is not an API failure. Fixes: pull latest open-navigator; set "
            "GOVERNANCE_DEMO_YEAR_SCOPE=0 in §3; or GOVERNANCE_GATEKEEPER_ENABLED=0 to skip Gatekeeper."
        )
        report.skipped.append(report.selection_note)
        logger.error(report.selection_note)
        flush_gatekeeper_logs(fsync=_fsync_logs)
        return report

    processed = 0
    t_api_sweep = time.perf_counter()
    api_seconds = 0.0
    for path in triage_paths:
        processed += 1
        ext = path.suffix.lower()
        rel_str, geo = relative_geography(path, raw_root)
        if progress_stdout:
            cap_label = f"/{len(triage_paths)}" if triage_paths else ""
            logger.info("[Gatekeeper %d%s] %s", processed, cap_label, rel_str)

        logger.info("Triage START | %s", rel_str)
        flush_gatekeeper_logs(fsync=_fsync_logs)

        try:
            if rules_only:
                verdict = triage_path_by_rules(path, raw_root)
            elif ext in PDF_EXTS:
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

        # PROCEED rule: governance meeting AND confidence ≥ threshold.
        # ``document_or_audio_type`` in meeting_* counts even when the bool was omitted/wrong.
        verdict.proceed = (
            (
                verdict.is_governance_meeting
                or verdict.document_or_audio_type in _MEETING_DOC_TYPES
            )
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

        # EXCLUDE: optional move under excluded_inputs/ (off by default).
        if move_excluded and excluded_root is not None:
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
        else:
            logger.info(
                "EXCLUDE | %s | %s | type=%s conf=%.2f | left in place | %s",
                geo or "(root)", path.name,
                verdict.document_or_audio_type, verdict.confidence_score,
                verdict.reasoning[:160],
            )

        report.add(verdict)
        api_seconds += getattr(verdict, "elapsed_seconds", 0.0) or 0.0
        if progress_stdout:
            _gatekeeper_progress(
                f"  Gatekeeper | [{processed}/{len(triage_paths)}] "
                f"{'rules' if rules_only else f'{verdict.elapsed_seconds:.1f}s'} | "
                f"{rel_str} | "
                f"{'KEEP' if verdict.proceed else 'EXCLUDE' if not verdict.error else 'ERROR'} "
                f"({verdict.document_or_audio_type})"
            )

        if flush_log_each_file:
            flush_gatekeeper_logs(fsync=_fsync_logs)

    sweep_elapsed = time.perf_counter() - t_api_sweep
    try:
        from colab_timed_steps import format_elapsed
    except ImportError:
        format_elapsed = lambda s: f"{s:.1f}s"  # type: ignore

    logger.info(
        "Gatekeeper done | processed=%d | proceed=%d | excluded=%d | errors=%d | "
        "api_wall=%s | api_model_sum=%.1fs",
        processed,
        len(report.proceed),
        len(report.excluded),
        len(report.errors),
        format_elapsed(sweep_elapsed),
        api_seconds,
    )
    if progress_stdout:
        _gatekeeper_progress(
            f"  Gatekeeper | API sweep finished — wall {format_elapsed(sweep_elapsed)}, "
            f"model time sum {api_seconds:.1f}s"
        )
    flush_gatekeeper_logs(fsync=_fsync_logs)

    if organize_meetings and report.proceed and not dry_run:
        try:
            from meeting_grouping import organize_proceed_into_meeting_folders

            moves = organize_proceed_into_meeting_folders(
                raw_root,
                report.proceed,
                dry_run=False,
                client=client,
                model=model,
            )
            logger.info("Organized %d file(s) into meetings/ folders", len(moves))
        except Exception as exc:
            logger.error("Meeting folder organization failed: %s", exc)

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
        from gemma_hf_backend import ensure_hf_token, gatekeeper_use_huggingface

        if gatekeeper_use_huggingface():
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
    """Backward-compatible alias — prefer :func:`configure_logging`."""
    configure_logging(verbose=verbose, log_path=None, console=True)


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

    raw_root = (args.raw_root or _default_raw_root()).expanduser().resolve()
    log_file = args.report_path.with_suffix(".log") if args.report_path else None
    configure_logging(verbose=args.verbose, log_path=log_file, console=True)

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
