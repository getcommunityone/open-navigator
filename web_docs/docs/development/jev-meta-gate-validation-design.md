---
sidebar_position: 36
title: Jev metadata gate validation sample
description: Multi-state stratified sample to choose a metadata keep/skip threshold with a wrong-skip upper bound ≤ 2%.
---

# Jev metadata gate validation sample

Decision record approved 2026-11-21. Extends
[Jev metadata screen and transcript scale-out](./jev-meta-and-scale-design.md)
(Phase 1 AL compare) with a multi-state validation sample that replaces the
Alabama-only CSV as the caption-gate calibration source.

## Problem

The AL-only compare (`data/cache/jev_meta_vs_transcript_al_review.csv`, N=300)
showed 98% keep/skip agreement at T=0.6, but it cannot support a calibrated
threshold for a national caption gate: one state, no sampling weights, no
holdout, and no wrong-skip confidence bound. We need a seeded multi-state
sample (~1,000) with transcript Jev as the answer key, disagreement rows for
hand check, and an A/B threshold pick whose half-B wrong-skip upper bound is
at or under 2%.

## Approach (locked)

New pure sampler + CLI orchestrator under `llm.typesafe` (Approach 1). Reuse
existing meta and transcript screeners; do not bolt survey design onto
`--compare`.

| Choice | Decision |
|---|---|
| Frame | Catalog rows with a downloaded transcript (`transcript_file_path` set) and usable title/description |
| Meta scores before strata | Two-phase: channel-capped candidate pool → meta Jev → stratified final draw |
| PR deliverable | Code + tests **and** a full scored run; commit CSVs + threshold report |
| States | Auto (seeded): mix of large and small by transcript count |

## Contract

### Modules

- `packages/llm/src/llm/typesafe/meta_gate_sample.py` — pure functions (no DB/Jev):
  pick states, channel-capped draw, strata, sampling weights, A/B split,
  Wilson CI, threshold pick.
- `packages/llm/src/llm/typesafe/meta_gate_validate.py` — CLI orchestration.

### CLI

```bash
python -m llm.typesafe.meta_gate_validate \
  --seed 20261121 --n-final 1000 --n-pool 2500
```

Flags: `--seed`, `--n-final`, `--n-pool`, `--states` (optional override),
`--dry-run`, `--database-url`, `--skip-screen` (reuse existing screens only),
`--rescreen`.

### Sampling

1. **States (seeded, 6–10, target 8):** rank states by transcripted-video count;
   draw ~half from the top quartile (large) and ~half from the bottom half
   among states with enough rows to support ≤10/channel and a per-state quota.
   Persist the chosen list on every output row and in the report.
2. **Seed:** `20261121` (override via `--seed`).
3. **Phase 1 pool:** ~2,500 channel-capped candidates (quota split across
   states); random within each state.
4. **Meta screen** that pool (skip if current meta `question_version` already
   present unless `--rescreen`).
5. **Phase 2 final N≈1,000:** 50% from meta keep-score ∈ [0.3, 0.7] (`stratum=
   band`), 50% SRS across all scored candidates (`stratum=srs`); ≤10 per
   channel still enforced; duplicates across strata dropped (band wins).
6. **Weight:** inverse of inclusion probability within the stratum draw
   (state × stratum). Column: `sampling_weight`.
7. **Transcript screen** the final 1,000 (answer key).
8. **A/B split:** seeded 50/50 on the final sample (`split` = `A`|`B`).

### Metrics and threshold pick

At threshold `T`, with transcript gate as answer key:

- **Wrong skip** = meta skip ∧ transcript keep
- **Wrong keep** = meta keep ∧ transcript skip

| Step | What |
|---|---|
| Half A | Report weighted wrong-skip and wrong-keep rates at `T ∈ {0.3, 0.4, 0.5, 0.6}` (tuning table only) |
| Half B | For each candidate `T`, report rates with **Wilson 95% CIs** on weighted proportions; also print unweighted counts |
| Pick rule | Among `T` whose half-B wrong-skip **upper** Wilson bound ≤ **2%**, choose the `T` that **minimizes** half-B wrong-keep rate. If none qualify, report failure and recommend the `T` with the lowest wrong-skip upper bound (do not claim the 2% gate). |
| Extra transcripts | On half B at chosen `T`: count and weighted rate of wrong keeps (captions the meta gate would still pull that transcript Jev would skip). Optionally delta vs T=0.6. |

Half A is exploratory (report the four thresholds). The binding pick uses half B
only — never choose `T` from A rates alone.

### Outputs

| Path | Role |
|---|---|
| `data/cache/jev_meta_gate_validation_sample.csv` | Full labeled sample (replaces AL file as calibration source) |
| `data/cache/jev_meta_gate_validation_disagreements.csv` | Meta≠transcript at chosen `T` (or 0.5 if none meet the bound); empty `human_decision` column |
| `data/cache/jev_meta_gate_validation_report.json` | Machine-readable rates, CIs, chosen T, extra-transcript cost |
| `web_docs/docs/development/jev-meta-gate-validation.md` | Human-readable threshold report (filled after the run) |

Sample CSV columns: `video_id`, `title`, `state_code`, `jurisdiction_id`,
`channel_id`, `stratum`, `sampling_weight`, `split`, `transcript_kind`,
`meta_kind`, `transcript_keep_score`, `meta_keep_score`, `transcript_gate`,
`meta_gate`, `agree_at_threshold`, `threshold`, `youtube_url`,
`keep_kind_keys`.

Keep `data/cache/jev_meta_vs_transcript_al_review.csv` as historical Phase 1
evidence; point Phase 3 calibration at the new multi-state sample.

### Tests (first)

`packages/llm/tests/test_meta_gate_sample.py`:

- Seeded reproducibility
- ≤10 videos per channel
- Stratum mix ~50/50 band/srs
- Weights positive and correct on a toy frame
- A/B split deterministic for a seed
- Wilson CI + pick rule on a fixture

## Out of scope

- Wiring `--skip-jev-meta-below` into caption backfill (#662)
- Keep/skip/review title-cue heuristics (#664)
- Changing Jev prompts or deleting the AL Phase 1 CSV

## Read first

- `web_docs/docs/development/jev-meta-and-scale-design.md`
- `packages/llm/src/llm/typesafe/screen_video_meta.py`
- `packages/llm/src/llm/typesafe/screen_transcripts.py`
- `AGENTS.md` (issue → branch → PR)
