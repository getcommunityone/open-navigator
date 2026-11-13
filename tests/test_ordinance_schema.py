"""CORE-1.1.1 (#237): the ordinance and amendment schema, with CHECK constraints.

dbt can't run in CI here (no warehouse), so these tests pin the contract in the model files:
keys, the status vocabulary, the link back to the source document, the status map that
never guesses, and the guard that keeps dbt runs passing before the ingest lands.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DBT = ROOT / "dbt_project"
MARTS_SCHEMA = DBT / "models" / "marts" / "_schema_ordinances.yml"
STATUS_MAP = DBT / "seeds" / "ordinance_status_map.csv"
STAGING_DIR = DBT / "models" / "staging" / "ordinances"
SOURCES = DBT / "models" / "staging" / "_staging.yml"

VOCABULARY = {"introduced", "awaiting_signature", "signed", "vetoed", "failed"}
AMBIGUOUS = {"adopted", "passed", "approved", "enacted by council"}


def _models() -> dict[str, dict]:
    doc = yaml.safe_load(MARTS_SCHEMA.read_text())
    return {m["name"]: m for m in doc["models"]}


def _column(model: dict, name: str) -> dict:
    return next(c for c in model["columns"] if c["name"] == name)


def _constraint_types(column: dict) -> set[str]:
    return {c["type"] for c in column.get("constraints", [])}


def test_both_marts_enforce_their_contract_and_type_every_column():
    models = _models()
    for name in ("ordinances", "ordinance_amendments"):
        model = models[name]
        assert model["config"]["contract"]["enforced"] is True
        assert model["config"]["materialized"] == "table"
        for column in model["columns"]:
            assert column.get("data_type"), f"{name}.{column['name']} has no data_type"
            assert column.get("description"), f"{name}.{column['name']} has no description"


def test_ordinances_keys():
    model = _models()["ordinances"]
    assert {"primary_key", "not_null"} <= _constraint_types(_column(model, "ordinance_uid"))
    for name in ("jurisdiction_id", "platform_code", "platform_ordinance_id", "identifier", "source_url"):
        assert "not_null" in _constraint_types(_column(model, name)), name
    fks = [c for c in model.get("constraints", []) if c["type"] == "foreign_key"]
    assert any(fk["columns"] == ["jurisdiction_id"] and "jurisdictions" in fk["to"] for fk in fks)


def test_status_check_allows_only_the_vocabulary_or_null():
    status = _column(_models()["ordinances"], "status")
    checks = [c for c in status.get("constraints", []) if c["type"] == "check"]
    assert len(checks) == 1
    expression = checks[0]["expression"]
    assert set(re.findall(r"'([a-z_]+)'", expression)) == VOCABULARY
    assert "is null" in expression.lower()
    assert "not_null" not in _constraint_types(status)  # null = not mapped, never guessed


def test_amendments_keys():
    model = _models()["ordinance_amendments"]
    assert {"primary_key", "not_null"} <= _constraint_types(_column(model, "amendment_uid"))
    for name in ("ordinance_uid", "source_url"):
        assert "not_null" in _constraint_types(_column(model, name)), name
    fks = [c for c in model.get("constraints", []) if c["type"] == "foreign_key"]
    assert any(fk["columns"] == ["ordinance_uid"] and "ordinances" in fk["to"] for fk in fks)


def test_status_map_never_guesses():
    with STATUS_MAP.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows, "the map is empty"
    keys = [row["raw_status_key"] for row in rows]
    assert len(keys) == len(set(keys)), "a raw status is mapped twice"
    for row in rows:
        key, status = row["raw_status_key"], row["status"]
        assert key == key.strip().lower(), f"{key!r} is not lowercased and trimmed"
        assert status in VOCABULARY, f"{key!r} maps to {status!r}, outside the vocabulary"
        assert key not in AMBIGUOUS, f"{key!r} is ambiguous and must stay unmapped"
    assert {row["status"] for row in rows} == VOCABULARY  # every status is reachable


def test_staging_reads_bronze_only_when_it_exists():
    for model, table in (("stg_ordinances", "bronze_ordinances"),
                         ("stg_ordinance_amendments", "bronze_ordinance_amendments")):
        sql = (STAGING_DIR / f"{model}.sql").read_text()
        call = f"source('bronze', '{table}')"
        assert call in sql, f"{model} doesn't declare its source"
        # The source() call comes before the guard, so dbt records the dependency at parse time.
        assert sql.index(call) < sql.index("{% if"), f"{model} declares its source inside the guard"
        assert "adapter.get_relation" in sql
        assert re.search(r"where\s+false", sql, re.IGNORECASE), f"{model} has no empty branch"


def test_bronze_sources_are_declared():
    doc = yaml.safe_load(SOURCES.read_text())
    bronze = next(s for s in doc["sources"] if s["name"] == "bronze")
    tables = {t["name"] for t in bronze["tables"]}
    assert {"bronze_ordinances", "bronze_ordinance_amendments"} <= tables
