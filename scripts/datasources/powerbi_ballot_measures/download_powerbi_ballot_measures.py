#!/usr/bin/env python3
"""
Download ballot-measures table from a public Power BI report.

Approach
--------
Public Power BI reports (``app.powerbi.com/view?r=<token>``) fetch every
visual's data by POSTing to ``<cluster>/public/reports/querydata``. We
launch the report in Playwright, intercept those XHR responses, and parse
the Power BI DSR (DataShape Result) payloads into rows. This is far more
reliable than DOM-scraping virtualized tables of 9k+ rows.

After capture, the script:
  1. Saves every raw querydata response to ``data/cache/powerbi_ballot_measures/raw/``.
  2. Picks the response whose row count is closest to ``--expected-count``
     (default 9670 — the headline KPI on the dashboard).
  3. Writes the chosen response as a CSV next to the raw payloads.

Usage
-----
    python scripts/datasources/powerbi_ballot_measures/download_powerbi_ballot_measures.py \
        --url "https://app.powerbi.com/view?r=<token>" \
        --expected-count 9670

    # Re-parse already-captured raw payloads without re-scraping:
    python scripts/datasources/powerbi_ballot_measures/download_powerbi_ballot_measures.py \
        --parse-only --expected-count 9670
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

try:
    from playwright.async_api import async_playwright
except ImportError:  # pragma: no cover - playwright is a runtime dep
    logger.error("playwright is required. pip install playwright && playwright install chromium")
    sys.exit(2)


DEFAULT_URL = (
    "https://app.powerbi.com/view?r="
    "eyJrIjoiYjEwNDI2NTctZDFkMy00ZGM4LWFkMTItNTcwYTdkZmMxMGIxIiwidCI6IjM4MmZiOGIwLTRkYzMtNDEwNy04MGJkLTM1OTViMjQzMmZhZSIsImMiOjZ9"
)
_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = _ROOT / "data" / "cache" / "powerbi_ballot_measures"
RAW_DIR = CACHE_DIR / "raw"

QUERYDATA_PATH_RE = re.compile(r"/public/reports/querydata", re.IGNORECASE)


# ---------------------------------------------------------------------------
# DSR (DataShape Result) parsing
# ---------------------------------------------------------------------------
#
# Power BI's querydata response is a deeply nested object. A typical shape:
#
# {
#   "results": [
#     {
#       "result": {
#         "data": {
#           "descriptor": {"Select": [{"Name": "Table.Col", "Value": "Col"}, ...]},
#           "dsr": {
#             "DS": [
#               {
#                 "PH": [
#                   {"DM0": [
#                       {"C": [val0, val1, ...], "R": 0, "Ø": 4},
#                       ...
#                   ]}
#                 ],
#                 "ValueDicts": {"D0": ["str1", ...], ...}
#               }
#             ]
#           }
#         }
#       }
#     }
#   ]
# }
#
# Cells use bit-packing:
#   * "R" (Repeat)   — bit N set means "reuse column N's value from the previous row".
#   * "Ø" (Null)     — bit N set means "column N is null".
#   * Dictionary refs are resolved by checking each column's "DN" hint in
#     descriptor.Select[N].Variations or by looking up integer values in
#     ValueDicts when the column is dictionary-encoded.
#
# We implement a pragmatic decoder that handles the common case (table
# visuals with no nested groupings).


def _extract_columns(descriptor: dict[str, Any]) -> list[str]:
    """Return user-facing column names from the descriptor."""
    cols: list[str] = []
    for entry in descriptor.get("Select", []) or []:
        # Prefer the friendly "Value" alias, then "Name", then the bare expression.
        name = entry.get("Value") or entry.get("Name") or entry.get("Expr") or ""
        if isinstance(name, dict):
            name = name.get("Property") or json.dumps(name, sort_keys=True)
        cols.append(str(name))
    return cols


def _resolve_cell(raw: Any, col_idx: int, value_dicts: dict[str, list[Any]],
                  dict_keys: list[str | None]) -> Any:
    """Resolve a packed cell value, expanding dictionary references."""
    if raw is None:
        return None
    dict_key = dict_keys[col_idx] if col_idx < len(dict_keys) else None
    if dict_key and isinstance(raw, int):
        bucket = value_dicts.get(dict_key) or []
        if 0 <= raw < len(bucket):
            return bucket[raw]
    return raw


def _column_dict_keys(ds: dict[str, Any], n_cols: int) -> list[str | None]:
    """For each output column, return the ValueDicts key (e.g. ``"D0"``) or None.

    DSR encodes this in ``SH[0].DataShapes[0]`` or in ``ValueDicts`` keys whose
    column order mirrors ``descriptor.Select``. We use a best-effort heuristic:
    if there are exactly ``n_cols`` dict buckets ``D0..D{n-1}``, assume positional
    mapping. Otherwise return None for unmapped columns.
    """
    value_dicts = ds.get("ValueDicts") or {}
    keys = [f"D{i}" for i in range(n_cols)]
    return [k if k in value_dicts else None for k in keys]


def parse_dsr(payload: dict[str, Any]) -> list[tuple[list[str], list[list[Any]]]]:
    """Parse one querydata payload into ``[(columns, rows), ...]`` per result.

    Returns an empty list if the payload has no tabular DSR data.
    """
    out: list[tuple[list[str], list[list[Any]]]] = []
    for result in payload.get("results", []) or []:
        data = (result.get("result") or {}).get("data") or {}
        descriptor = data.get("descriptor") or {}
        dsr = data.get("dsr") or {}
        columns = _extract_columns(descriptor)
        if not columns:
            continue
        for ds in dsr.get("DS", []) or []:
            value_dicts = ds.get("ValueDicts") or {}
            dict_keys = _column_dict_keys(ds, len(columns))
            rows: list[list[Any]] = []
            prev_row: list[Any] = [None] * len(columns)
            for ph in ds.get("PH", []) or []:
                # Each PH (PrimaryHierarchy) carries one or more DM (DataModel) arrays.
                for dm_key, dm_rows in ph.items():
                    if not dm_key.startswith("DM"):
                        continue
                    for cell in dm_rows or []:
                        c = cell.get("C") or []
                        repeat_mask = cell.get("R", 0) or 0
                        null_mask = cell.get("Ø", 0) or 0
                        row: list[Any] = []
                        c_iter = iter(c)
                        for col_idx in range(len(columns)):
                            if null_mask & (1 << col_idx):
                                row.append(None)
                            elif repeat_mask & (1 << col_idx):
                                row.append(prev_row[col_idx])
                            else:
                                try:
                                    raw_val = next(c_iter)
                                except StopIteration:
                                    raw_val = None
                                row.append(_resolve_cell(raw_val, col_idx, value_dicts, dict_keys))
                        rows.append(row)
                        prev_row = row
            if rows:
                out.append((columns, rows))
    return out


# ---------------------------------------------------------------------------
# Playwright capture
# ---------------------------------------------------------------------------
async def _capture(url: str, raw_dir: Path, *, headless: bool, idle_seconds: float,
                   max_seconds: float) -> list[Path]:
    """Open the Power BI URL and persist every querydata response to ``raw_dir``."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    captured: list[Path] = []
    last_capture_at = [asyncio.get_event_loop().time()]
    counter = [0]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(viewport={"width": 1600, "height": 1000})
        page = await context.new_page()

        async def _on_response(response):
            if not QUERYDATA_PATH_RE.search(response.url):
                return
            try:
                body = await response.json()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Non-JSON querydata response from {}: {}", response.url, exc)
                return
            counter[0] += 1
            path = raw_dir / f"querydata_{counter[0]:04d}.json"
            path.write_text(json.dumps(body))
            captured.append(path)
            last_capture_at[0] = asyncio.get_event_loop().time()
            logger.info("Captured querydata #{} ({} bytes) → {}",
                        counter[0], path.stat().st_size, path.name)

        page.on("response", lambda r: asyncio.create_task(_on_response(r)))

        logger.info("Opening {}", url)
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)

        # Power BI lazy-loads the table on user interaction (scroll/hover). We
        # simulate scrolling on the page to coax it into paging through all rows.
        start = asyncio.get_event_loop().time()
        consecutive_idle = 0.0
        while True:
            now = asyncio.get_event_loop().time()
            if now - start > max_seconds:
                logger.warning("Hit max_seconds={}, stopping capture", max_seconds)
                break
            idle = now - last_capture_at[0]
            if idle >= idle_seconds and captured:
                logger.info("No new querydata for {:.1f}s — assuming complete", idle)
                break
            # Nudge the report: scroll page + send PageDown to focused visual.
            try:
                await page.mouse.wheel(0, 800)
                await page.keyboard.press("PageDown")
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(1.0)
            consecutive_idle = idle

        await context.close()
        await browser.close()

    logger.success("Captured {} querydata payloads → {}", len(captured), raw_dir)
    return captured


# ---------------------------------------------------------------------------
# Pick the best payload and write CSV
# ---------------------------------------------------------------------------
def _choose_best_parse(raw_dir: Path, expected_count: int) -> tuple[list[str], list[list[Any]], Path] | None:
    """Return ``(columns, rows, source_path)`` for the parse closest to expected_count."""
    best: tuple[int, list[str], list[list[Any]], Path] | None = None  # (delta, cols, rows, path)
    for path in sorted(raw_dir.glob("querydata_*.json")):
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        parses = parse_dsr(payload)
        for cols, rows in parses:
            n = len(rows)
            if n == 0:
                continue
            delta = abs(n - expected_count)
            logger.debug("{}: {} rows × {} cols (Δ={} vs expected {})",
                         path.name, n, len(cols), delta, expected_count)
            if best is None or delta < best[0] or (delta == best[0] and n > len(best[2])):
                best = (delta, cols, rows, path)
    if best is None:
        return None
    _, cols, rows, path = best
    return cols, rows, path


def _write_csv(columns: list[str], rows: list[list[Any]], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(["" if v is None else v for v in row])
    logger.success("Wrote {} rows × {} cols → {}", len(rows), len(columns), csv_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=DEFAULT_URL, help="Public Power BI ``/view?r=...`` URL")
    parser.add_argument("--expected-count", type=int, default=9670,
                        help="Expected ballot-measure row count (KPI on dashboard).")
    parser.add_argument("--parse-only", action="store_true",
                        help="Skip scraping; reparse existing raw/*.json into CSV.")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--headed", dest="headless", action="store_false",
                        help="Run with a visible browser (useful for debugging).")
    parser.add_argument("--idle-seconds", type=float, default=8.0,
                        help="Stop capture after this many seconds without a new querydata response.")
    parser.add_argument("--max-seconds", type=float, default=180.0,
                        help="Hard cap on total capture time.")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output CSV path (default: data/cache/powerbi_ballot_measures/ballot_measures_<ts>.csv).")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if not args.parse_only:
        asyncio.run(_capture(
            args.url, RAW_DIR,
            headless=args.headless,
            idle_seconds=args.idle_seconds,
            max_seconds=args.max_seconds,
        ))

    best = _choose_best_parse(RAW_DIR, args.expected_count)
    if best is None:
        logger.error("No parseable querydata responses found in {}", RAW_DIR)
        return 1
    cols, rows, src = best

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    csv_path = args.out or CACHE_DIR / f"ballot_measures_{ts}.csv"
    _write_csv(cols, rows, csv_path)

    delta = len(rows) - args.expected_count
    status = "OK" if delta == 0 else ("UNDER" if delta < 0 else "OVER")
    logger.info("Count check [{}]: scraped={:,}, expected={:,}, Δ={:+}",
                status, len(rows), args.expected_count, delta)
    if delta != 0:
        logger.warning("Row count does not match expected — Power BI may have paged the "
                       "data into multiple querydata responses. Inspect {} or re-run "
                       "with --headed and a larger --max-seconds.", src.name)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
