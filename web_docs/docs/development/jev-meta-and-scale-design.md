---
sidebar_position: 35
title: Jev metadata screen and transcript scale-out
description: Sequenced plan — compare title/description Jev to transcript Jev, scale captioned screens, then optionally gate caption downloads.
---

# Jev metadata screen and transcript scale-out

Decision record approved 2026-11-21 (Approach A). Builds on
[Jev meeting-kind analysis gate](./jev-meeting-kind-gate.md) and
[Jev transcript screening](./jev-transcript-screening.md).

## Problem

Transcript Jev gates Gemini well, but captions are still fetched for many
non-meetings. Catalog already has `title` + `description` on
`bronze.bronze_event_youtube` before any caption download. We need (1) a
head-to-head compare of metadata vs transcript screens, (2) scale transcript
Jev across captioned videos, and (3) only then an opt-in caption-backfill skip.

## Sequenced plan

| Phase | What | Gate default |
|---|---|---|
| **1 — Compare** | Metadata Jev on the same ~300 AL analyzed videos; CSV vs transcript screens | Nothing skipped |
| **2 — Scale transcript** | `screen_transcripts` over captioned backlog (by state) — [#661](https://github.com/getcommunityone/open-navigator/issues/661) | Gemini skip still opt-in `--skip-jev-meeting-below 0.6` |
| **3 — Caption gate** | Only if Phase 1 agreement is good enough — [#662](https://github.com/getcommunityone/open-navigator/issues/662) | Opt-in on `backfill_transcripts`; unscreened meta never skipped |

Phase 1 issue: [#660](https://github.com/getcommunityone/open-navigator/issues/660).

## Phase 1 contract

### Metadata screen

- CLI: `python -m llm.typesafe.screen_video_meta`
- Input state: `title` + `description` (optional channel title), from
  `bronze.bronze_event_youtube` (+ channel join when useful).
- Same Choice labels as transcript screen (`government_meeting`, `town_hall`,
  `government_other`, `not_government`) and the same Noul questions; wording
  refers to title/description rather than transcript text.
- Table: `bronze.bronze_video_meta_screen_jev` — one row per `video_id`; columns
  mirror the transcript screen table (`meeting_kind`, probabilities,
  `has_decisions_p`, `mentions_data_center_p`, tokens, `question_version`,
  `screened_at`). Separate table so transcript rows are never overwritten.
- Keep-score: `P(government_meeting) + P(town_hall)` (same as analysis gate).
- Stage label for usage rows: `jev_meta_screen`.

### Compare

- Join meta ↔ transcript screens on `video_id` for the AL calibrate sample
  (current transcript `question_version`).
- Export CSV with both kinds, both keep-scores, agree/disagree at T=0.6,
  title, YouTube URL.
- Record agreement rates on this page under **Compare results** (below). Caption
  gate (Phase 3) stays blocked until those numbers are written and accepted.

## Phase 2 / 3 (summary)

- **Phase 2:** batch `screen_transcripts` without `--analyzed-only` across
  states; no caption behavior change.
- **Phase 3:** `backfill_transcripts --skip-jev-meta-below T` (name TBD) reads
  `bronze_video_meta_screen_jev`; default off; missing meta row ⇒ download.

## Out of scope

Channel discover rewrites, deleting captions, dashboard stage row, changing
Gemini prompts.

## Compare results

**2026-11-21 — AL analyzed sample, N=300, T=0.6**

| Metric | Value |
|---|---|
| Agree on keep/skip | **294 / 300 (98.0%)** |
| Meta skip ∩ transcript keep (risky for caption gate) | **6** |
| Meta keep ∩ transcript skip | **0** |

The 6 risky rows are mostly titled “Pre-Council Briefing” / personal meeting room /
employee recognitions — meta keep-score dipped below 0.6 while transcript still
kept them. Spreadsheet:
`data/cache/jev_meta_vs_transcript_al_review.csv`.

**Caption-gate decision:** agreement is strong enough to prototype Phase 3 as
**opt-in** with the same T=0.6, but do **not** turn it on by default until a
human spot-checks those 6 (and any similar title patterns) in the CSV.

**Multi-state calibration (follow-up):** the AL file is historical Phase 1
evidence only. Choose the production metadata threshold from the stratified
validation sample — see
[Jev metadata gate validation sample](./jev-meta-gate-validation-design.md)
([#666](https://github.com/getcommunityone/open-navigator/issues/666)).

### Final keep / skip / review (2026-11-21, #664)

Threshold stays **0.6**. After compare scores are written:

1. Metadata title cues (`pre-council`, `briefing`, `meeting room`) lift
   `meta_keep` to at least 0.6 when present (`llm.typesafe.keep_decision`).
2. Final decision: transcript ≥ 0.9 and meta in [0.4, 0.6] → **keep**;
   transcript in [0.6, 0.7] and meta < 0.1 → **review**; else keep only if
   both ≥ 0.6.
3. Review rows: `data/cache/jev_meta_vs_transcript_al_final_review.csv`.

AL reprocess (N=300): old both≥0.6 was keep 235 / skip 65; new is keep **240** /
skip **59** / review **1**. The six changes are the five cue/rule keeps above
plus Employee Recognitions → review.

## Read first

- `packages/llm/src/llm/typesafe/screen_transcripts.py`
- `packages/scrapers/src/scrapers/youtube/backfill_transcripts.py`
- `web_docs/docs/development/jev-meeting-kind-gate.md`
