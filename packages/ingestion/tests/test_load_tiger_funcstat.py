"""FUNCSTAT CSVs for counties / school districts (#356)."""
from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.census import load_tiger_funcstat as mod


def test_cache_paths_point_at_tiger_funcstat_dir():
    assert mod.CACHE.name == "tiger_funcstat"
    assert mod.COUNTY_CSV.name == "county_funcstat_2024.csv"
    assert mod.SCHOOL_CSV.name == "school_district_funcstat_2024.csv"


def test_county_csv_has_independent_cities_as_f(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Baltimore city county-equivalent is FUNCSTAT F so it is not double-counted."""
    csv = tmp_path / "county_funcstat_2024.csv"
    csv.write_text("GEOID,FUNCSTAT,LSAD,CLASSFP\n24510,F,25,C7\n01001,A,06,H1\n", encoding="utf-8")
    monkeypatch.setattr(mod, "COUNTY_CSV", csv)
    import pandas as pd

    df = pd.read_csv(csv, dtype=str)
    assert df.set_index("GEOID").loc["24510", "FUNCSTAT"] == "F"
    assert df.set_index("GEOID").loc["01001", "FUNCSTAT"] == "A"
