"""Stages 1–5 Run all chain + VPN auto-resume coverage (#761)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from api.routes import batch_jobs as bj


@pytest.fixture()
def fake_scripts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path
    disc = (
        root
        / "packages/scrapers/src/scrapers/youtube/load_missing_county_channels.py"
    )
    disc.parent.mkdir(parents=True)
    disc.write_text("# discover\n", encoding="utf-8")
    script = root / "packages/scrapers/scripts/youtube_run_priority_states_last_n.sh"
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/bash\n", encoding="utf-8")
    monkeypatch.setattr(bj, "_repo_root", lambda: root)
    monkeypatch.setattr(bj, "_LAUNCH_SCRIPT", str(script.relative_to(root)))
    return root


def test_run_all_chains_discover_then_shell_all(fake_scripts: Path) -> None:
    argv, env = bj._build_launch_argv(
        "all",
        states=["AL"],
        cohort="priority",
        n=10,
        parallel=2,
    )
    assert argv[:3] == ["bash", "--noprofile", "--norc"]
    chain = argv[4]
    assert "=== Discover (channel candidates) ===" in chain
    assert "load_missing_county_channels.py" in chain
    assert "--load" in chain
    assert "youtube_run_priority_states_last_n.sh" in chain
    assert chain.count(" all") >= 1 or chain.endswith("all")
    assert env.get("BATCH_STATUS") == "1"


@pytest.mark.parametrize(
    "step,needle",
    [
        ("discover", "load_missing_county_channels.py"),
        ("catalog", "youtube_run_priority_states_last_n.sh"),
        ("captions", "youtube_run_priority_states_last_n.sh"),
        ("analyze-light", "youtube_run_priority_states_last_n.sh"),
        ("reports-light", "youtube_run_priority_states_last_n.sh"),
    ],
)
def test_stage_run_argv(fake_scripts: Path, step: str, needle: str) -> None:
    argv, _env = bj._build_launch_argv(
        step,
        states=["AL", "GA"],
        cohort="priority",
        n=10,
        parallel=2,
    )
    joined = " ".join(argv)
    assert needle in joined
    if step != "discover":
        assert step in argv or (
            step == "analyze-light" and "analyze-light" in argv
        )


def test_all_launch_steps_need_vpn_for_auto_resume() -> None:
    """Discover through reports-light (and all) wait/resume on VPN (#761)."""
    for step in (
        "discover",
        "catalog",
        "captions",
        "analyze-light",
        "reports-light",
        "all",
    ):
        assert step in bj._LAUNCH_STEPS_NEED_VPN
        assert step in bj._LAUNCH_STEPS


def test_spawn_sets_auto_resume_true(fake_scripts: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bj.subprocess,
        "Popen",
        lambda *a, **k: type("P", (), {"pid": 4242})(),
    )
    meta = bj._spawn_launch(
        "catalog",
        states=["AL"],
        cohort="priority",
        n=10,
        parallel=2,
        auto_resume=True,
    )
    assert meta["auto_resume"] is True
    assert meta["stopped"] is False
    assert meta["step"] == "catalog"
