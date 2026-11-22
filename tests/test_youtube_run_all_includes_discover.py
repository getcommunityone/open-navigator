"""Run all must include stage 0 discover (#689)."""

from __future__ import annotations

from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "packages"
    / "scrapers"
    / "scripts"
    / "youtube_run_priority_states_last_n.sh"
)


def test_all_case_runs_discover_before_catalog():
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "run_discover()" in text
    # The `all)` arm must call discover (unless SKIP_DISCOVER) before catalog.
    start = text.index("  all)")
    end = text.index("  list)", start)
    all_arm = text[start:end]
    assert "run_discover" in all_arm
    assert all_arm.index("run_discover") < all_arm.index("run_catalog")
    assert "SKIP_DISCOVER" in all_arm
