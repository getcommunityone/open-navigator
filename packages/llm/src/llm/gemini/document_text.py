"""
Bytes-based document text extraction for on-demand meeting-doc comparison.

A BYTES-based companion to the disk-path ``_normalize_to_text`` in
:mod:`llm.gemini.meeting_document_enrichment`. The enrichment module reads
already-scraped files from disk; this module extracts plain text from the raw
``bytes`` of a document fetched on demand (e.g. an agenda/minutes URL the user
clicks to compare against the AI summary). It mirrors the same per-format logic
(PDF via PyMuPDF/fitz, DOCX via python-docx, HTML via BeautifulSoup, plus a
free OCR fallback for scanned PDFs) and shares the same size guards.

Never raises on a malformed document: extraction failures are logged and an
empty string is returned so callers can render an "unavailable" state.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import urlparse

from loguru import logger

# Reuse the shared constants + the free OCR fallback from the enrichment module
# rather than re-defining them, so both paths stay in lockstep.
from llm.gemini.meeting_document_enrichment import (
    _MAX_DOC_CHARS,
    _MIN_TEXT_CHARS,
    _ocr_pdf_text,
)

__all__ = ["extract_text_from_bytes"]

# Content-type fragments → document kind.
_PDF_TYPES = ("application/pdf", "application/x-pdf")
_DOCX_TYPES = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)
_DOC_TYPES = ("application/msword",)
_HTML_TYPES = ("text/html", "application/xhtml")
_TEXT_TYPES = ("text/plain",)


def _ext_from_url(url: str) -> str:
    """Lower-case file extension from a URL path (no leading dot). '' if none."""
    try:
        path = urlparse(url).path
    except (ValueError, TypeError):
        path = url or ""
    suffix = PurePosixPath(path).suffix
    return suffix.lstrip(".").lower()


def _kind_from_signals(content: bytes, *, url: str, content_type: str | None) -> str:
    """Decide document kind from content_type, then URL extension, then magic bytes.

    Returns one of: 'pdf', 'docx', 'doc', 'html', 'text', or '' (unknown).
    """
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    if ct:
        if any(t in ct for t in _PDF_TYPES):
            return "pdf"
        if any(t in ct for t in _DOCX_TYPES):
            return "docx"
        if any(t in ct for t in _DOC_TYPES):
            return "doc"
        if any(t in ct for t in _HTML_TYPES):
            return "html"
        if any(t in ct for t in _TEXT_TYPES):
            return "text"

    ext = _ext_from_url(url)
    if ext == "pdf":
        return "pdf"
    if ext == "docx":
        return "docx"
    if ext == "doc":
        return "doc"
    if ext in ("html", "htm"):
        return "html"
    if ext in ("txt", "text"):
        return "text"

    # Magic bytes — a %PDF header is definitive even with no type/extension.
    if content[:5].startswith(b"%PDF"):
        return "pdf"
    # DOCX is a ZIP (PK\x03\x04); only claim it when nothing else matched.
    if content[:4] == b"PK\x03\x04":
        return "docx"

    # Default to HTML when the body looks like markup, else plain text.
    head = content[:512].lstrip().lower()
    if head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<body" in head:
        return "html"
    return "text"


def _pdf_text(content: bytes) -> str:
    """Extract a PDF's text layer; OCR-fallback for scanned PDFs (no text layer)."""
    import fitz  # PyMuPDF

    with fitz.open(stream=content, filetype="pdf") as doc:
        text = "\n".join(page.get_text() for page in doc).strip()
    if len(text) < _MIN_TEXT_CHARS:
        # Scanned / no text layer: recover via the FREE local OCR fallback.
        ocr_text = _ocr_pdf_text(content)
        if len(ocr_text) > len(text):
            logger.info(
                "PDF text layer thin ({} chars) — using OCR fallback ({} chars)",
                len(text),
                len(ocr_text),
            )
            return ocr_text.strip()
    return text


def _docx_text(content: bytes) -> str:
    import docx  # python-docx

    document = docx.Document(BytesIO(content))
    return "\n".join(p.text for p in document.paragraphs if p.text.strip()).strip()


def _html_text(content: bytes) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content.decode("utf-8", errors="ignore"), "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(" ", strip=True).strip()


def extract_text_from_bytes(
    content: bytes, *, url: str, content_type: str | None = None
) -> str:
    """Extract plain text from raw document bytes. Returns '' on any failure.

    The document kind is decided from ``content_type`` (preferred), then the
    ``url`` extension, then magic bytes (``%PDF`` / ZIP). Supported: PDF, DOCX,
    HTML/HTM, and plain text. Legacy binary ``.doc`` is unsupported (no
    pure-python reader) → ''. The returned text is capped at ``_MAX_DOC_CHARS``.

    Never raises: extraction errors are caught and logged, returning '' so the
    caller can show an "unavailable" state instead of failing.
    """
    if not content:
        return ""

    kind = _kind_from_signals(content, url=url, content_type=content_type)
    if kind == "doc":
        logger.warning("Legacy binary .doc not supported (skip): {}", url)
        return ""

    try:
        if kind == "pdf":
            text = _pdf_text(content)
        elif kind == "docx":
            text = _docx_text(content)
        elif kind == "html":
            text = _html_text(content)
        elif kind == "text":
            text = content.decode("utf-8", errors="ignore").strip()
        else:
            logger.warning("Unknown document kind for {} ({})", url, content_type)
            return ""
    except Exception as exc:  # noqa: BLE001 — a bad document must never raise to callers
        logger.warning("Text extraction failed for {} ({}): {}", url, kind, exc)
        return ""

    if len(text) > _MAX_DOC_CHARS:
        text = text[:_MAX_DOC_CHARS]
    return text
