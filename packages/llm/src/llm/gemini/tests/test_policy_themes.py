"""Unit tests for the controlled-vocabulary primary_theme taxonomy + extraction."""

from __future__ import annotations

from llm.gemini.browser_policy_analysis import _normalize_part1_analysis
from llm.gemini.policy_themes import (
    PRIMARY_THEMES,
    THEME_TO_COFOG,
    cofog_for_theme,
    is_valid_theme,
    normalize_primary_theme,
)


def test_vocabulary_is_18_labels_with_cofog():
    assert len(PRIMARY_THEMES) == 18
    assert set(PRIMARY_THEMES) == set(THEME_TO_COFOG)
    assert all(v.startswith("COFOG-") for v in THEME_TO_COFOG.values())


def test_normalize_exact_and_case_insensitive():
    assert normalize_primary_theme("Zoning and Land Use") == "Zoning and Land Use"
    assert normalize_primary_theme("  zoning and land use  ") == "Zoning and Land Use"
    assert normalize_primary_theme("PARKS AND RECREATION") == "Parks and Recreation"


def test_normalize_unknown_and_empty_returns_none():
    assert normalize_primary_theme(None) is None
    assert normalize_primary_theme("") is None
    assert normalize_primary_theme("Not A Real Theme") is None


def test_is_valid_and_cofog_lookup():
    assert is_valid_theme("Public Safety and Emergency Services")
    assert not is_valid_theme("nonsense")
    assert cofog_for_theme("public safety and emergency services") == "COFOG-03"
    assert cofog_for_theme("nope") is None


def test_extraction_normalizes_decision_theme_nullable():
    parsed = {
        "meeting": {"jurisdiction": "Test City"},
        "decisions": [
            {"decision_id": "D001", "primary_theme": "zoning and land use"},
            {"decision_id": "D002", "primary_theme": "bogus theme"},
            {"decision_id": "D003"},  # missing key -> untouched (back-compat)
        ],
        "uncontested_items": [],
    }
    out = _normalize_part1_analysis(parsed)
    by_id = {d["decision_id"]: d for d in out["decisions"]}
    assert by_id["D001"]["primary_theme"] == "Zoning and Land Use"
    assert by_id["D002"]["primary_theme"] is None
    assert "primary_theme" not in by_id["D003"]
