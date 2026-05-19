"""
Optional post-crawl hook: run Ollama structured extraction on ``page_*.readable.txt`` files.

Enable during jurisdiction meeting crawls::

  SCRAPED_MEETINGS_OLLAMA_EXTRACT=1
  SCRAPED_MEETINGS_OLLAMA_EXTRACT_MAX_PAGES=5   # per run, directory pages only
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from loguru import logger

from scripts.scraping.html_to_markdown import readable_txt_to_markdown
from scripts.scraping.ollama_extract import extract_structured_ollama, ollama_model


def ollama_extract_enabled() -> bool:
    return (os.getenv("SCRAPED_MEETINGS_OLLAMA_EXTRACT") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def ollama_extract_max_pages() -> int:
    try:
        return max(0, int(os.getenv("SCRAPED_MEETINGS_OLLAMA_EXTRACT_MAX_PAGES", "3") or "3"))
    except ValueError:
        return 3


def maybe_extract_after_readable_txt(
    readable_path: Path,
    *,
    page_url: str,
    crawl_root: Path,
) -> Optional[Path]:
    """
    If enabled, write ``page_*.ollama.json`` next to the readable sidecar.

    Returns the JSON path when written.
    """
    if not ollama_extract_enabled():
        return None
    max_pages = ollama_extract_max_pages()
    if max_pages <= 0:
        return None

    counter_file = crawl_root / "_ollama_extract_count.txt"
    try:
        n = int(counter_file.read_text().strip() or "0")
    except (OSError, ValueError):
        n = 0
    if n >= max_pages:
        return None

    out_path = readable_path.with_suffix(".ollama.json")
    try:
        md = readable_txt_to_markdown(
            readable_path.read_text(encoding="utf-8", errors="replace")
        )
        result = extract_structured_ollama(
            md,
            extra_system=(
                f"Page URL: {page_url}. "
                "Focus on the main public meeting date in the page header if multiple dates appear."
            ),
        )
        payload = {
            "source_url": page_url,
            "readable_txt": str(readable_path),
            "model": ollama_model(),
            "extraction": result.model_dump(),
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        counter_file.write_text(str(n + 1), encoding="utf-8")
        logger.info(f"Ollama extraction → {out_path}")
        return out_path
    except Exception as exc:
        logger.warning(f"Ollama sidecar skipped for {readable_path}: {exc}")
        return None
