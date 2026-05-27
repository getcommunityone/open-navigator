"""Unit tests for the HUD ZIP-county crosswalk pipeline port."""
from __future__ import annotations

import asyncio
import sys
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

_HUD_DIR = Path(__file__).resolve().parents[1] / "scripts" / "datasources" / "hud"
sys.path.insert(0, str(_HUD_DIR))

import zip_county_pipeline as mod  # noqa: E402
from zip_county_pipeline import (  # noqa: E402
    HudZipCountyPipeline,
    ZipCountyRow,
    _safe_decimal,
    _safe_str,
    find_latest_xlsx,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _make_xlsx(path: Path, data_rows: list[tuple]) -> None:
    """Write a minimal HUD-shaped xlsx. Cols 0-3 are strings, 4-7 numeric."""
    STR_COLS = {0, 1, 2, 3}
    strings = ["ZIP", "COUNTY", "CITY", "STATE", "RES", "BUS", "OTH", "TOT"]

    def sidx(s: str) -> int:
        if s not in strings:
            strings.append(s)
        return strings.index(s)

    header = "".join(f'<c t="s"><v>{i}</v></c>' for i in range(8))
    body = [f"<row>{header}</row>"]
    for rec in data_rows:
        cells = []
        for i, val in enumerate(rec):
            if val is None:
                cells.append("<c></c>")
            elif i in STR_COLS:
                cells.append(f'<c t="s"><v>{sidx(val)}</v></c>')
            else:
                cells.append(f"<c><v>{val}</v></c>")
        body.append(f'<row>{"".join(cells)}</row>')

    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    sheet = f'<worksheet {ns}><sheetData>{"".join(body)}</sheetData></worksheet>'
    sst = f'<sst {ns}>' + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/sharedStrings.xml", sst)
        z.writestr("xl/worksheets/sheet1.xml", sheet)


def test_safe_decimal():
    assert _safe_decimal("0.5") == Decimal("0.5")
    assert _safe_decimal(None) is None
    assert _safe_decimal("   ") is None
    assert _safe_decimal("not-a-number") is None


def test_safe_str():
    assert _safe_str(None) is None
    assert _safe_str("   ") is None
    assert _safe_str("  hello  ") == "hello"
    assert _safe_str("abcdefgh", 5) == "abcde"


def test_schema_accepts_valid_row():
    row = ZipCountyRow.model_validate({
        "source": "hud_zip_county",
        "source_version": "ZIP_COUNTY_122025",
        "natural_key": "00601:72001",
        "zip": "00601",
        "county": "72001",
        "usps_zip_pref_city": "ADJUNTAS",
        "usps_zip_pref_state": "PR",
        "res_ratio": Decimal("0.5"),
        "bus_ratio": None,
        "oth_ratio": None,
        "tot_ratio": Decimal("0.6"),
    })
    assert row.zip == "00601"
    assert row.res_ratio == Decimal("0.5")
    assert row.bus_ratio is None


def test_schema_rejects_overlong_zip_and_state():
    base = {
        "source": "hud_zip_county",
        "source_version": "v",
        "natural_key": "x",
        "zip": "00601",
        "county": "72001",
    }
    with pytest.raises(Exception):
        ZipCountyRow.model_validate({**base, "zip": "006010"})  # 6 chars
    with pytest.raises(Exception):
        ZipCountyRow.model_validate({**base, "usps_zip_pref_state": "PRX"})  # 3 chars


def test_pipeline_metadata():
    p = HudZipCountyPipeline()
    assert p.source == "hud_zip_county"
    assert p.batch_size == 2_000
    assert p.row_schema is ZipCountyRow


def test_find_latest_xlsx_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_latest_xlsx()


def test_extract_yields_validated_envelope_rows(tmp_path):
    xlsx = tmp_path / "ZIP_COUNTY_122025.xlsx"
    _make_xlsx(xlsx, [
        ("00601", "72001", "ADJUNTAS", "PR", "0.5", "0.1", "0.0", "0.6"),
        ("00602", "72003", "AGUADA", "PR", "0.9", "0.05", "0.05", "1.0"),
        (None, "72005", "X", "PR", "0.1", "0.1", "0.1", "0.3"),  # missing zip -> skipped
    ])
    p = HudZipCountyPipeline(xlsx_path=xlsx)

    async def collect():
        out = []
        async for raw in p.extract(_ctx()):
            row = p.validate(raw)
            assert row is not None, f"rejected: {raw}"
            out.append(row)
        return out

    rows = asyncio.run(collect())
    assert len(rows) == 2  # third row skipped (missing zip)
    first = rows[0]
    assert first.zip == "00601"
    assert first.county == "72001"
    assert first.usps_zip_pref_state == "PR"
    assert first.res_ratio == Decimal("0.5")
    assert first.natural_key == "00601:72001"
    assert first.source == "hud_zip_county"
    assert first.source_version == "ZIP_COUNTY_122025"


def test_extract_respects_limit(tmp_path):
    xlsx = tmp_path / "ZIP_COUNTY_122025.xlsx"
    _make_xlsx(xlsx, [
        ("00601", "72001", "ADJUNTAS", "PR", "0.5", "0.1", "0.0", "0.6"),
        ("00602", "72003", "AGUADA", "PR", "0.9", "0.05", "0.05", "1.0"),
    ])
    p = HudZipCountyPipeline(xlsx_path=xlsx, limit=1)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    assert len(asyncio.run(collect())) == 1
