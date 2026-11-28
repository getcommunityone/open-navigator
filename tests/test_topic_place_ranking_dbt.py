"""topic_place_ranking (#1437): counting each speaker once, shrinkage, the evidence minimum and size bands.

The mart's arithmetic lives in dbt (CLAUDE.md: transformations in dbt). Its dbt unit test
(``_schema_topic_place_ranking.yml``, fixture rows only, no warehouse data) is the executable spec; this pytest checks
the spec says what the decision record promises and, where dbt and the warehouse are reachable, runs it.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

DBT = Path(__file__).resolve().parents[1] / "dbt_project"
SCHEMA = DBT / "models" / "marts" / "_schema_topic_place_ranking.yml"


def _unit() -> dict:
    [ut] = yaml.safe_load(SCHEMA.read_text())["unit_tests"]
    return ut


def _expected(jid: str) -> dict:
    return next(r for r in _unit()["expect"]["rows"] if r["jurisdiction_id"] == jid)


def test_each_speaker_counts_once_on_their_majority_side() -> None:
    sides = _unit()["given"][0]["rows"]
    ann = [r for r in sides if r["meeting_speaker_id"].startswith("ann-")]
    assert len(ann) == 3  # Ann B. spoke against at three meetings ...
    j1 = _expected("J1")
    assert (j1["speakers_for"], j1["speakers_against"], j1["speakers_split"]) == (3, 7, 1)  # ... and counts once


def test_officials_minors_old_and_unsided_readings_are_not_counted() -> None:
    j1 = _expected("J1")
    assert j1["officials_side"] == "for" and j1["officials_for"] == 1
    assert j1["speakers_for"] == 3  # the official, the possible minor and the not-sure reading are not residents' sides
    assert not any(r["jurisdiction_id"] == "J3" for r in _unit()["expect"]["rows"])  # school district left out


def test_shrinkage_toward_national_rate() -> None:
    v = _unit()["overrides"]["vars"]
    k = v["ranking_prior_weight"]
    national = 7 / 19
    for jid, f, a in (("J1", 3, 7), ("J2", 9, 0)):
        e = _expected(jid)
        assert e["national_against_share"] == round(national, 4)
        assert e["shrunk_against_share"] == round((a + k * national) / (f + a + k), 4)


def test_evidence_minimum_and_bands() -> None:
    v = _unit()["overrides"]["vars"]
    assert (v["ranking_min_speakers"], v["ranking_min_meetings"], v["ranking_window_months"]) == (10, 2, 24)
    j1, j2 = _expected("J1"), _expected("J2")
    assert j1["is_ranked"] and j1["band_rank"] == 1 and j1["size_band"] == "large"
    assert not j2["is_ranked"] and j2["band_rank"] is None and j2["size_band"] == "small"  # 9 speakers < 10


def test_dbt_project_vars_match_the_decision_record() -> None:
    v = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert (v["ranking_window_months"], v["ranking_min_speakers"], v["ranking_min_meetings"],
            v["ranking_prior_weight"]) == (24, 10, 2, 10)


@pytest.mark.skipif(not os.environ.get("RUN_DBT_UNIT_TESTS") or not shutil.which("dbt"),
                    reason="set RUN_DBT_UNIT_TESTS=1 with dbt and the warehouse reachable")
def test_dbt_unit_test_passes() -> None:
    out = subprocess.run(["dbt", "test", "--select", "topic_place_ranking,test_type:unit"], cwd=DBT,
                         capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stdout[-3000:]
