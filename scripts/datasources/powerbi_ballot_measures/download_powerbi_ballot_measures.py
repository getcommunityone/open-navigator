#!/usr/bin/env python3
"""
Download ballot-measures table from a public Power BI report.

Approach
--------
Public Power BI reports (``app.powerbi.com/view?r=<token>``) fetch every
visual's data by POSTing to ``<cluster>/public/reports/querydata``. We
launch the report in Playwright, capture the main table's query template
(headers + POST body), then page through the full dataset with
``Window.RestartTokens`` (500 rows per request). Each response is Power BI
DSR (DataShape Result) JSON — not DOM scraping.

After capture, the script:
  1. Saves every raw querydata response to ``data/cache/ncls/raw/``.
  2. Merges all table pages into one CSV (deduped by row content).
  3. Asserts the row count matches ``--expected-count`` (default 9670).

Usage
-----
    python scripts/datasources/powerbi_ballot_measures/download_powerbi_ballot_measures.py \
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
CACHE_DIR = _ROOT / "data" / "cache" / "ncls"
RAW_DIR = CACHE_DIR / "raw"

QUERYDATA_PATH_RE = re.compile(r"/public/reports/querydata", re.IGNORECASE)
TABLE_QUERY_MARKER = "All Years Table.StateName"
MIN_TABLE_COLUMNS = 10
PAGE_SIZE = 500


# ---------------------------------------------------------------------------
# DSR (DataShape Result) parsing
# ---------------------------------------------------------------------------


def _friendly_column_name(entry: dict[str, Any]) -> str:
    """Prefer NativeReferenceName, then strip ``Entity.`` from Name."""
    native = entry.get("NativeReferenceName")
    if native:
        return str(native)
    name = entry.get("Name") or entry.get("Value") or ""
    if isinstance(name, str) and "." in name:
        return name.rsplit(".", 1)[-1]
    return str(name)


def _extract_columns(descriptor: dict[str, Any]) -> list[str]:
    cols: list[str] = []
    for entry in descriptor.get("Select", []) or []:
        cols.append(_friendly_column_name(entry))
    return cols


def _resolve_cell(raw: Any, col_idx: int, value_dicts: dict[str, list[Any]],
                  dict_keys: list[str | None]) -> Any:
    if raw is None:
        return None
    dict_key = dict_keys[col_idx] if col_idx < len(dict_keys) else None
    if dict_key and isinstance(raw, int):
        bucket = value_dicts.get(dict_key) or []
        if 0 <= raw < len(bucket):
            return bucket[raw]
    return raw


def _column_dict_keys(ds: dict[str, Any], n_cols: int) -> list[str | None]:
    value_dicts = ds.get("ValueDicts") or {}
    keys = [f"D{i}" for i in range(n_cols)]
    return [k if k in value_dicts else None for k in keys]


def parse_dsr(payload: dict[str, Any]) -> list[tuple[list[str], list[list[Any]]]]:
    """Parse one querydata payload into ``[(columns, rows), ...]`` per result."""
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


def _is_table_payload(payload: dict[str, Any]) -> bool:
    return TABLE_QUERY_MARKER in json.dumps(payload)


def _best_table_parse(payload: dict[str, Any]) -> tuple[list[str], list[list[Any]]] | None:
    best: tuple[list[str], list[list[Any]]] | None = None
    for cols, rows in parse_dsr(payload):
        if len(cols) < MIN_TABLE_COLUMNS or not rows:
            continue
        if best is None or len(rows) > len(best[1]):
            best = (cols, rows)
    return best


def _sql_literal(value: Any) -> str:
    if value is None or value == "":
        return "''"
    if isinstance(value, float):
        return f"{value}D"
    if isinstance(value, int):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def _restart_literal(value: Any) -> str:
    """Power BI ``RestartTokens`` use bare ``null`` for missing values, not ``''``."""
    if value is None or value == "":
        return "null"
    if isinstance(value, float):
        return f"{value}D"
    if isinstance(value, int) and not isinstance(value, bool):
        return _sql_literal(str(value))
    if isinstance(value, str) and re.match(r"^-?\d*\.\d", value):
        try:
            return f"{float(value)}D"
        except ValueError:
            pass
    return _sql_literal(value)


def _ballot_restart_token(row: list[Any]) -> str:
    """Last RestartToken column — ballot label (e.g. ``Proposition 119``)."""
    if len(row) > 9 and row[9] not in (None, ""):
        return _restart_literal(row[9])
    if len(row) > 10 and row[10] not in (None, ""):
        return _restart_literal(row[10])
    return "null"


def restart_tokens_from_row(row: list[Any]) -> list[list[str]]:
    """Build ``RestartTokens`` for the next 500-row window (11 value columns)."""
    if len(row) < 8:
        raise ValueError(f"row too short for RestartTokens: {row!r}")
    pct = row[8] if len(row) > 8 else None
    tokens = [
        _restart_literal(row[0]),
        _restart_literal(row[1]),
        _restart_literal(row[2]),
        _restart_literal(row[3]),
        _restart_literal(row[4]),
        _restart_literal(row[5]),
        _restart_literal(row[6]),
        _restart_literal(row[7]),
        _restart_literal(pct),
        "''",
        _ballot_restart_token(row),
    ]
    return [tokens]


# ---------------------------------------------------------------------------
# Playwright: capture session + paginate querydata XHR
# ---------------------------------------------------------------------------
async def _paginate_table(
    context,
    url: str,
    headers: dict[str, str],
    base_body: dict[str, Any],
    raw_dir: Path,
    *,
    expected_count: int,
    max_pages: int,
    resume: bool,
) -> tuple[list[str], list[list[Any]]]:
    """Fetch all table pages via RestartTokens; save each raw JSON response."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    merged: dict[tuple[str, ...], list[Any]] = {}
    columns: list[str] = []
    restart: list[list[str]] | None = None
    start_page = 0

    if resume:
        existing = sorted(raw_dir.glob("table_page_*.json"))
        for path in existing:
            payload = json.loads(path.read_text())
            parsed = _best_table_parse(payload)
            if not parsed:
                continue
            columns, rows = parsed
            for row in rows:
                merged[tuple("" if v is None else str(v) for v in row)] = row
        if existing:
            start_page = len(existing)
            last_path = existing[-1]
            last_parsed = _best_table_parse(json.loads(last_path.read_text()))
            if last_parsed:
                restart = restart_tokens_from_row(last_parsed[1][-1])
                logger.info(
                    "Resuming from page {} (loaded {:,} unique rows from {})",
                    start_page, len(merged), last_path.name,
                )

    for page_num in range(start_page, max_pages):
        if page_num > 0:
            await asyncio.sleep(0.75)
        body = json.loads(json.dumps(base_body))
        cmd = body["queries"][0]["Query"]["Commands"][0]["SemanticQueryDataShapeCommand"]
        window: dict[str, Any] = {"Count": PAGE_SIZE}
        if restart:
            window["RestartTokens"] = restart
        cmd["Binding"]["DataReduction"]["Primary"]["Window"] = window

        payload: dict[str, Any] | None = None
        parsed: tuple[list[str], list[list[Any]]] | None = None
        for attempt in range(5):
            try:
                response = await context.request.post(
                    url, data=json.dumps(body), headers=headers, timeout=120_000,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Page {} attempt {}: request failed: {}", page_num, attempt + 1, exc)
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            await asyncio.sleep(0.5 * (2 ** attempt))
            if response.status != 200:
                text = await response.text()
                raise RuntimeError(f"querydata page {page_num} failed: HTTP {response.status}: {text[:300]}")
            payload = await response.json()
            parsed = _best_table_parse(payload)
            if parsed:
                break
            logger.debug("Page {} attempt {}: empty DSR, retrying", page_num, attempt + 1)
        raw_path = raw_dir / f"table_page_{page_num + 1:04d}.json"
        raw_path.write_text(json.dumps(payload))
        if not parsed:
            logger.warning("Page {}: empty or unparseable response — stopping pagination", page_num)
            break
        columns, rows = parsed
        new = 0
        for row in rows:
            key = tuple("" if v is None else str(v) for v in row)
            if key not in merged:
                merged[key] = row
                new += 1
        logger.info(
            "Page {:>2}: batch={:,} new={:,} total={:,}",
            page_num, len(rows), new, len(merged),
        )
        if len(rows) < PAGE_SIZE:
            break
        if new == 0:
            logger.warning(
                "Page {}: batch had no new rows (overlap) — advancing RestartTokens anyway",
                page_num,
            )
        if len(merged) >= expected_count:
            logger.info("Reached expected row count ({:,}) — stopping pagination", expected_count)
            break
        try:
            restart = restart_tokens_from_row(rows[-1])
        except ValueError as exc:
            logger.warning("Cannot build RestartTokens from last row: {}", exc)
            break

    return columns, list(merged.values())


async def _capture_and_download(
    url: str,
    raw_dir: Path,
    *,
    headless: bool,
    expected_count: int,
    max_pages: int,
    resume: bool,
) -> tuple[list[str], list[list[Any]]]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(viewport={"width": 1600, "height": 1200})
        page = await context.new_page()

        # Patch: _wait_for_table_request uses page.goto internally — refactor
        holder: dict[str, Any] = {}

        async def _on_request(request):
            if request.method != "POST" or not QUERYDATA_PATH_RE.search(request.url):
                return
            body = request.post_data_json
            if not isinstance(body, dict) or TABLE_QUERY_MARKER not in json.dumps(body):
                return
            if "table" not in holder:
                holder["table"] = (request.url, dict(request.headers), body)
                logger.info("Captured table querydata template")

        page.on("request", lambda r: asyncio.create_task(_on_request(r)))
        logger.info("Opening {}", url)
        await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        start = asyncio.get_event_loop().time()
        while "table" not in holder:
            if asyncio.get_event_loop().time() - start > 90:
                raise TimeoutError("Timed out waiting for ballot-measures table querydata request")
            await page.mouse.wheel(0, 600)
            await page.wait_for_timeout(400)

        query_url, headers, base_body = holder["table"]
        columns, rows = await _paginate_table(
            context, query_url, headers, base_body, raw_dir,
            expected_count=expected_count, max_pages=max_pages, resume=resume,
        )
        await context.close()
        await browser.close()
    return columns, rows


# ---------------------------------------------------------------------------
# Parse-only merge (legacy raw/querydata_*.json captures)
# ---------------------------------------------------------------------------
def _merge_table_parses(raw_dir: Path) -> tuple[list[str], list[list[Any]]]:
    merged: dict[tuple[str, ...], list[Any]] = {}
    columns: list[str] = []
    for path in sorted(raw_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if not _is_table_payload(payload):
            continue
        parsed = _best_table_parse(payload)
        if not parsed:
            continue
        cols, rows = parsed
        if len(cols) > len(columns):
            columns = cols
        for row in rows:
            merged[tuple("" if v is None else str(v) for v in row)] = row
    return columns, list(merged.values())


def _write_csv(columns: list[str], rows: list[list[Any]], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(["" if v is None else v for v in row])
    logger.success("Wrote {:,} rows × {} cols → {}", len(rows), len(columns), csv_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=DEFAULT_URL, help="Public Power BI ``/view?r=...`` URL")
    parser.add_argument("--expected-count", type=int, default=9670,
                        help="Expected ballot-measure row count (KPI on dashboard).")
    parser.add_argument("--parse-only", action="store_true",
                        help="Skip scraping; merge existing raw/*.json into CSV.")
    parser.add_argument("--resume", action="store_true",
                        help="Continue pagination from existing raw/table_page_*.json files.")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--headed", dest="headless", action="store_false",
                        help="Run with a visible browser (useful for debugging).")
    parser.add_argument("--max-pages", type=int, default=25,
                        help="Safety cap on RestartTokens pagination (500 rows/page; 25 ≈ 12.5k rows).")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output CSV path (default: data/cache/ncls/ballot_measures_<ts>.csv).")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if args.parse_only:
        columns, rows = _merge_table_parses(RAW_DIR)
    else:
        columns, rows = asyncio.run(_capture_and_download(
            args.url,
            RAW_DIR,
            headless=args.headless,
            expected_count=args.expected_count,
            max_pages=args.max_pages,
            resume=args.resume,
        ))

    if not rows:
        logger.error("No table rows parsed")
        return 1

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    csv_path = args.out or CACHE_DIR / f"ballot_measures_{ts}.csv"
    _write_csv(columns, rows, csv_path)
    logger.info("Output directory: {}", CACHE_DIR.resolve())
    logger.info("Raw querydata pages: {}", RAW_DIR.resolve())

    delta = len(rows) - args.expected_count
    tolerance = max(50, int(args.expected_count * 0.05))
    status = "OK" if abs(delta) <= tolerance else ("UNDER" if delta < 0 else "OVER")
    logger.info(
        "Count check [{}]: scraped={:,}, expected={:,}, Δ={:+} (tolerance ±{:,})",
        status, len(rows), args.expected_count, delta, tolerance,
    )
    if abs(delta) > tolerance:
        logger.warning(
            "Row count outside dashboard KPI tolerance — inspect raw payloads in {} "
            "or re-run with --resume.",
            RAW_DIR,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
