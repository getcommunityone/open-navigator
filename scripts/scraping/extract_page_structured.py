#!/usr/bin/env python3
"""
Fetch a government URL (or read crawl HTML / readable.txt) and extract structured JSON via Ollama.

Pipeline:
  URL → httpx/Playwright HTML → Markdown → Ollama (Gemma) → Pydantic JSON

Examples::

  .venv/bin/python scripts/scraping/extract_page_structured.py \\
    --url https://www.tuscco.com/commission-agenda-minutes/

  .venv/bin/python scripts/scraping/extract_page_structured.py \\
    --readable-txt data/cache/scraped_meetings/AL/county/.../page_001.readable.txt

  .venv/bin/python scripts/scraping/extract_page_structured.py --check-ollama
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

from scripts.scraping.html_to_markdown import html_to_markdown, readable_txt_to_markdown  # noqa: E402
from scripts.scraping.ollama_extract import (  # noqa: E402
    check_ollama_ready,
    extract_structured_ollama,
    ollama_model,
)


async def _fetch_html(url: str, timeout: float) -> str:
    import httpx

    import os

    verify_env = (os.getenv("SCRAPED_MEETINGS_HTTP_VERIFY") or "true").strip().lower()
    verify = verify_env not in ("0", "false", "no", "off")

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        verify=verify,
        headers={"User-Agent": "OpenNavigator-llm-scrape/1.0"},
    ) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            if (os.getenv("SCRAPED_MEETINGS_PLAYWRIGHT_FALLBACK") or "true").strip().lower() in (
                "0",
                "false",
                "no",
                "off",
            ):
                raise
            logger.warning(f"httpx failed ({exc}); trying Playwright…")
            from scripts.discovery.comprehensive_discovery_pipeline_jurisdiction import (
                fetch_html_via_playwright,
            )

            html, _status, _reason = await fetch_html_via_playwright(url)
            if not html:
                raise RuntimeError(f"Playwright returned no HTML for {url} ({_reason})")
            return html


def main() -> int:
    ap = argparse.ArgumentParser(description="Structured LLM extraction from a web page")
    ap.add_argument("--url", help="Page URL to fetch")
    ap.add_argument("--html-file", type=Path, help="Local HTML snapshot")
    ap.add_argument("--readable-txt", type=Path, help="Local page_*.readable.txt from crawl")
    ap.add_argument("--out", type=Path, help="Write JSON here (default: stdout)")
    ap.add_argument("--markdown-out", type=Path, help="Optional: save cleaned Markdown")
    ap.add_argument("--model", default="", help=f"Ollama model (default env / {ollama_model()})")
    ap.add_argument("--check-ollama", action="store_true", help="Verify Ollama + model and exit")
    ap.add_argument("--timeout", type=float, default=60.0, help="HTTP fetch timeout seconds")
    args = ap.parse_args()

    if args.check_ollama:
        try:
            info = check_ollama_ready(model=args.model or None)
        except RuntimeError as exc:
            logger.error(str(exc))
            return 2
        print(json.dumps(info, indent=2))
        return 0

    if args.readable_txt:
        md = readable_txt_to_markdown(args.readable_txt.read_text(encoding="utf-8", errors="replace"))
        source = str(args.readable_txt)
    elif args.html_file:
        html = args.html_file.read_text(encoding="utf-8", errors="replace")
        md = html_to_markdown(html, source_url=str(args.html_file))
        source = str(args.html_file)
    elif args.url:
        html = asyncio.run(_fetch_html(args.url, args.timeout))
        md = html_to_markdown(html, source_url=args.url)
        source = args.url
    else:
        ap.error("Pass --url, --html-file, or --readable-txt (or --check-ollama)")

    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(md, encoding="utf-8")
        logger.info(f"Wrote Markdown → {args.markdown_out}")

    logger.info(f"Extracting with Ollama model {args.model or ollama_model()} ({len(md):,} chars)…")
    try:
        result = extract_structured_ollama(md, model=args.model or None)
    except RuntimeError as exc:
        logger.error(str(exc))
        return 2
    payload = {
        "source": source,
        "model": args.model or ollama_model(),
        "extraction": result.model_dump(),
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        logger.success(f"Wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
