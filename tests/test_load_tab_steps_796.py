"""#796: the "2 Load" tab. Load steps run in the same orchestrator as deploy steps, in their own group."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ORCH = ROOT / "packages" / "hosting" / "src" / "hosting" / "deploy" / "run_deployment.py"


def _load_orchestrator():
    spec = importlib.util.spec_from_file_location("run_deployment_under_test", _ORCH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def orch():
    return _load_orchestrator()


def test_load_steps_exist_in_the_load_group(orch):
    assert orch.step_group("load-analysis") == "load"
    assert orch.step_group("dbt-gold") == "load"
    assert orch.step_group("database") == "deploy"
    assert orch.step_group("web") == "deploy"


def test_load_steps_target_the_local_warehouse_not_prod(orch):
    assert orch.STEP_DEFS["load-analysis"]["target"] == "local-warehouse"
    assert orch.STEP_DEFS["dbt-gold"]["target"] == "local-warehouse"


def test_defaults_per_group(orch):
    assert orch.DEFAULT_STEPS_BY_GROUP["load"] == ["load-analysis", "dbt-gold"]
    assert orch.DEFAULT_STEPS_BY_GROUP["deploy"] == ["database"]
    assert orch.DEFAULT_STEPS == ["database"]  # unchanged for existing callers


def test_available_steps_carry_their_group(orch):
    by_key = {s["key"]: s["group"] for s in orch.available_steps()}
    assert by_key == {
        "load-analysis": "load",
        "dbt-gold": "load",
        "database": "deploy",
        "web": "deploy",
    }


def test_job_group(orch):
    assert orch.job_group(["load-analysis", "dbt-gold"]) == "load"
    assert orch.job_group(["dbt-gold"]) == "load"
    assert orch.job_group(["database"]) == "deploy"
    assert orch.job_group([]) == "deploy"


def test_load_step_argv_uses_the_loader_and_dbt_run(orch, monkeypatch):
    monkeypatch.setenv("DBT_BIN", "/opt/dbt/bin/dbt")
    load = orch._step_argv("load-analysis")
    assert load[0] == sys.executable
    assert load[1:] == ["-m", "llm.enrichment.load_analysis_cache_to_bronze"]
    gold = orch._step_argv("dbt-gold")
    assert gold[:2] == ["/opt/dbt/bin/dbt", "run"]
    assert "int_preferred_event_analysis+" in gold and "bronze_decisions_from_ai+" in gold
    assert "{dbt}" not in " ".join(gold)


def test_dbt_bin_prefers_the_dbt_environment(orch, monkeypatch, tmp_path):
    monkeypatch.delenv("DBT_BIN", raising=False)
    fake_root = tmp_path
    dbt = fake_root / "dbt_project" / ".venv_dbt" / "bin" / "dbt"
    dbt.parent.mkdir(parents=True)
    dbt.write_text("#!/bin/sh\n")
    monkeypatch.setattr(orch, "_repo_root", lambda: fake_root)
    assert orch.dbt_bin() == str(dbt)


def test_dbt_bin_falls_back_to_path(orch, monkeypatch, tmp_path):
    monkeypatch.delenv("DBT_BIN", raising=False)
    monkeypatch.setattr(orch, "_repo_root", lambda: tmp_path)
    assert orch.dbt_bin() == "dbt"


def test_child_env_can_import_the_llm_package(orch):
    env = orch._child_env()
    assert str(ROOT / "packages" / "llm" / "src") in env["PYTHONPATH"].split(":")


def test_a_job_cannot_mix_load_and_deploy_steps(orch, capsys):
    with pytest.raises(SystemExit):
        orch.main(["--job-id", "t", "--steps", "load-analysis,database", "--dry-run"])
    assert "cannot run in the same job" in capsys.readouterr().err


def test_dry_run_of_a_load_job_runs_nothing(orch, tmp_path, monkeypatch):
    monkeypatch.setattr(orch, "_repo_root", lambda: tmp_path)  # logs must sit under the repo root
    rc = orch.main(
        ["--job-id", "load_test", "--steps", "load-analysis,dbt-gold", "--dry-run", "--status-dir", str(tmp_path)]
    )
    assert rc == 0
    import json

    job = json.loads((tmp_path / "load_test.json").read_text())
    assert job["group"] == "load" and job["label"].startswith("Load analysis")
    assert [s["status"] for s in job["steps"]] == ["completed", "completed"]
    log = (tmp_path / "load_test_load-analysis.log").read_text()
    assert "[dry-run] no command executed" in log
