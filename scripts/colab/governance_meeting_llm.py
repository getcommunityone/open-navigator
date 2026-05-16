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
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".webm", ".mp4"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

# Folders inside a jurisdiction directory that hold scraper-temp artifacts and
# are unsafe to send to the model. ``_contact_images`` is intentionally NOT in
# this list — Demo 5 enriches contact photos with perceived demographics.
SKIP_DIR_PREFIXES: tuple[str, ...] = ()
SKIP_DIR_NAMES = {"__pycache__", ".ipynb_checkpoints", "_crawl_html", "_sitemaps", "excluded_inputs"}

# Token-budget tiers we expose to judges. Names match Gemma 4 media-resolution levels.
TOKEN_BUDGET_HIGH = "HIGH"   # ~1,120 tokens per image — financial tables, ledgers, bids
TOKEN_BUDGET_MEDIUM = "MEDIUM"
TOKEN_BUDGET_LOW = "LOW"     # ~64 tokens per image — standard text-heavy minutes


def model_supports_thinking(model: str) -> bool:
    """Whether the model accepts ``thinking_config`` (``thinking_budget`` /
    ``include_thoughts``).

    The ``gemma-4-26b-a4b-it`` alias has been observed to return ``400
    INVALID_ARGUMENT: Thinking budget is not supported for this model``,
    so by default we skip ``thinking_config`` for any model whose id starts
    with ``gemma``. Gemini 2.5+ accepts it.

    Override with env ``GOVERNANCE_FORCE_THINKING=1`` if you've picked a Gemma 4
    variant (e.g. 31B Dense) that supports thinking via the SDK config.
    """
    import os
    if os.environ.get("GOVERNANCE_FORCE_THINKING", "0") == "1":
        return True
    return not (model or "").lower().startswith("gemma")


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
                    elif ext in AUDIO_EXTS:
                        inv.audio.append(f)
                    elif ext in IMAGE_EXTS:
                        inv.images.append(f)
                yield inv


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


def chunk_audio_ffmpeg(
    audio_path: Path,
    *,
    out_dir: Path,
    chunk_minutes: int = 15,
    fmt: str = "mp3",
) -> List[Path]:
    """
    Split ``audio_path`` into ``chunk_minutes``-minute pieces via ffmpeg's
    segmenter. Returns the sorted list of chunk paths under ``out_dir``.
    Raises if ffmpeg is not on PATH — Colab ships with it by default.
    """
    if not _ffmpeg_available():
        raise RuntimeError(
            "ffmpeg not found on PATH. On Colab it ships by default; locally run "
            "`apt-get install -y ffmpeg` or `brew install ffmpeg`."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = audio_path.stem
    pattern = out_dir / f"{stem}_chunk_%03d.{fmt}"
    seconds = max(60, int(chunk_minutes * 60))
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(audio_path),
        "-f", "segment", "-segment_time", str(seconds),
        "-c:a", "libmp3lame" if fmt == "mp3" else "copy",
        str(pattern),
    ]
    subprocess.run(cmd, check=True)
    return sorted(out_dir.glob(f"{stem}_chunk_*.{fmt}"))


# ─────────────────────────────────────────────────────────────
# Google GenAI client wrapper (multimodal + thinking + media_resolution)
# ─────────────────────────────────────────────────────────────


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

    Set ``GOVERNANCE_LLM_BACKEND=huggingface`` to run local weights from Hugging Face
    (``google/gemma-4-E4B-it`` via ``AutoModelForImageTextToText``). Otherwise uses
    ``pip install google-genai>=1.0`` and AI Studio.
    """
    try:
        from gemma_hf_backend import call_gemma_hf_multimodal, use_huggingface

        if use_huggingface():
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
            if thinking_budget is not None:
                tc_kwargs["thinking_budget"] = thinking_budget
            config_kwargs["thinking_config"] = ThinkingConfig(**tc_kwargs)
    elif include_thoughts or thinking_budget is not None:
        # Model rejects thinking_config server-side (Gemma 4 returns 400
        # INVALID_ARGUMENT: "Thinking budget is not supported for this model").
        # Run the prompt as a normal generation; thoughts will come back empty.
        print(
            f"   ℹ️  Skipping thinking_config: {model!r} does not support it. "
            "Demo 3's reasoning-trace output will be empty — use a Gemini 2.5+ model "
            "(e.g. gemini-2.5-flash) via GOVERNANCE_GENAI_MODEL to see thinking output."
        )

    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(**config_kwargs),
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

    result = call_google_genai_multimodal(
        api_key=api_key,
        model=model,
        system_instruction=system_instruction,
        user_text=user_text,
        media=media,
        temperature=0.0,
        max_output_tokens=max_output_tokens,
        # Don't request thinking — transcription is mechanical, and Gemma 4 returns
        # 400 INVALID_ARGUMENT if thinking_config is attached to non-thinking variants.
        include_thoughts=False,
        thinking_budget=None,
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

    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=[types.Part.from_text(text=policy_prompt)])],
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=512,
            response_mime_type="application/json",
        ),
    )

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


def policy_drift_summarize(
    chunk_jsons: List[Dict[str, Any]],
    *,
    api_key: str,
    model: str,
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

    result = call_google_genai_multimodal(
        api_key=api_key,
        model=model,
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
    "PDF_EXTS", "AUDIO_EXTS", "IMAGE_EXTS",
    "TOKEN_BUDGET_HIGH", "TOKEN_BUDGET_MEDIUM", "TOKEN_BUDGET_LOW",
    "JurisdictionDir", "MeetingInventory",
    "PdfPageRender", "GenAIResult",
    "load_text_file", "chunk_text",
    "parse_policy_analysis_response",
    "parse_jurisdiction_dir", "walk_raw_inputs", "mirror_output_path",
    "classify_pdf_page_heuristic", "render_pdf_pages",
    "extract_pdf_digital_text", "is_scanned_pdf",
    "chunk_audio_ffmpeg",
    "call_google_genai_multimodal",
    "transcribe_audio_with_gemma", "TRANSCRIPTION_SUPPORTED_LANGUAGES",
    "embed_text_with_gemma", "cosine_similarity_matrix",
    "shield_review_text", "SHIELD_HARM_CATEGORIES",
    "model_supports_thinking",
    "policy_drift_summarize",
    "load_meeting_data_lookup", "load_contacts_lookup",
    "merge_meeting_data_by_jurisdiction", "merge_contacts_by_jurisdiction",
    "mime_for",
    "OpenAICompatibleConfig", "call_openai_compatible_chat",
]
