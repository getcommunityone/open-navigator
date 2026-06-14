#!/usr/bin/env python3
"""Convert every jurisdiction's main home page to a PDF snapshot.

Reads ``public.jurisdictions`` for jurisdictions that have a ``website_url`` and
renders each home page to PDF with headless Chromium (Playwright). PDFs land in
the usual per-jurisdiction cache hierarchy::

    data/cache/wikipedia/{ST}/{segment}/{jurisdiction_id}/homepage.pdf

where ``segment`` is ``state`` | ``county`` | ``municipality`` | ``school`` |
``township`` (derived from ``jurisdiction_type``) and ``jurisdiction_id`` is the
canonical ``{place_slug}_{geoid}`` folder name. A sidecar ``homepage.meta.json``
records the source URL, final URL, HTTP status, byte size and render timestamp.

Usage::

    # all jurisdictions in Alabama (first 25), skip ones already rendered
    python -m scrapers.homepage_pdf.scrape --states AL --limit 25

    # specific jurisdictions, re-render even if a PDF exists
    python -m scrapers.homepage_pdf.scrape --jurisdiction-ids anniston_0101852 --overwrite

    # the whole country (long-running) at 4 concurrent tabs
    python -m scrapers.homepage_pdf.scrape --concurrency 4

Requires Chromium: ``.venv/bin/python -m playwright install chromium`` (and on
WSL/Ubuntu often ``sudo .venv/bin/python -m playwright install-deps``). Set
``HOMEPAGE_PDF_CHROMIUM_EXECUTABLE`` / ``HOMEPAGE_PDF_CHANNEL=chrome`` to use a
system Chrome instead of bundled Chromium.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from loguru import logger

# Output root: data/cache/wikipedia at the repo root, overridable via env / CLI.
DEFAULT_OUTPUT_ROOT = Path(
    os.getenv("HOMEPAGE_PDF_OUTPUT_ROOT") or "data/cache/wikipedia"
)

# jurisdiction_type (public.jurisdictions) -> filesystem segment under {ST}/.
# Mirrors the cache layout used by scraped_meetings / ballotpedia caches.
_TYPE_TO_SEGMENT = {
    "state": "state",
    "county": "county",
    "parish": "county",
    "borough": "county",
    "city": "municipality",
    "town": "municipality",
    "village": "municipality",
    "township": "township",
    "municipality": "municipality",
    "cdp": "municipality",
    "school_district": "school",
    "school": "school",
}

_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


# --------------------------------------------------------------------------- #
# Path helpers
# --------------------------------------------------------------------------- #
def cache_segment(jurisdiction_type: str | None) -> str:
    """Filesystem segment under ``{state}/`` for a jurisdiction type."""
    raw = (jurisdiction_type or "").strip().lower()
    return _TYPE_TO_SEGMENT.get(raw, "municipality")


def safe_folder(jurisdiction_id: str) -> str:
    """Canonical ``{place_slug}_{geoid}`` folder, defensively sanitized."""
    folder = _SAFE_SEGMENT_RE.sub("_", (jurisdiction_id or "").strip()).strip("_")
    return folder[:200] or "unknown"


def jurisdiction_pdf_path(output_root: Path, target: "Target") -> Path:
    """``{root}/{ST}/{segment}/{jurisdiction_id}/homepage.pdf``."""
    st = (target.state_code or "XX").strip().upper() or "XX"
    return (
        Path(output_root)
        / st
        / cache_segment(target.jurisdiction_type)
        / safe_folder(target.jurisdiction_id)
        / "homepage.pdf"
    )


# --------------------------------------------------------------------------- #
# Target discovery
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Target:
    jurisdiction_id: str
    state_code: str | None
    jurisdiction_type: str | None
    name: str | None
    website_url: str


def _database_url() -> str | None:
    return (
        os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or "postgresql://postgres@localhost:5433/open_navigator"
    )


def _normalize_url(url: str) -> str | None:
    u = (url or "").strip()
    if not u:
        return None
    if not re.match(r"^https?://", u, re.IGNORECASE):
        u = "https://" + u
    return u


def load_targets(
    *,
    states: list[str] | None,
    types: list[str] | None,
    jurisdiction_ids: list[str] | None,
    limit: int | None,
) -> list[Target]:
    """Query ``public.jurisdictions`` for jurisdictions with a home page."""
    import psycopg2  # local import: heavy, only needed for discovery
    from dotenv import load_dotenv

    load_dotenv()
    url = _database_url()
    if not url:
        raise RuntimeError("No database URL (set NEON_DATABASE_URL_DEV / DATABASE_URL)")

    where = ["website_url IS NOT NULL", "btrim(website_url) <> ''"]
    params: list[Any] = []
    if states:
        where.append("upper(state_code) = ANY(%s)")
        params.append([s.strip().upper() for s in states])
    if types:
        where.append("lower(jurisdiction_type) = ANY(%s)")
        params.append([t.strip().lower() for t in types])
    if jurisdiction_ids:
        where.append("jurisdiction_id = ANY(%s)")
        params.append([j.strip() for j in jurisdiction_ids])

    sql = (
        "SELECT jurisdiction_id, state_code, jurisdiction_type, name, website_url "
        "FROM public.jurisdictions "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY state_code, jurisdiction_type, jurisdiction_id"
    )
    if limit:
        sql += " LIMIT %s"
        params.append(limit)

    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    targets: list[Target] = []
    for jid, state_code, jtype, name, website_url in rows:
        norm = _normalize_url(website_url)
        if not norm:
            continue
        targets.append(
            Target(
                jurisdiction_id=jid,
                state_code=state_code,
                jurisdiction_type=jtype,
                name=name,
                website_url=norm,
            )
        )
    return targets


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _launch_options() -> dict[str, Any]:
    headless_env = (os.getenv("HOMEPAGE_PDF_HEADLESS") or "true").strip().lower()
    headless = headless_env not in ("0", "false", "no", "off")
    opts: dict[str, Any] = {
        "headless": headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    }
    channel = (os.getenv("HOMEPAGE_PDF_CHANNEL") or "").strip()
    if channel:
        opts["channel"] = channel
    executable = (os.getenv("HOMEPAGE_PDF_CHROMIUM_EXECUTABLE") or "").strip()
    if executable:
        opts["executable_path"] = executable
    return opts


async def _render_one(
    browser: Any,
    target: Target,
    *,
    output_root: Path,
    overwrite: bool,
    timeout_ms: int,
) -> dict[str, Any]:
    pdf_path = jurisdiction_pdf_path(output_root, target)
    result: dict[str, Any] = {
        "jurisdiction_id": target.jurisdiction_id,
        "url": target.website_url,
        "path": str(pdf_path),
        "status": "pending",
    }
    if pdf_path.exists() and not overwrite:
        result["status"] = "skipped"
        return result

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    context = await browser.new_context(
        ignore_https_errors=True,
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36 OpenNavigatorBot/1.0"
        ),
    )
    page = await context.new_page()
    try:
        # Navigate on `domcontentloaded` (reliable) rather than `networkidle`:
        # many gov sites poll/beacon forever and never go idle, which would
        # otherwise hard-fail an otherwise-rendered page.
        response = await page.goto(
            target.website_url, wait_until="domcontentloaded", timeout=timeout_ms
        )
        # Best-effort: let late content settle, but never let a never-idle
        # page (analytics, chat widgets) fail the whole render.
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:  # noqa: BLE001
            pass
        try:
            await page.wait_for_timeout(800)
        except Exception:  # noqa: BLE001
            pass
        await page.emulate_media(media="screen")
        await page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "0.4in", "bottom": "0.4in", "left": "0.4in", "right": "0.4in"},
        )
        size = pdf_path.stat().st_size if pdf_path.exists() else 0
        result.update(
            status="ok",
            http_status=response.status if response else None,
            final_url=page.url,
            bytes=size,
        )
        _write_meta(pdf_path, target, result)
    except Exception as exc:  # noqa: BLE001
        result.update(status="error", error=str(exc)[:300])
        # Remove a truncated/zero-byte PDF so a re-run retries cleanly.
        if pdf_path.exists() and pdf_path.stat().st_size == 0:
            pdf_path.unlink(missing_ok=True)
    finally:
        await context.close()
    return result


def _write_meta(pdf_path: Path, target: Target, result: dict[str, Any]) -> None:
    meta = {
        "jurisdiction_id": target.jurisdiction_id,
        "name": target.name,
        "state_code": target.state_code,
        "jurisdiction_type": target.jurisdiction_type,
        "source_url": target.website_url,
        "final_url": result.get("final_url"),
        "http_status": result.get("http_status"),
        "bytes": result.get("bytes"),
    }
    pdf_path.with_name("homepage.meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


async def render_all(
    targets: Iterable[Target],
    *,
    output_root: Path,
    overwrite: bool,
    concurrency: int,
    timeout_ms: int,
) -> list[dict[str, Any]]:
    from playwright.async_api import async_playwright

    targets = list(targets)
    sem = asyncio.Semaphore(max(1, concurrency))
    results: list[dict[str, Any]] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**_launch_options())
        try:

            async def _bounded(t: Target) -> dict[str, Any]:
                async with sem:
                    res = await _render_one(
                        browser,
                        t,
                        output_root=output_root,
                        overwrite=overwrite,
                        timeout_ms=timeout_ms,
                    )
                tag = res["status"].upper()
                logger.info(
                    "[{}] {} {} -> {}",
                    tag,
                    t.jurisdiction_id,
                    t.website_url,
                    res.get("error") or res.get("path"),
                )
                return res

            results = await asyncio.gather(*(_bounded(t) for t in targets))
        finally:
            await browser.close()
    return results


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _split_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [v.strip() for v in value.split(",") if v.strip()]
    return items or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--states", help="Comma-separated USPS codes (e.g. AL,GA)")
    parser.add_argument(
        "--types",
        help="Comma-separated jurisdiction_type filter (e.g. city,county)",
    )
    parser.add_argument(
        "--jurisdiction-ids",
        help="Comma-separated jurisdiction_id values to render",
    )
    parser.add_argument(
        "--limit", type=int, help="Cap the number of jurisdictions rendered"
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=f"Cache root (default: {DEFAULT_OUTPUT_ROOT})",
    )
    parser.add_argument(
        "--concurrency", type=int, default=3, help="Concurrent Chromium tabs"
    )
    parser.add_argument(
        "--timeout", type=int, default=45, help="Per-page navigation timeout (seconds)"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-render even when a homepage.pdf already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the jurisdictions that would be rendered, then exit",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    targets = load_targets(
        states=_split_csv(args.states),
        types=_split_csv(args.types),
        jurisdiction_ids=_split_csv(args.jurisdiction_ids),
        limit=args.limit,
    )
    logger.info(
        "Discovered {} jurisdiction(s) with a home page -> {}",
        len(targets),
        args.output_root,
    )
    if not targets:
        logger.warning("Nothing to render.")
        return 0

    if args.dry_run:
        for t in targets:
            logger.info(
                "{} | {} | {} -> {}",
                t.jurisdiction_id,
                t.state_code,
                t.website_url,
                jurisdiction_pdf_path(args.output_root, t),
            )
        return 0

    results = asyncio.run(
        render_all(
            targets,
            output_root=args.output_root,
            overwrite=args.overwrite,
            concurrency=args.concurrency,
            timeout_ms=args.timeout * 1000,
        )
    )

    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = [r for r in results if r["status"] == "error"]
    logger.success(
        "Rendered {} PDF(s), {} skipped, {} error(s)", ok, skipped, len(errors)
    )
    for r in errors[:20]:
        logger.warning("  FAILED {} -> {}", r["jurisdiction_id"], r.get("error"))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
