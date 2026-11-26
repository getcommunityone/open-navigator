"""Pure sampling / metrics for metadata keep-skip gate validation.

No database or Jev calls — see ``meta_gate_validate`` for orchestration.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any, Literal, Sequence

Stratum = Literal["band", "srs"]
Split = Literal["A", "B"]

DEFAULT_SEED = 20261121
DEFAULT_BAND = (0.3, 0.7)
DEFAULT_THRESHOLDS: tuple[float, ...] = (0.3, 0.4, 0.5, 0.6)
MAX_WRONG_SKIP_UB = 0.02


@dataclass(frozen=True)
class VideoRow:
    video_id: str
    state_code: str
    channel_id: str
    title: str
    jurisdiction_id: str


@dataclass(frozen=True)
class ScoredVideo(VideoRow):
    meta_keep_score: float


@dataclass(frozen=True)
class SampledVideo(ScoredVideo):
    stratum: Stratum
    sampling_weight: float
    split: Split = "A"


def pick_states(
    state_counts: dict[str, int],
    *,
    rng: random.Random,
    n_states: int = 8,
    min_count: int = 50,
) -> list[str]:
    """Seeded mix of large (top quartile) and small (bottom half) states."""
    eligible = {s: c for s, c in state_counts.items() if c >= min_count}
    if not eligible:
        return []
    ranked = sorted(eligible, key=lambda s: (-eligible[s], s))
    n = len(ranked)
    top_q = ranked[: max(1, n // 4)]
    bottom_half = ranked[n // 2 :]
    n_large = max(1, n_states // 2)
    n_small = max(1, n_states - n_large)
    large = list(top_q)
    rng.shuffle(large)
    small = [s for s in bottom_half if s not in large]
    rng.shuffle(small)
    chosen: list[str] = []
    for s in large:
        if len(chosen) >= n_large:
            break
        chosen.append(s)
    for s in small:
        if len(chosen) >= n_large + n_small:
            break
        if s not in chosen:
            chosen.append(s)
    # Fill if pools were thin
    for s in ranked:
        if len(chosen) >= n_states:
            break
        if s not in chosen:
            chosen.append(s)
    return chosen[:n_states]


def draw_channel_capped(
    rows: Sequence[VideoRow],
    *,
    rng: random.Random,
    n: int,
    max_per_channel: int = 10,
) -> list[VideoRow]:
    """SRS of up to ``n`` rows with at most ``max_per_channel`` per channel_id."""
    if n <= 0 or not rows:
        return []
    order = list(rows)
    rng.shuffle(order)
    picked: list[VideoRow] = []
    per_ch: dict[str, int] = defaultdict(int)
    for row in order:
        if len(picked) >= n:
            break
        ch = row.channel_id or ""
        if per_ch[ch] >= max_per_channel:
            continue
        picked.append(row)
        per_ch[ch] += 1
    return picked


def _in_band(score: float, band: tuple[float, float]) -> bool:
    lo, hi = band
    return lo <= score <= hi


def stratified_final_draw(
    scored: Sequence[ScoredVideo],
    *,
    rng: random.Random,
    n_final: int = 1000,
    band: tuple[float, float] = DEFAULT_BAND,
    max_per_channel: int = 10,
) -> list[SampledVideo]:
    """Half band / half SRS; band wins on overlap; channel cap; inverse weights."""
    if n_final <= 0 or not scored:
        return []
    n_band_target = n_final // 2
    n_srs_target = n_final - n_band_target

    by_state: dict[str, list[ScoredVideo]] = defaultdict(list)
    for v in scored:
        by_state[v.state_code].append(v)

    # Allocate band/srs quotas roughly proportional to state pool size
    states = sorted(by_state)
    state_sizes = [len(by_state[s]) for s in states]
    total = sum(state_sizes) or 1

    def _quotas(target: int) -> dict[str, int]:
        raw = {s: target * len(by_state[s]) / total for s in states}
        floors = {s: int(math.floor(raw[s])) for s in states}
        rem = target - sum(floors.values())
        frac_order = sorted(states, key=lambda s: (raw[s] - floors[s], s), reverse=True)
        for s in frac_order:
            if rem <= 0:
                break
            floors[s] += 1
            rem -= 1
        return floors

    band_q = _quotas(n_band_target)
    srs_q = _quotas(n_srs_target)

    selected: dict[str, SampledVideo] = {}
    per_ch: dict[str, int] = defaultdict(int)

    def _can_take(v: ScoredVideo) -> bool:
        ch = v.channel_id or ""
        return per_ch[ch] < max_per_channel and v.video_id not in selected

    def _take(v: ScoredVideo, stratum: Stratum, weight: float) -> None:
        ch = v.channel_id or ""
        selected[v.video_id] = SampledVideo(
            video_id=v.video_id,
            state_code=v.state_code,
            channel_id=v.channel_id,
            title=v.title,
            jurisdiction_id=v.jurisdiction_id,
            meta_keep_score=v.meta_keep_score,
            stratum=stratum,
            sampling_weight=weight,
            split="A",
        )
        per_ch[ch] += 1

    # --- Band draw per state ---
    for state in states:
        pool = [v for v in by_state[state] if _in_band(v.meta_keep_score, band)]
        rng.shuffle(pool)
        need = band_q[state]
        taken: list[ScoredVideo] = []
        for v in pool:
            if len(taken) >= need:
                break
            if _can_take(v):
                taken.append(v)
        n_drawn = len(taken)
        n_cell = len(pool)
        w = (n_cell / n_drawn) if n_drawn else 0.0
        for v in taken:
            _take(v, "band", w)

    # --- SRS draw per state (exclude already selected) ---
    for state in states:
        pool = [v for v in by_state[state] if v.video_id not in selected]
        rng.shuffle(pool)
        need = srs_q[state]
        taken = []
        for v in pool:
            if len(taken) >= need:
                break
            if _can_take(v):
                taken.append(v)
        n_drawn = len(taken)
        n_cell = len(by_state[state])  # SRS frame = all scored in state
        w = (n_cell / n_drawn) if n_drawn else 0.0
        for v in taken:
            _take(v, "srs", w)

    # Top up if short (any remaining, channel-capped)
    if len(selected) < n_final:
        leftover = [v for v in scored if _can_take(v)]
        rng.shuffle(leftover)
        for v in leftover:
            if len(selected) >= n_final:
                break
            stratum: Stratum = "band" if _in_band(v.meta_keep_score, band) else "srs"
            # weight as if singleton draw from remaining cell
            _take(v, stratum, 1.0)

    return list(selected.values())


def assign_ab_split(
    rows: Sequence[SampledVideo],
    *,
    rng: random.Random,
) -> list[SampledVideo]:
    """Seeded ~50/50 A/B split."""
    order = list(rows)
    rng.shuffle(order)
    mid = len(order) // 2
    out: list[SampledVideo] = []
    for i, row in enumerate(order):
        split: Split = "A" if i < mid else "B"
        out.append(replace(row, split=split))
    return out


def wilson_interval(
    successes: float,
    n: float,
    *,
    z: float = 1.96,
) -> tuple[float, float]:
    """Wilson score 95% CI for a binomial proportion."""
    if n <= 0:
        return (0.0, 1.0)
    p = max(0.0, min(1.0, successes / n))
    z2 = z * z
    denom = 1.0 + z2 / n
    center = p + z2 / (2.0 * n)
    margin = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)
    lo = (center - margin) / denom
    hi = (center + margin) / denom
    return (max(0.0, lo), min(1.0, hi))


def gate_label(keep_score: float | None, threshold: float) -> Literal["keep", "skip"]:
    """Skip only when keep_score is strictly below threshold (None → keep)."""
    if keep_score is None:
        return "keep"
    return "skip" if keep_score < threshold else "keep"


def weighted_rate_and_ci(
    indicators: Sequence[float],
    weights: Sequence[float],
) -> dict[str, float]:
    """Hajek weighted mean with Wilson CI using Kish effective n."""
    if not indicators:
        return {
            "rate": 0.0,
            "n": 0.0,
            "n_eff": 0.0,
            "lo": 0.0,
            "ub": 1.0,
            "count": 0.0,
        }
    w = [float(x) for x in weights]
    y = [float(x) for x in indicators]
    sw = sum(w)
    if sw <= 0:
        return {
            "rate": 0.0,
            "n": float(len(y)),
            "n_eff": 0.0,
            "lo": 0.0,
            "ub": 1.0,
            "count": float(sum(y)),
        }
    p = sum(wi * yi for wi, yi in zip(w, y)) / sw
    n_eff = (sw * sw) / sum(wi * wi for wi in w)
    successes = p * n_eff
    lo, ub = wilson_interval(successes, n_eff)
    return {
        "rate": p,
        "n": float(len(y)),
        "n_eff": n_eff,
        "lo": lo,
        "ub": ub,
        "count": float(sum(y)),
    }


def rate_table(
    rows: Sequence[dict[str, Any]],
    *,
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
    split_filter: Split | None = None,
) -> list[dict[str, Any]]:
    """Wrong-skip / wrong-keep rates at each threshold.

    Each row needs ``split``, ``sampling_weight``, ``meta_keep_score``,
    ``transcript_keep_score``.
    """
    subset = [
        r
        for r in rows
        if split_filter is None or r.get("split") == split_filter
    ]
    out: list[dict[str, Any]] = []
    for t in thresholds:
        ws_ind: list[float] = []
        wk_ind: list[float] = []
        weights: list[float] = []
        ws_n = wk_n = 0
        for r in subset:
            w = float(r.get("sampling_weight") or 1.0)
            meta_g = gate_label(r.get("meta_keep_score"), t)
            tx_g = gate_label(r.get("transcript_keep_score"), t)
            wrong_skip = 1.0 if (meta_g == "skip" and tx_g == "keep") else 0.0
            wrong_keep = 1.0 if (meta_g == "keep" and tx_g == "skip") else 0.0
            ws_ind.append(wrong_skip)
            wk_ind.append(wrong_keep)
            weights.append(w)
            ws_n += int(wrong_skip)
            wk_n += int(wrong_keep)
        ws = weighted_rate_and_ci(ws_ind, weights)
        wk = weighted_rate_and_ci(wk_ind, weights)
        out.append(
            {
                "threshold": float(t),
                "n": len(subset),
                "wrong_skip_n": ws_n,
                "wrong_keep_n": wk_n,
                "wrong_skip_rate": ws["rate"],
                "wrong_keep_rate": wk["rate"],
                "wrong_skip_lo": ws["lo"],
                "wrong_skip_ub": ws["ub"],
                "wrong_keep_lo": wk["lo"],
                "wrong_keep_ub": wk["ub"],
                "n_eff": ws["n_eff"],
            }
        )
    return out


def pick_threshold(
    half_b_table: Sequence[dict[str, Any]],
    *,
    max_wrong_skip_ub: float = MAX_WRONG_SKIP_UB,
) -> dict[str, Any]:
    """Prefer T with wrong-skip UB ≤ bound and minimal wrong-keep rate."""
    qualifying = [
        row
        for row in half_b_table
        if float(row.get("wrong_skip_ub", 1.0)) <= max_wrong_skip_ub
    ]
    if qualifying:
        best = min(
            qualifying,
            key=lambda r: (float(r["wrong_keep_rate"]), float(r["threshold"])),
        )
        return {
            "chosen": float(best["threshold"]),
            "meets_bound": True,
            "extra_transcripts": int(best["wrong_keep_n"]),
            "row": dict(best),
        }
    if not half_b_table:
        return {
            "chosen": None,
            "meets_bound": False,
            "extra_transcripts": 0,
            "row": None,
        }
    best = min(half_b_table, key=lambda r: float(r.get("wrong_skip_ub", 1.0)))
    return {
        "chosen": float(best["threshold"]),
        "meets_bound": False,
        "extra_transcripts": int(best["wrong_keep_n"]),
        "row": dict(best),
    }
