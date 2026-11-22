---
sidebar_position: 37
title: Jev metadata gate validation — implementation plan
description: Task plan for the multi-state stratified validation sample (#666).
---

# Jev metadata gate validation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a seeded multi-state ~1,000-video validation sample that picks a metadata keep/skip threshold with half-B wrong-skip Wilson upper bound ≤ 2%, and report extra-transcript cost.

**Architecture:** Pure survey-design helpers in `meta_gate_sample.py` (unit-tested first); CLI `meta_gate_validate.py` loads the transcripted catalog frame, screens meta on a channel-capped pool, draws the stratified final sample with weights, screens transcript as answer key, writes CSVs/JSON/docs.

**Tech Stack:** Python 3.11+, pytest, loguru, psycopg2, existing `llm.typesafe.screen_video_meta` / `screen_transcripts`, Wilson score interval (stdlib/`math` only).

## Global Constraints

- Calendar years on the wire stay strings; not relevant to this change.
- New Python only in `packages/llm` — never add to `scripts/`.
- Conventional Commits; branch `feat/666-meta-gate-validation`; PR closes #666.
- No fabricated rates — report empty/unavailable if screens fail.
- TDD for sampler: failing test before production code.
- Default seed `20261121`; channel cap `10`; thresholds `(0.3, 0.4, 0.5, 0.6)`; wrong-skip UB ≤ `0.02`.
- Design: `web_docs/docs/development/jev-meta-gate-validation-design.md`.

## File map

| File | Responsibility |
|---|---|
| `packages/llm/src/llm/typesafe/meta_gate_sample.py` | Pure sampling, weights, split, Wilson, pick |
| `packages/llm/src/llm/typesafe/meta_gate_validate.py` | CLI + DB load + screen orchestration + CSV/JSON/docs writers |
| `packages/llm/tests/test_meta_gate_sample.py` | Sampler unit tests |
| `packages/llm/tests/test_meta_gate_validate.py` | Parser / dry-path smoke (no live Jev) |
| `data/cache/jev_meta_gate_validation_*.csv\|json` | Run artifacts |
| `web_docs/docs/development/jev-meta-gate-validation.md` | Human threshold report |

---

### Task 1: State pick + channel-capped pool draw

**Files:**
- Create: `packages/llm/src/llm/typesafe/meta_gate_sample.py`
- Test: `packages/llm/tests/test_meta_gate_sample.py`

**Interfaces:**
- Produces:
  - `VideoRow` dataclass: `video_id`, `state_code`, `channel_id`, `title`, `jurisdiction_id` (+ optional fields later)
  - `pick_states(state_counts: dict[str, int], *, rng: random.Random, n_states: int = 8, min_count: int = 50) -> list[str]`
  - `draw_channel_capped(rows: Sequence[VideoRow], *, rng, n: int, max_per_channel: int = 10) -> list[VideoRow]`

- [ ] **Step 1: Write failing tests** for seeded state pick (large+small mix) and channel cap / reproducibility.

```python
def test_pick_states_mixes_large_and_small_and_is_seeded():
    counts = {f"S{i}": c for i, c in enumerate(
        [5000, 4000, 3000, 2000, 1500, 800, 400, 200, 100, 80, 60, 55]
    )}
    a = pick_states(counts, rng=random.Random(20261121), n_states=8, min_count=50)
    b = pick_states(counts, rng=random.Random(20261121), n_states=8, min_count=50)
    assert a == b and len(a) == 8
    ranked = sorted(counts, key=counts.get, reverse=True)
    top_q = set(ranked[: max(1, len(ranked) // 4)])
    bottom_half = set(ranked[len(ranked) // 2 :])
    assert any(s in top_q for s in a) and any(s in bottom_half for s in a)

def test_draw_channel_capped_respects_cap_and_seed():
    rows = [
        VideoRow(video_id=f"v{i}", state_code="AL", channel_id=f"c{i // 15}",
                 title="t", jurisdiction_id="j")
        for i in range(100)
    ]
    got = draw_channel_capped(rows, rng=random.Random(1), n=40, max_per_channel=10)
    assert len(got) <= 40
    from collections import Counter
    assert max(Counter(r.channel_id for r in got).values()) <= 10
    assert draw_channel_capped(rows, rng=random.Random(1), n=40, max_per_channel=10) == got
```

- [ ] **Step 2: Run tests — expect FAIL** (`pytest packages/llm/tests/test_meta_gate_sample.py -q`)
- [ ] **Step 3: Implement minimal `pick_states` + `draw_channel_capped` + `VideoRow`**
- [ ] **Step 4: Run tests — expect PASS**
- [ ] **Step 5: Commit** `test(llm): sampler state pick and channel cap for meta gate validation`

---

### Task 2: Stratified final draw, weights, A/B split

**Files:**
- Modify: `meta_gate_sample.py`
- Modify: `test_meta_gate_sample.py`

**Interfaces:**
- Produces:
  - `ScoredVideo` = VideoRow fields + `meta_keep_score: float`
  - `SampledVideo` = ScoredVideo + `stratum: Literal["band","srs"]`, `sampling_weight: float`, `split: Literal["A","B"]`
  - `stratified_final_draw(scored, *, rng, n_final=1000, band=(0.3,0.7), max_per_channel=10) -> list[SampledVideo]`
  - Weight: within each (state, stratum) cell, `w = N_cell / n_drawn_cell` (finite-population inverse inclusion for SRS without replacement in that cell). For band stratum, `N_cell` = count in band in that state in the **pool**; for srs, `N_cell` = all scored in that state in the pool. Videos selected in band are excluded from srs eligibility.
  - `assign_ab_split(rows, *, rng) -> list[SampledVideo]` with ~50/50, deterministic.

- [ ] **Step 1: Failing tests** — ~50/50 strata, band wins on overlap, weights = N/n on toy frame, A/B deterministic and balanced.

```python
def test_stratified_draw_band_and_srs_with_weights():
    # 20 videos state X: 10 in band [0.3,0.7], 10 outside; unique channels
    scored = [...]
    out = stratified_final_draw(scored, rng=random.Random(0), n_final=10, max_per_channel=10)
    bands = [r for r in out if r.stratum == "band"]
    srs = [r for r in out if r.stratum == "srs"]
    assert abs(len(bands) - len(srs)) <= 1
    # band weight for state X: N_band/n_band
    assert all(r.sampling_weight > 0 for r in out)

def test_ab_split_seeded_half():
    rows = [SampledVideo(...) for i in range(100)]  # weights/strata filled
    a = assign_ab_split(rows, rng=random.Random(20261121))
    b = assign_ab_split(rows, rng=random.Random(20261121))
    assert [r.split for r in a] == [r.split for r in b]
    assert abs(sum(r.split == "A" for r in a) - 50) <= 1
```

- [ ] **Step 2–4:** RED → implement → GREEN
- [ ] **Step 5: Commit** `feat(llm): stratified meta-gate sample with weights and A/B split`

---

### Task 3: Wilson CI + threshold pick

**Files:**
- Modify: `meta_gate_sample.py`
- Modify: `test_meta_gate_sample.py`

**Interfaces:**
- Produces:
  - `wilson_interval(successes: float, n: float, *, z: float = 1.96) -> tuple[float,float]` (standard Wilson; for weighted rates pass effective counts: `p_hat = sum(w*y)/sum(w)`, `n_eff = (sum w)^2 / sum(w^2)`, `successes = p_hat * n_eff`)
  - `gate_label(keep_score, threshold) -> "keep"|"skip"` using `meeting_keep_p_below` semantics (None → keep)
  - `rate_table(rows, *, thresholds, split_filter) -> list[dict]` with wrong_skip/wrong_keep counts, weighted rates, Wilson CIs
  - `pick_threshold(half_b_table, *, max_wrong_skip_ub=0.02) -> dict` with `chosen`, `meets_bound`, `extra_transcripts` (wrong_keep count)

```python
def test_wilson_contains_p_and_pick_rule():
    lo, hi = wilson_interval(1, 100)
    assert 0 <= lo <= 0.01 <= hi <= 1
    table = [
        {"threshold": 0.3, "wrong_skip_ub": 0.015, "wrong_keep_rate": 0.2, "wrong_keep_n": 20},
        {"threshold": 0.5, "wrong_skip_ub": 0.018, "wrong_keep_rate": 0.05, "wrong_keep_n": 5},
        {"threshold": 0.6, "wrong_skip_ub": 0.03, "wrong_keep_rate": 0.01, "wrong_keep_n": 1},
    ]
    pick = pick_threshold(table, max_wrong_skip_ub=0.02)
    assert pick["chosen"] == 0.5 and pick["meets_bound"] is True
```

- [ ] **Step 2–4:** RED → implement → GREEN
- [ ] **Step 5: Commit** `feat(llm): Wilson intervals and meta-gate threshold pick`

---

### Task 4: CLI orchestration (validate module)

**Files:**
- Create: `packages/llm/src/llm/typesafe/meta_gate_validate.py` (+ `__main__` via `python -m`)
- Create: `packages/llm/tests/test_meta_gate_validate.py`
- Ensure package runs as `python -m llm.typesafe.meta_gate_validate`

**Behavior:**
1. Resolve DB URL; load frame SQL: transcript_file_path IS NOT NULL, title/description present, channel_id, state_code.
2. Count by state → `pick_states` (or `--states` override).
3. Per-state channel-capped draw totaling `--n-pool`.
4. Unless `--skip-screen` / `--dry-run`: meta-screen missing pool videos (reuse `screen_meta` + upsert).
5. Load meta keep-scores for pool; `stratified_final_draw`; `assign_ab_split`.
6. Transcript-screen final sample (reuse transcript screener helpers / same DB table).
7. Build rate tables for A and B; `pick_threshold` on B; write sample CSV, disagreements CSV (`human_decision` empty), report JSON.
8. `--dry-run` stops after pool selection and prints counts / estimated tokens.

- [ ] **Step 1: Parser test** for flags defaults
- [ ] **Step 2–4:** Implement CLI; keep heavy I/O out of unit tests (mock or dry-run only)
- [ ] **Step 5: Commit** `feat(llm): meta_gate_validate CLI for multi-state calibration sample`

---

### Task 5: Full run + docs report + PR

**Files:**
- Create: `web_docs/docs/development/jev-meta-gate-validation.md`
- Create: cache CSVs/JSON from the run
- Modify: sidebars if needed for the results page
- PR via `gh`

- [ ] **Step 1:** Run `python -m llm.typesafe.meta_gate_validate --seed 20261121 --n-final 1000 --n-pool 2500` (long; log progress). Use repo `.venv` and env from `.env`.
- [ ] **Step 2:** Fill results markdown from JSON (real numbers only).
- [ ] **Step 3:** Commit artifacts + docs.
- [ ] **Step 4:** Push branch; `gh pr create` with Attributes + Closes #666.

---

## Self-review

1. Spec coverage: sampling, weights, transcript labels, disagreement CSV, A/B, Wilson, pick ≤2%, extra transcripts, tests, issue/PR — all tasked.
2. No TBD placeholders in task steps.
3. Types: `VideoRow` / `ScoredVideo` / `SampledVideo` consistent across tasks.
