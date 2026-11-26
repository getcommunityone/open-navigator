"""Unit tests for metadata-gate validation sampling (pure, no DB/Jev)."""

from __future__ import annotations

import random
from collections import Counter

import pytest

from llm.typesafe.meta_gate_sample import (
    SampledVideo,
    ScoredVideo,
    VideoRow,
    assign_ab_split,
    draw_channel_capped,
    pick_states,
    pick_threshold,
    stratified_final_draw,
    wilson_interval,
)


def test_pick_states_mixes_large_and_small_and_is_seeded():
    counts = {
        f"S{i}": c
        for i, c in enumerate(
            [5000, 4000, 3000, 2000, 1500, 800, 400, 200, 100, 80, 60, 55]
        )
    }
    a = pick_states(counts, rng=random.Random(20261121), n_states=8, min_count=50)
    b = pick_states(counts, rng=random.Random(20261121), n_states=8, min_count=50)
    assert a == b
    assert len(a) == 8
    ranked = sorted(counts, key=counts.get, reverse=True)
    top_q = set(ranked[: max(1, len(ranked) // 4)])
    bottom_half = set(ranked[len(ranked) // 2 :])
    assert any(s in top_q for s in a)
    assert any(s in bottom_half for s in a)


def test_draw_channel_capped_respects_cap_and_seed():
    rows = [
        VideoRow(
            video_id=f"v{i}",
            state_code="AL",
            channel_id=f"c{i // 15}",
            title="t",
            jurisdiction_id="j",
        )
        for i in range(100)
    ]
    got = draw_channel_capped(rows, rng=random.Random(1), n=40, max_per_channel=10)
    assert len(got) <= 40
    assert max(Counter(r.channel_id for r in got).values()) <= 10
    again = draw_channel_capped(rows, rng=random.Random(1), n=40, max_per_channel=10)
    assert [r.video_id for r in again] == [r.video_id for r in got]


def test_stratified_draw_band_and_srs_with_weights():
    scored: list[ScoredVideo] = []
    for i in range(20):
        # 10 in band [0.3, 0.7], 10 outside; unique channels
        score = 0.5 if i < 10 else (0.1 if i < 15 else 0.9)
        scored.append(
            ScoredVideo(
                video_id=f"v{i}",
                state_code="X",
                channel_id=f"c{i}",
                title="t",
                jurisdiction_id="j",
                meta_keep_score=score,
            )
        )
    out = stratified_final_draw(
        scored, rng=random.Random(0), n_final=10, max_per_channel=10
    )
    assert len(out) == 10
    bands = [r for r in out if r.stratum == "band"]
    srs = [r for r in out if r.stratum == "srs"]
    assert abs(len(bands) - len(srs)) <= 1
    assert all(r.sampling_weight > 0 for r in out)
    # Band N=10; if we drew 5 band → weight 2.0
    if bands:
        n_band = len(bands)
        assert bands[0].sampling_weight == pytest.approx(10 / n_band)


def test_stratified_band_wins_on_overlap():
    scored = [
        ScoredVideo(
            video_id="same",
            state_code="X",
            channel_id="c0",
            title="t",
            jurisdiction_id="j",
            meta_keep_score=0.5,
        ),
        *[
            ScoredVideo(
                video_id=f"o{i}",
                state_code="X",
                channel_id=f"c{i+1}",
                title="t",
                jurisdiction_id="j",
                meta_keep_score=0.1,
            )
            for i in range(9)
        ],
    ]
    out = stratified_final_draw(
        scored, rng=random.Random(1), n_final=4, max_per_channel=10
    )
    by_id = {r.video_id: r for r in out}
    if "same" in by_id:
        assert by_id["same"].stratum == "band"


def test_ab_split_seeded_half():
    rows = [
        SampledVideo(
            video_id=f"v{i}",
            state_code="X",
            channel_id=f"c{i}",
            title="t",
            jurisdiction_id="j",
            meta_keep_score=0.5,
            stratum="band" if i % 2 == 0 else "srs",
            sampling_weight=1.0,
            split="A",
        )
        for i in range(100)
    ]
    a = assign_ab_split(rows, rng=random.Random(20261121))
    b = assign_ab_split(rows, rng=random.Random(20261121))
    assert [r.split for r in a] == [r.split for r in b]
    assert abs(sum(1 for r in a if r.split == "A") - 50) <= 1


def test_wilson_contains_p_and_pick_rule():
    lo, hi = wilson_interval(1, 100)
    assert 0.0 <= lo <= 0.01 <= hi <= 1.0
    table = [
        {
            "threshold": 0.3,
            "wrong_skip_ub": 0.015,
            "wrong_keep_rate": 0.2,
            "wrong_keep_n": 20,
        },
        {
            "threshold": 0.5,
            "wrong_skip_ub": 0.018,
            "wrong_keep_rate": 0.05,
            "wrong_keep_n": 5,
        },
        {
            "threshold": 0.6,
            "wrong_skip_ub": 0.03,
            "wrong_keep_rate": 0.01,
            "wrong_keep_n": 1,
        },
    ]
    pick = pick_threshold(table, max_wrong_skip_ub=0.02)
    assert pick["chosen"] == 0.5
    assert pick["meets_bound"] is True
    assert pick["extra_transcripts"] == 5
