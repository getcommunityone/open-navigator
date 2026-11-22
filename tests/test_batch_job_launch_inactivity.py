"""Launch inactivity / VPN warning helpers for the batch-jobs dashboard (#750)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import api.routes.batch_jobs as bj


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
