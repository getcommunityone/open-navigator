"""Run all must cover discover through reports (#689, #691)."""

from __future__ import annotations

from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "packages"
    / "scrapers"
    / "scripts"
    / "youtube_run_priority_states_last_n.sh"
)


def _all_arm() -> str:
    text = _SCRIPT.read_text(encoding="utf-8")
    start = text.index("  all)")
    end = text.index("  list)", start)
    return text[start:end]


def test_all_case_runs_discover_before_catalog():
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "run_discover()" in text
    all_arm = _all_arm()
    assert "run_discover" in all_arm
    assert all_arm.index("run_discover") < all_arm.index("run_catalog")
    assert "SKIP_DISCOVER" in all_arm


def test_all_case_runs_reports_after_analyze():
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "run_reports()" in text
    all_arm = _all_arm()
    assert "run_reports" in all_arm
    assert all_arm.index("run_analyze") < all_arm.index("run_reports")
    assert "SKIP_REPORTS" in all_arm
