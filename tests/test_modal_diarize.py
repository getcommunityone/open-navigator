"""The Modal GPU step's plain parts (#314): batch cap, estimated cost, usage row. Modal isn't needed to import it."""

import math

from llm.gpu import modal_diarize as md


def test_the_batch_is_capped_trimmed_and_deduplicated():
    items = [" a.opus ", "b.mp3", "a.opus", "", "c.wav", "d.wav"]
    assert md.plan_batch(items, limit=3) == ["a.opus", "b.mp3", "c.wav"]


def test_a_limit_below_one_still_runs_one_item():
    assert md.plan_batch(["a", "b"], limit=0) == ["a"]


def test_the_cost_is_seconds_times_the_published_gpu_rate():
    assert math.isclose(md.estimated_cost_usd(3600, "T4"), 3600 * md.GPU_USD_PER_SECOND["T4"])
    assert math.isclose(md.estimated_cost_usd(10, "t4"), 10 * md.GPU_USD_PER_SECOND["T4"])


def test_an_unknown_gpu_has_no_cost_rather_than_a_guess():
    assert md.estimated_cost_usd(60, "Z9") is None


def test_the_usage_row_says_it_is_an_estimate():
    row = md.usage_row("a.opus", "T4", "2026-11-14T20:00:00+00:00", 1800.0, "ok")
    assert row["item_name"] == "a.opus" and row["gpu_name"] == "T4" and row["run_status_code"] == "ok"
    assert math.isclose(row["gpu_hours"], 0.5)
    assert math.isclose(row["estimated_cost_usd"], 1800 * md.GPU_USD_PER_SECOND["T4"])
    assert row["is_estimated"] is True
    assert row["platform_name"] == "modal"


def test_an_item_is_a_volume_path_or_a_direct_url():
    assert md.source_of("meetings/2026-11-03.opus") == ("volume", "/audio/meetings/2026-11-03.opus")
    assert md.source_of("https://example.org/a.mp4") == ("url", "https://example.org/a.mp4")


def test_a_path_cannot_leave_the_volume():
    try:
        md.source_of("../etc/passwd")
    except ValueError as e:
        assert "volume" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_the_output_name_is_safe_for_a_file():
    assert md.output_name("meetings/2026-11-03 council.opus") == "meetings_2026-11-03_council.diarized.json"
    assert md.output_name("https://example.org/v/a.mp4?x=1").endswith(".diarized.json")
