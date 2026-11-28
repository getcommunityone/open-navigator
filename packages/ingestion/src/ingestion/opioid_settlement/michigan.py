"""Load Michigan's opioid settlement spending (MDHHS dashboard workbook) into bronze.

    python -m ingestion.opioid_settlement.michigan
    python -m ingestion.opioid_settlement.michigan --dry-run

Source: Michigan Department of Health and Human Services, "Opioid Settlement: Settlement
Spending" (https://www.michigan.gov/opioids/opioidsettlements/settlement-spending),
dashboard workbook FY22 to FY24 (data as of 30 Jun 2024, per the file name). Published
by the state for public transparency; no key. One row per spend-plan line: fiscal year,
status, pillar, strategy, program, recipient organization, appropriation, spend plan,
expenditures and remaining plan.

This is state-level spending by MDHHS, not payments to individual cities or counties, so
rows attach to the state jurisdiction. The workbook is a pivot dashboard, so the loader
reads the "Detailed" sheet with the standard library (no spreadsheet dependency) and
addresses cells by reference because empty cells are omitted.
"""

from __future__ import annotations

import argparse
import io
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

import httpx
from loguru import logger
from sqlalchemy import text

from ..pgutil import get_engine

PAGE_URL = "https://www.michigan.gov/opioids/opioidsettlements/settlement-spending/prior-years-spending"
FILE_URL = (
    "https://www.michigan.gov/opioids/-/media/Project/Websites/opioids/Settlement-Media/"
    "Opioid-Dashboard-FY22-FY23-and-FY24-63024.xlsx"
)
REPORTED_AS_OF = "2024-06-30"
USER_AGENT = "open-navigator"
DATA_SOURCE = "Michigan DHHS Opioid Settlement dashboard workbook (FY22-FY24)"
TABLE = "bronze.bronze_opioid_settlement_spending"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

_DDL = [
    "CREATE SCHEMA IF NOT EXISTS bronze",
    f"""CREATE TABLE IF NOT EXISTS {TABLE} (
        state_code TEXT NOT NULL,
        source_row INTEGER NOT NULL,
        fiscal_year_label TEXT,
        status TEXT,
        pillar TEXT,
        strategy TEXT,
        program TEXT,
        recipient TEXT,
        appropriation TEXT,
        spend_plan TEXT,
        expenditures TEXT,
        remaining_plan TEXT,
        reported_as_of DATE,
        source_url TEXT,
        data_source TEXT,
        ingestion_date TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (state_code, source_row)
    )""",
]
_COLS = [
    "state_code", "source_row", "fiscal_year_label", "status", "pillar", "strategy", "program",
    "recipient", "appropriation", "spend_plan", "expenditures", "remaining_plan",
    "reported_as_of", "source_url", "data_source",
]
_UPSERT = text(
    f"INSERT INTO {TABLE} ({', '.join(_COLS)}) VALUES ({', '.join(':' + c for c in _COLS)}) "
    f"ON CONFLICT (state_code, source_row) DO UPDATE SET "
    + ", ".join(f"{c}=EXCLUDED.{c}" for c in _COLS[2:])
    + ", ingestion_date = NOW()"
)

# Detailed sheet columns (header row): B Status, C Pillar, D strategy, E Programs, F Vendor,
# G FY label, H Appropriation, I Current Spend Plan, J Expenditures, K Remaining Spend Plan.
_MAP = {
    "G": "fiscal_year_label", "B": "status", "C": "pillar", "D": "strategy", "E": "program",
    "F": "recipient", "H": "appropriation", "I": "spend_plan", "J": "expenditures", "K": "remaining_plan",
}


def parse_workbook(blob: bytes) -> list[dict[str, Any]]:
    """Rows of the 'Detailed' sheet as bronze dicts (header and total rows dropped)."""
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        shared = [
            "".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t"))
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)
        ]
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid = next(s.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                   for s in wb.iter(f"{{{NS['m']}}}sheet") if s.get("name") == "Detailed")
        target = next(r.get("Target") for r in rels if r.get("Id") == rid)
        sheet = ET.fromstring(z.read("xl/" + target.lstrip("/").removeprefix("xl/")))

    def cell_value(c: ET.Element) -> str | None:
        v = c.find("m:v", NS)
        if v is None or v.text is None:
            return None
        return shared[int(v.text)] if c.get("t") == "s" else v.text

    out: list[dict[str, Any]] = []
    for row in sheet.iter(f"{{{NS['m']}}}row"):
        n = int(row.get("r"))
        cells = {re.match(r"[A-Z]+", c.get("r")).group(): cell_value(c) for c in row.findall("m:c", NS)}
        if not cells.get("F") or not re.fullmatch(r"FY\d{2}", cells.get("G") or ""):
            continue  # header rows, or a total row with no recipient / fiscal year
        rec = {dst: (cells.get(col) or "").strip() or None for col, dst in _MAP.items()}
        rec.update(
            state_code="MI", source_row=n, reported_as_of=REPORTED_AS_OF,
            source_url=PAGE_URL, data_source=DATA_SOURCE,
        )
        out.append(rec)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Load Michigan opioid settlement spending")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)

    resp = httpx.get(FILE_URL, headers={"User-Agent": USER_AGENT}, timeout=90, follow_redirects=True)
    resp.raise_for_status()
    rows = parse_workbook(resp.content)
    logger.info("Parsed {:,} spend-plan lines", len(rows))
    if not a.dry_run:
        engine = get_engine()
        with engine.begin() as cx:
            for stmt in _DDL:
                cx.execute(text(stmt))
            cx.execute(_UPSERT, rows)
        logger.success("Loaded {:,} Michigan opioid settlement lines into {}", len(rows), TABLE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
