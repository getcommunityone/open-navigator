---
sidebar_position: 39
title: Jev-light cascade (screen, blurb, Gemini)
description: Cheap coverage path — Jev screen with topic flags for everyone, short blurb for keepers, full Gemini only for high-value keepers.
---

# Jev-light cascade (screen, blurb, Gemini)

Decision record approved 2026-11-22 (Approach A + option 3 blurb). Parent issue
[#702](https://github.com/getcommunityone/open-navigator/issues/702). Builds on
[Jev transcript screening](./jev-transcript-screening.md),
[Jev meeting-kind analysis gate](./jev-meeting-kind-gate.md), and
[Jev metadata screen and transcript scale-out](./jev-meta-and-scale-design.md).

## Problem

Full Gemini Part‑1 on every captioned video in the data-centers cohort is on the
order of **$85–$120** for the pending backlog (token medians × paid
`gemini-2.5-flash-lite` rates; see usage logs under `data/logs/llm_usage`).
Prepaid Gemini keys hit HTTP 402 while Jev screening is ~20× cheaper per video
and already answers meeting kind / decisions / data center. Jev **cannot**
write summaries ([TypeSafe](https://www.shipwithjev.com/blog/can-jev-summarize));
YouTube’s uploader `description` is only present ~half the time and often short
boilerplate — not a meeting digest. We need structured coverage + a weak blurb
without paying Part‑1 for every transcript.

## Decision (Approach A)

| Stage | Who | What | Model |
|---|---|---|---|
| **1 — Screen** | Every captioned video (scale via [#661](https://github.com/getcommunityone/open-navigator/issues/661)) | Existing three questions **plus** light topic Noul flags in the **same** Jev request | `jev-1.14.0` |
| **2 — Blurb** | **Keepers only** (keep-score ≥ 0.6) | One short generative blurb (1–2 sentences) | Cheap chat: `deepseek-flash` or `gemini-2.5-flash-lite` |
| **3 — Full analysis** | **High-value keepers only** | Existing Part‑1 / Part‑2 pipeline | Gemini Flash-Lite (current) |

**Keep-score** (unchanged): `P(government_meeting) + P(town_hall)`. Default gate
threshold **T = 0.6** via `--skip-jev-meeting-below 0.6`. Unscreened videos are
**never** skipped by the gate (same contract as today).

**Why pack topic flags into stage 1:** Jev prices **input** tokens; questions are
tiny next to transcript chunks. A second Jev pass over the same state for
keepers would mostly re-pay the state. Put light flags on the first request.

**Why blurb only for keepers:** Generation is the expensive step relative to Jev.
Non-keepers get flags (and optional YouTube description) only — no chat call.

**High-value for stage 3 (v1 rule):** keeper **and**
(`mentions_data_center_p` ≥ 0.5 **or** `has_decisions_p` ≥ 0.5), unless an
operator forces full analyze. Tune later; do not invent tighter thresholds
without a measured cohort rate.

## Light topic flags (same request)

Add Noul questions alongside the existing three. Exact wording lives in
`screen_transcripts.QUESTIONS` ([#703](https://github.com/getcommunityone/open-navigator/issues/703)):

| Key | Intent |
|---|---|
| `mentions_zoning` | Zoning, land use, site plan, special exception, annexation |
| `mentions_budget` | Budget, tax, millage, bond, appropriation, contract spend |
| `mentions_housing` | Housing, affordable housing, zoning for residential density |
| `mentions_environment` | Water, sewer, power/utilities, environmental impact (incl. data-center utilities) |

`QUESTION_VERSION` **must** bump. Rescreen policy: new columns nullable until
rescreened; skip helpers that only read keep-score remain valid on old rows.
Optional `--rescreen` already exists for forcing a new version.

## Blurb storage ([#705](https://github.com/getcommunityone/open-navigator/issues/705))

- **Table:** `bronze.bronze_transcript_blurb_light` (name locked here)
- **Grain:** one row per `video_id`
- **Columns (minimum):** `video_id` PK, `blurb_text` TEXT, `model` TEXT,
  `prompt_sha256` TEXT, `input_tokens` INT NULL, `output_tokens` INT NULL,
  `created_at` TIMESTAMPTZ
- **Usage stage:** `light_blurb`
- **Prompt:** “1–2 factual sentences about what this public meeting appears to
  cover; no invented votes, amounts, or names not supported by the excerpt.”
  Pass a truncated transcript (and YouTube description when present).
- **Failure:** leave no row (or do not overwrite a good row); UI shows
  unavailable — **never** fabricate prose (CLAUDE.md, No Fabricated Data).

## UI excerpt order

When full Part‑1 `meeting_summary` is absent:

1. Light `blurb_text` if present  
2. Else YouTube / event `description` if length ≥ 120 characters (tune in
   implementation; avoid 73-char median boilerplate)  
3. Else extractive transcript snippet (first usable window / keyword window)  
4. Else explicit empty / “No summary available”

When Part‑1 summary exists, it **wins** (current analyzed meeting UX unchanged).

Jev flags (kind, decisions, data center, topic Nouls) surface as badges/metadata
on light cards — not as a fake summary paragraph.

## Analyze launch wiring ([#704](https://github.com/getcommunityone/open-navigator/issues/704))

- Data-centers cohort analyze launches pass `--skip-jev-meeting-below 0.6`.
- Coordinate with [#661](https://github.com/getcommunityone/open-navigator/issues/661):
  screen DC captioned backlog before relying on the gate for savings.
- Log skip counts (sent / skipped / unscreened) so the dashboard is not “green
  running” while every call 402s for other reasons ([#699](https://github.com/getcommunityone/open-navigator/issues/699)
  billing UX is separate).

## Cost sketch (order of magnitude, not a quote)

| Path | Rough $/video | Notes |
|---|---|---|
| Jev screen (+ flags) | ~$0.0003–$0.001 | Same state as today’s screen |
| Keeper blurb | ≪ Part‑1 | One short chat call |
| Full Part‑1+2 | ~$0.012 median | From logged Flash-Lite usage |

Gate savings scale with the **fail** rate at T=0.6 on the DC cohort — measure
after #661; do not assume “90% pass.”

## Out of scope (v1)

- Foundry / Azure OpenAI provider wiring  
- Replacing Part‑1 fields (speakers, dollar amounts, quotes) with Jev  
- Meta caption-download gate ([#662](https://github.com/getcommunityone/open-navigator/issues/662)) — still Phase 3 of the meta/scale design  
- Changing Jev into a summarizer (impossible by product contract)

## Child issues

| Issue | Piece |
|---|---|
| [#703](https://github.com/getcommunityone/open-navigator/issues/703) | Topic flags on the screen request |
| [#704](https://github.com/getcommunityone/open-navigator/issues/704) | Wire meeting-kind gate into data-centers analyze |
| [#705](https://github.com/getcommunityone/open-navigator/issues/705) | Keeper blurb + storage + excerpt precedence |
| [#661](https://github.com/getcommunityone/open-navigator/issues/661) | Scale transcript screens (prerequisite for gate savings) |

## Read first

- `packages/llm/src/llm/typesafe/screen_transcripts.py`
- `packages/llm/src/llm/gemini/batch_backlog.py`
- `packages/llm/src/llm/usage/prices.yaml` (`jev-`, `gemini-2.5-flash-lite`)
