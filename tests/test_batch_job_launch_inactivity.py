"""Launch inactivity / VPN warning helpers for the batch-jobs dashboard (#750)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import api.routes.batch_jobs as bj


def test_run_all_argv_chains_discover_then_shell(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(bj, "_repo_root", lambda: tmp_path)
    disc = tmp_path / "packages/scrapers/src/scrapers/youtube/load_missing_county_channels.py"
    disc.parent.mkdir(parents=True)
    disc.write_text("# stub\n", encoding="utf-8")
    shell = tmp_path / "packages/scrapers/scripts/youtube_run_priority_states_last_n.sh"
    shell.parent.mkdir(parents=True)
    shell.write_text("#!/bin/bash\n", encoding="utf-8")
    argv, env = bj._build_launch_argv(
        "all",
        states=["WI", "AL"],
        cohort="data_centers",
        n=10,
        parallel=4,
    )
    assert argv[:2] == ["bash", "-c"]
    chain = argv[2]
    assert "load_missing_county_channels.py" in chain
    assert "--states WI,AL" in chain
    assert "--cohort data_centers" in chain
    assert "youtube_run_priority_states_last_n.sh" in chain
    assert 'echo "=== Discover' in chain
    assert env.get("COHORT") == "data_centers"
    assert env.get("STATES") == "WI,AL"


def test_vpn_down_regex_matches_surfshark_lines() -> None:
    assert bj._VPN_DOWN_RE.search(
        "Discovery failed for Ellis County: Surfshark is off: connect it, then re-run."
    )
    assert bj._VPN_DOWN_RE.search("VpnRequiredError: no VPN tunnel route")
    assert not bj._VPN_DOWN_RE.search("vpn_guard: VPN up via eth3")


def test_launch_warn_seconds_env(monkeypatch) -> None:
    monkeypatch.setenv("BATCH_JOB_LAUNCH_WARN_SECONDS", "120")
    assert bj._launch_warn_seconds() == 120.0
    monkeypatch.setenv("BATCH_JOB_LAUNCH_WARN_SECONDS", "bad")
    assert bj._launch_warn_seconds() == float(bj._LAUNCH_WARN_SECONDS_DEFAULT)


def test_launch_activity_iso_ignores_unrelated_freshest_for_discover() -> None:
    started = "2026-11-22T20:00:00+00:00"
    meta = {"step": "discover", "started_at": started}
    # Fresher analyze stamp must not hide a hung discover launch.
    freshest = "2026-11-22T21:30:00+00:00"
    assert bj._launch_activity_iso(meta, freshest) == started


def test_launch_operator_signals_warns_after_inactivity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BATCH_JOB_LAUNCH_WARN_SECONDS", "60")
    monkeypatch.setattr(bj, "_repo_root", lambda: tmp_path)
    log_dir = tmp_path / "data" / "cache" / "batch_jobs"
    log_dir.mkdir(parents=True)
    stale = datetime.now(timezone.utc) - timedelta(minutes=20)
    log_path = log_dir / "launch_discover_test.log"
    log_path.write_text(
        f"{stale.strftime('%Y-%m-%d %H:%M:%S')} | INFO | Discovering YouTube channels for Adams, WI\n",
        encoding="utf-8",
    )
    # Pin mtime in case timestamp parse fails on some platforms.
    import os

    os.utime(log_path, (stale.timestamp(), stale.timestamp()))

    started = (datetime.now(timezone.utc) - timedelta(minutes=25)).isoformat()
    running = [{"step": "discover", "started_at": started, "pid": 1}]
    signals = bj._launch_operator_signals(freshest="", running=running, stalled=[])
    assert signals["vpn_down"] is False
    assert signals["inactive_seconds"] is not None
    assert signals["inactive_seconds"] >= 60
    assert "no launch-log activity" in signals["warning"]
    assert "discover" in signals["warning"]


def test_launch_operator_signals_vpn_down_from_log(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BATCH_JOB_LAUNCH_WARN_SECONDS", "3600")
    monkeypatch.setattr(bj, "_repo_root", lambda: tmp_path)
    log_dir = tmp_path / "data" / "cache" / "batch_jobs"
    log_dir.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    log_path = log_dir / "launch_discover_vpn.log"
    log_path.write_text(
        f"{now.strftime('%Y-%m-%d %H:%M:%S')} | WARNING | Discovery failed for "
        f"Ellis County: Surfshark is off: connect it, then re-run.\n",
        encoding="utf-8",
    )
    started = now.isoformat()
    running = [{"step": "discover", "started_at": started, "pid": 1}]
    signals = bj._launch_operator_signals(freshest="", running=running, stalled=[])
    assert signals["vpn_down"] is True
    assert "Surfshark" in signals["warning"]


def test_orphan_vpn_warning_after_process_exits(monkeypatch, tmp_path: Path) -> None:
    """After Discover aborts on VpnRequiredError, PID is gone but log still warns."""
    monkeypatch.setattr(bj, "_repo_root", lambda: tmp_path)
    log_dir = tmp_path / "data" / "cache" / "batch_jobs"
    log_dir.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    (log_dir / "launch_discover_dead.log").write_text(
        f"{now.strftime('%Y-%m-%d %H:%M:%S')} | ERROR | Surfshark is off: connect it, then re-run.\n",
        encoding="utf-8",
    )
    signals = bj._launch_operator_signals(freshest="", running=[], stalled=[])
    assert signals["vpn_down"] is True
    assert "Surfshark" in signals["warning"]


def test_auto_resume_waits_for_vpn(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BATCH_JOBS_ALLOW_LAUNCH", "1")
    monkeypatch.setenv("BATCH_JOBS_AUTO_RESUME", "1")
    monkeypatch.setattr(bj, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(bj, "_vpn_tunnel_up_for_resume", lambda: False)
    monkeypatch.setattr(bj, "_pid_alive", lambda _pid: False)
    (tmp_path / "data" / "cache" / "batch_jobs").mkdir(parents=True)
    exit_path = tmp_path / "data" / "cache" / "batch_jobs" / "discover.exit"
    exit_path.write_text("5\n", encoding="utf-8")
    meta = {
        "pid": 999001,
        "step": "discover",
        "states": ["WI"],
        "cohort": "priority",
        "n": 10,
        "parallel": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "exit_path": str(exit_path),
        "auto_resume": True,
        "resume_count": 0,
        "stopped": False,
    }
    bj._write_launches([meta])
    resumed, note = bj._maybe_auto_resume_launches("")
    assert resumed == []
    assert "waiting for VPN" in note
    kept = bj._read_launches()
    assert kept and kept[0].get("awaiting_vpn") is True


def test_auto_resume_respawns_when_vpn_up(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BATCH_JOBS_ALLOW_LAUNCH", "1")
    monkeypatch.setenv("BATCH_JOBS_AUTO_RESUME", "1")
    monkeypatch.setattr(bj, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(bj, "_vpn_tunnel_up_for_resume", lambda: True)
    monkeypatch.setattr(bj, "_pid_alive", lambda _pid: False)
    (tmp_path / "data" / "cache" / "batch_jobs").mkdir(parents=True)
    exit_path = tmp_path / "data" / "cache" / "batch_jobs" / "discover.exit"
    exit_path.write_text("5\n", encoding="utf-8")
    spawned: list[dict] = []

    def _fake_spawn(step, **kwargs):
        meta = {
            "pid": 4242,
            "step": step,
            "states": kwargs.get("states") or [],
            "cohort": kwargs.get("cohort") or "priority",
            "n": kwargs.get("n") or 10,
            "parallel": kwargs.get("parallel") or 1,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "exit_path": str(tmp_path / "new.exit"),
            "auto_resume": True,
            "resume_count": kwargs.get("resume_count") or 1,
            "stopped": False,
            "awaiting_vpn": False,
            "log": "data/cache/batch_jobs/launch_discover_new.log",
        }
        spawned.append(meta)
        return meta

    monkeypatch.setattr(bj, "_spawn_launch", _fake_spawn)
    bj._write_launches(
        [
            {
                "pid": 999002,
                "step": "discover",
                "states": ["WI"],
                "cohort": "priority",
                "n": 10,
                "parallel": 1,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "exit_path": str(exit_path),
                "auto_resume": True,
                "resume_count": 0,
                "stopped": False,
                "awaiting_vpn": True,
            }
        ]
    )
    resumed, note = bj._maybe_auto_resume_launches("")
    assert resumed == ["discover"]
    assert "Auto-resumed" in note
    assert spawned and spawned[0]["resume_count"] == 1


def test_auto_resume_skips_clean_exit_and_stopped(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BATCH_JOBS_ALLOW_LAUNCH", "1")
    monkeypatch.setenv("BATCH_JOBS_AUTO_RESUME", "1")
    monkeypatch.setattr(bj, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(bj, "_vpn_tunnel_up_for_resume", lambda: True)
    monkeypatch.setattr(bj, "_pid_alive", lambda _pid: False)
    (tmp_path / "data" / "cache" / "batch_jobs").mkdir(parents=True)
    ok_exit = tmp_path / "data" / "cache" / "batch_jobs" / "ok.exit"
    ok_exit.write_text("0\n", encoding="utf-8")
    calls = {"n": 0}

    def _no_spawn(*_a, **_k):
        calls["n"] += 1
        raise AssertionError("should not spawn")

    monkeypatch.setattr(bj, "_spawn_launch", _no_spawn)
    bj._write_launches(
        [
            {
                "pid": 1,
                "step": "discover",
                "exit_path": str(ok_exit),
                "auto_resume": True,
                "resume_count": 0,
                "stopped": False,
                "states": ["WI"],
                "cohort": "priority",
                "n": 10,
                "parallel": 1,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "pid": 2,
                "step": "captions",
                "exit_path": "",
                "auto_resume": False,
                "stopped": True,
                "resume_count": 0,
                "states": ["WI"],
                "cohort": "priority",
                "n": 10,
                "parallel": 1,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
    )
    resumed, _note = bj._maybe_auto_resume_launches("")
    assert resumed == []
    assert calls["n"] == 0
