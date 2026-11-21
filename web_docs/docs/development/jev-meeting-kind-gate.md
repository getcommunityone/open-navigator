---
sidebar_position: 33
title: Jev meeting-kind analysis gate
description: Calibrate a government_meeting probability floor and skip non-meetings before Gemini, alongside the existing decisions skip.
---

# Jev meeting-kind analysis gate

Decision record for screening captioned videos with TypeSafe Jev’s `meeting_kind`
probabilities before paid Gemini analysis. Builds on
[Jev transcript screening](./jev-transcript-screening.md) (#424). Approved in design
review 2026-11-21.

## Problem

The batch Jobs Transcripts stage denominates coverage against
`intermediate.int_events_union` (~270k candidate videos). Analyses sit far behind
landed transcripts (~6.8k / ~179k). Many captioned videos are not official
governing-body meetings (press conferences, ceremonies, trainings, non-government).
Sending them to Gemini wastes quota and time. Jev already stores
`meeting_kind` and `meeting_kind_probabilities` on
`bronze.bronze_transcript_screen_jev`, but the only analysis skip today is
`--skip-jev-below` on `has_decisions_p`.

## Goal

Screen transcripts that already exist, calibrate a floor **T** on
`P(government_meeting)`, then optionally leave non-meetings out of Gemini submit.
Keep the existing decisions skip as a separate, independent flag.

## Decisions

| Choice | Decision |
|---|---|
| Where to screen | Captioned videos only (Option A) — Jev needs transcript text; this gates analysis, not caption fetch |
| Primary filter | `P(government_meeting) >= T` (probability floor), not hard top-label alone |
| How to pick T | Calibrate first against videos Gemini has already analyzed |
| Flags | Both independent: `--skip-jev-meeting-below T` and existing `--skip-jev-below P` |
| Implementation shape | Thin gate + separate calibrate report (Approach 1) |
| Defaults | Neither skip flag on; unscreened videos are never skipped |
| Out of scope | Pre-transcript title/channel heuristics, dashboard “screened” stage, deleting/changing transcripts, replacing Gemini |

## Contract

### Unchanged

- Table `bronze.bronze_transcript_screen_jev` (one row per `video_id`): existing
  columns including `meeting_kind`, `meeting_kind_probabilities` (jsonb),
  `has_decisions_p`, `question_version`, `screened_at`.
- CLI `python -m llm.typesafe.screen_transcripts` (screen / `--dry-run` / `--rescreen`).
- `batch_backlog submit --skip-jev-below P` — skip when current-version
  `has_decisions_p < P`.

### New

**Calibrate mode** (`python -m llm.typesafe.screen_transcripts --calibrate`):

- Input: warehouse URL; optional `--state` / `--limit`. Does not call Jev.
- Join: current `question_version` rows in `bronze.bronze_transcript_screen_jev` to
  `bronze.bronze_event_youtube` where `policy_analysis_at IS NOT NULL` (already
  sent through Gemini — the proxy for “we treated this as worth analyzing”).
- Output: for each candidate T in a fixed grid (`0.5`, `0.6`, `0.7`), counts of
  those joined videos that would be kept vs skipped at T, i.e. the false-skip
  rate if we had gated before analysis.
- Ops records the chosen T in this page under **Chosen threshold** (below) when
  calibration finishes — do not invent a production T in code defaults.

**Gate** on `llm.gemini.batch_backlog submit`:

- `--skip-jev-meeting-below T` (float, opt-in, default unset).
- Skip set: `video_id` where `question_version` is current and
  `(meeting_kind_probabilities->>'government_meeting')::float < T`.
- Null / missing probability ⇒ do not skip (same spirit as unscreened).
- Independent of `--skip-jev-below`; if both are set, a video is skipped if it
  fails either gate.
- Unscreened videos and older `question_version` rows are never in the skip set.
- Skipped videos are left out and counted in logs; not stamped failed; transcripts
  unchanged.

### Rollout

```bash
# 1. Calibrate (needs screens already joined to analyzed videos)
.venv/bin/python -m llm.typesafe.screen_transcripts --calibrate --state AL --limit 300
# 2. Record T under Chosen threshold below, then screen more of the captioned backlog
.venv/bin/python -m llm.typesafe.screen_transcripts --state AL --limit 500
# 3. Gate Gemini submit (either/both flags)
.venv/bin/python -m llm.gemini.batch_backlog submit --state AL --skip-jev-meeting-below T --dry-run
```

1. Run calibrate on a few hundred already-analyzed videos (priority states first).
2. Write the chosen T into **Chosen threshold** on this page.
3. Screen the captioned backlog state-by-state with `screen_transcripts`.
4. Submit analysis with `--skip-jev-meeting-below T`; add `--skip-jev-below` only
   when a second cut on decisions is wanted.

## Chosen threshold

**T = 0.6** (set 2026-11-21).

- Sample: 300 AL videos with `policy_analysis_at` already set, screened with
  current `question_version` (`--state AL --analyzed-only --limit 300`).
- Kind mix: 240 `government_meeting`, 35 `government_other`, 25 `not_government`.
- At T=0.6: **keep 239 / skip 61**. Skips are 35 other + 25 not-government +
  **1** labeled `government_meeting` with `P < 0.6`. Keeps are all
  `government_meeting`. So among top-label meetings, false-skip is ~0.4% (1/240);
  the ~20% “false-skip vs historically analyzed” rate is mostly correct drops of
  non-meetings the old pipeline still analyzed.
- T=0.5 / 0.7 differ by only a few rows (curve is flat below 0.5).

## Testing

- Unit: parse `--skip-jev-meeting-below`; skip-set query returns only current
  `question_version` rows below T; unscreened / null prob excluded; union with
  decisions skip when both flags set.
- Calibrate: dry join over fixture rows prints per-T counts (no live Jev call).
- No change to Gemini prompt or transcript tables.

## Read first

- [Jev transcript screening](./jev-transcript-screening.md)
- `packages/llm/src/llm/typesafe/screen_transcripts.py`
- `packages/llm/src/llm/gemini/batch_backlog.py`
- `packages/llm/tests/test_typesafe.py`
