"""#823: counts and error drill-downs on the Load tab.

The loader writes its counts and every file it did not load; the job runner records counts per step
(and dbt's per-model results); the API serves them filtered and paged. Test data is constructed here.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import time
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- the loader
loader = pytest.importorskip("llm.enrichment.load_analysis_cache_to_bronze")


def _put(cache: Path, name: str, analysis: str | None = '{"meeting": {}}', meta: dict | None = None) -> None:
    folder = cache / "AL" / "municipality" / "x_1" / "chan"
    (folder / "02_analysis").mkdir(parents=True, exist_ok=True)
    (folder / "04_runs").mkdir(parents=True, exist_ok=True)
    if analysis is not None:
        (folder / "02_analysis" / f"{name}.json").write_text(analysis)
    if meta is not None:
        (folder / "04_runs" / f"{name}.meta.json").write_text(json.dumps(meta))


@pytest.fixture()
def cache(tmp_path, monkeypatch):
    root = tmp_path / "cache"
    _put(root, "good", meta={"video_id": "vidGOOD0001"})
    _put(root, "empty", analysis="", meta={"video_id": "vidEMPTY001"})
    _put(root, "nometa")
    _put(root, "novideo", meta={"title": "t"})
    _put(root, "noevent", meta={"video_id": "vidNOEVENT1"})
    _put(root, "othertier", meta={"video_id": "vidOTHER001", "files": {"analysis_json": "a/othertier_full.json"}})

    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(loader.psycopg2, "connect", lambda *_a, **_k: _Conn())
    monkeypatch.setattr(loader, "build_video_to_event_map", lambda _c: {"vidGOOD0001": 7})
    return root


def test_loader_lists_every_file_it_did_not_load(cache):
    items: list[dict] = []
    stats = loader.run(cache_root=cache, database_url="x", dry_run=True, gate=False, items=items)
    assert stats["discovered"] == 6 and stats["loaded"] == 1
    assert (stats["errors"], stats["errors_unreadable"], stats["errors_upsert"]) == (1, 1, 0)
    by_file = {Path(i["file"]).name: i for i in items}
    assert set(by_file) == {"empty.json", "nometa.json", "novideo.json", "noevent.json", "othertier.json"}
    assert (by_file["empty.json"]["outcome"], by_file["empty.json"]["reason"]) == ("error", "unreadable")
    assert by_file["empty.json"]["detail"]  # the parser's message, so the reader can see why
    assert by_file["nometa.json"]["reason"] == "no_meta"
    assert by_file["novideo.json"]["reason"] == "no_video"
    assert (by_file["noevent.json"]["reason"], by_file["noevent.json"]["video_id"]) == ("no_event", "vidNOEVENT1")
    assert by_file["othertier.json"]["reason"] == "meta_mismatch"
    assert all(i["outcome"] == "skipped" for n, i in by_file.items() if n != "empty.json")
    assert by_file["empty.json"]["file"].startswith("AL/")  # path under the cache root, not absolute
    # every file is accounted for: loaded + listed = discovered
    assert stats["loaded"] + len(items) == stats["discovered"]


def test_loader_without_an_items_list_behaves_as_before(cache):
    stats = loader.run(cache_root=cache, database_url="x", dry_run=True, gate=False)
    assert stats["loaded"] == 1 and stats["skipped_no_meta"] == 1


def test_result_json_shape(tmp_path):
    out = tmp_path / "deep" / "r.json"
    loader.write_result_json(out, {"discovered": 2, "loaded": 1}, [{"file": "a", "outcome": "error"}], dry_run=True)
    data = json.loads(out.read_text())
    assert data["schema"] == 1 and data["kind"] == "load-analysis" and data["dry_run"] is True
    assert data["counts"] == {"discovered": 2, "loaded": 1} and data["items"][0]["file"] == "a"
    assert not list(out.parent.glob("*.tmp"))


@pytest.mark.parametrize(
    ("stats", "code"),
    [
        ({"errors": 1, "errors_unreadable": 1, "errors_upsert": 0}, 0),  # one bad input file must not stop dbt
        ({"errors": 1, "errors_unreadable": 0, "errors_upsert": 1}, 1),  # a failed write is a failed run
        ({"errors": 0, "errors_unreadable": 0, "errors_upsert": 0}, 0),
    ],
)
def test_exit_code_fails_only_on_database_errors(monkeypatch, tmp_path, stats, code):
    seen = {}

    def fake_run(**kw):
        seen.update(kw)
        kw["items"].append({"file": "x.json", "outcome": "error", "reason": "unreadable"})
        return stats

    out = tmp_path / "r.json"
    monkeypatch.setattr(loader, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["loader", "--result-json", str(out)])
    assert loader.main() == code
    assert json.loads(out.read_text())["items"][0]["file"] == "x.json"
    assert isinstance(seen["items"], list)


# --------------------------------------------------------------------------- the job runner
def _orchestrator():
    spec = importlib.util.spec_from_file_location(
        "run_deployment_823", ROOT / "packages" / "hosting" / "src" / "hosting" / "deploy" / "run_deployment.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def orch():
    return _orchestrator()


def test_load_step_gets_a_result_path_and_other_steps_do_not(orch, tmp_path):
    path = orch.result_path_for(tmp_path, "load_1", "load-analysis")
    assert path == tmp_path / "load_1_load-analysis.result.json"
    argv = orch._step_argv("load-analysis", path)
    assert argv[-2:] == ["--result-json", str(path)]
    assert "--result-json" not in orch._step_argv("load-analysis")  # no path, no dangling flag
    assert "--result-json" not in orch._step_argv("dbt-gold", path)


def test_summarize_load_counts(orch):
    counts = {"discovered": 10, "loaded": 4, "loaded_light": 4, "skipped_no_event": 3, "skipped_low_keep_score": 2,
              "skipped_other_tier": 9, "errors": 1, "errors_unreadable": 1, "unchecked_no_bronze_row": 5}
    assert orch.summarize_load_counts(counts) == {"read": 10, "loaded": 4, "skipped": 5, "errors": 1}
    assert orch.summarize_load_counts({}) == {"read": 0, "loaded": 0, "skipped": 0, "errors": 0}


def _run_results(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"results": [
        {"unique_id": "model.p.event_meeting", "status": "success"},
        {"unique_id": "model.p.event_decision", "status": "error", "message": "column x does not exist"},
        {"unique_id": "model.p.decision_speakers", "status": "skipped"},
    ]}))


def test_dbt_results_are_read_per_model(orch, tmp_path):
    rr = tmp_path / "run_results.json"
    _run_results(rr)
    result = orch.dbt_result_from_run_results(rr, time.time() - 5)
    assert result["kind"] == "dbt"
    assert result["counts"] == {"models": 3, "success": 1, "error": 1, "skipped": 1}
    assert [(i["file"], i["outcome"], i["reason"]) for i in result["items"]] == [
        ("model.p.event_decision", "error", "error"), ("model.p.decision_speakers", "skipped", "skipped")]
    assert result["items"][0]["detail"] == "column x does not exist"


def test_stale_or_missing_dbt_results_are_not_reported(orch, tmp_path):
    rr = tmp_path / "run_results.json"
    assert orch.dbt_result_from_run_results(rr, time.time()) is None
    _run_results(rr)
    old = time.time() - 3600
    os.utime(rr, (old, old))
    assert orch.dbt_result_from_run_results(rr, time.time()) is None  # left by an earlier dbt run
    rr.write_text("not json")
    assert orch.dbt_result_from_run_results(rr, 0) is None


def test_collect_step_result(orch, tmp_path):
    root = tmp_path
    load_result = tmp_path / "j_load-analysis.result.json"
    assert orch.collect_step_result("load-analysis", load_result, root, time.time()) is None  # no file, no counts
    load_result.write_text(json.dumps({"counts": {"discovered": 3, "loaded": 2, "skipped_no_meta": 1, "errors": 0}}))
    assert orch.collect_step_result("load-analysis", load_result, root, time.time()) == {
        "read": 3, "loaded": 2, "skipped": 1, "errors": 0}
    _run_results(root / "dbt_project" / "target" / "run_results.json")
    dbt_result = tmp_path / "j_dbt-gold.result.json"
    assert orch.collect_step_result("dbt-gold", dbt_result, root, time.time() - 5)["error"] == 1
    assert json.loads(dbt_result.read_text())["kind"] == "dbt"  # written for the drill-down


def _job(orch, monkeypatch, tmp_path, steps):
    monkeypatch.setattr(orch, "_repo_root", lambda: tmp_path)
    status = tmp_path / "status"
    status.mkdir(exist_ok=True)
    return orch.DeploymentJob(job_id="load_x", steps=steps, dry_run=False, status_dir=status, log_dir=status)


def test_a_step_starts_with_no_counts(orch, monkeypatch, tmp_path):
    job = _job(orch, monkeypatch, tmp_path, ["load-analysis", "dbt-gold"])
    assert all(s["counts"] is None and s["result"] is None for s in job.to_dict()["steps"])


def test_a_real_run_records_counts_even_when_the_step_fails(orch, monkeypatch, tmp_path):
    """Run the runner end to end with a stand-in loader that writes a result file and exits 1."""
    script = (
        "import json,sys;"
        "json.dump({'counts': {'discovered': 5, 'loaded': 3, 'skipped_no_event': 1, 'errors': 1}, 'items': []},"
        " open(sys.argv[sys.argv.index('--result-json') + 1], 'w'));"
        "sys.exit(1)"
    )
    monkeypatch.setitem(orch.STEP_DEFS["load-analysis"], "argv", ["{python}", "-c", script, "--result-json", "{result}"])
    job = _job(orch, monkeypatch, tmp_path, ["load-analysis", "dbt-gold"])
    assert orch._Orchestrator(job).run() == 1
    load, dbt = json.loads(job.status_path.read_text())["steps"]
    assert load["status"] == "failed" and load["exit_code"] == 1
    assert load["counts"] == {"read": 5, "loaded": 3, "skipped": 1, "errors": 1}
    assert load["result"] == "status/load_x_load-analysis.result.json"
    assert dbt["status"] == "skipped" and dbt["counts"] is None


# --------------------------------------------------------------------------- the API
pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi import FastAPI


@pytest.fixture()
def get(monkeypatch, tmp_path):
    auth = types.ModuleType("api.auth")
    auth.require_admin = lambda: None
    monkeypatch.setitem(sys.modules, "api", types.ModuleType("api"))
    monkeypatch.setitem(sys.modules, "api.auth", auth)
    spec = importlib.util.spec_from_file_location("deployments_823", ROOT / "api" / "routes" / "deployments.py")
    m = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, m)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "_status_dir", lambda: tmp_path)
    app = FastAPI()
    app.include_router(m.router, prefix="/api")

    items = (
        [{"file": f"AL/a/no_event_{i}.json", "video_id": f"vid{i:08d}", "tier": "light", "outcome": "skipped",
          "reason": "no_event", "detail": None} for i in range(60)]
        + [{"file": "AL/a/empty.json", "video_id": None, "tier": "light", "outcome": "error", "reason": "unreadable",
            "detail": "Expecting value: line 1 column 1 (char 0)"},
           {"file": "GA/b/odd.json", "video_id": "vidODD00001", "tier": "full", "outcome": "skipped",
            "reason": "brand_new_reason", "detail": None}]
    )
    (tmp_path / "load_1_load-analysis.result.json").write_text(json.dumps({
        "schema": 1, "kind": "load-analysis", "dry_run": False,
        "counts": {"discovered": 100, "loaded": 38, "errors": 1, "flag": True, "note": "x"}, "items": items}))

    def _get(path: str, **params):
        async def go():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
                return await c.get(path, params=params)

        return asyncio.run(go())

    return _get


def test_result_endpoint_counts_and_reasons(get):
    body = get("/api/deployments/load_1/result", step="load-analysis").json()
    assert body["available"] is True and body["kind"] == "load-analysis"
    assert body["counts"] == {"discovered": 100, "loaded": 38, "errors": 1}  # only numbers
    assert body["total"] == 62 and len(body["rows"]) == 50
    reasons = body["reasons"]
    assert [(r["reason"], r["outcome"], r["count"]) for r in reasons] == [
        ("unreadable", "error", 1), ("no_event", "skipped", 60), ("brand_new_reason", "skipped", 1)]  # errors first
    assert reasons[0]["label"] == "File could not be read" and reasons[0]["advice"]
    assert reasons[2]["label"] == "brand new reason"  # an unknown reason still shows, under its own name
    assert sum(r["count"] for r in reasons) == body["total"]


def test_result_endpoint_filters_and_pages(get):
    assert get("/api/deployments/load_1/result", step="load-analysis", outcome="error").json()["total"] == 1
    by_reason = get("/api/deployments/load_1/result", step="load-analysis", reason="no_event", limit=25, offset=50).json()
    assert by_reason["total"] == 60 and len(by_reason["rows"]) == 10
    assert len(by_reason["reasons"]) == 3  # reason counts always cover the whole run
    assert get("/api/deployments/load_1/result", step="load-analysis", q="EXPECTING value").json()["total"] == 1
    assert get("/api/deployments/load_1/result", step="load-analysis", q="vidODD").json()["rows"][0]["tier"] == "full"
    assert get("/api/deployments/load_1/result", step="load-analysis", q="zzz").json()["total"] == 0


def test_result_endpoint_says_when_nothing_was_recorded(get):
    body = get("/api/deployments/load_1/result", step="dbt-gold").json()
    assert body["available"] is False and body["counts"] == {} and body["rows"] == []
    assert get("/api/deployments/older_run/result", step="load-analysis").json()["available"] is False


def test_result_endpoint_rejects_bad_input(get):
    assert get("/api/deployments/load_1/result", step="nope").status_code == 400
    assert get("/api/deployments/a..b/result", step="load-analysis").status_code == 400
    assert get("/api/deployments/load_1/result", step="load-analysis", limit=0).status_code == 422
