---
sidebar_position: 40
title: Batch analysis light vs full
description: Run all covers stages 1–5 (through reports light); analysis/reports full are opt-in with multi-select eligibility filters (#755).
---

# Batch analysis light vs full

Decision draft 2026-11-22. Parent issue
[#755](https://github.com/getcommunityone/open-navigator/issues/755). Builds on
[Jev-light cascade](./jev-light-cascade-design.md) and today’s Batch Job Status
stages / Run all.

## Problem

**Run all** and the stage list treat Gemini analysis + reports as one pass.
Operators want cheap **light** coverage on every captioned video in the funnel,
and expensive **full** analysis/reports only on a **chosen subset** (multi-select
filters such as has-decisions and interestingness). Full must not run by
default.

## Decision

### Stages (seven)

| # | Stage | Launch step (API) | In **Run all**? |
|---|--------|-------------------|-----------------|
| 1 | Discover | `discover` | Yes |
| 2 | Videos | `catalog` | Yes |
| 3 | Transcripts | `captions` | Yes |
| 4 | Analysis light | `analyze-light` | Yes |
| 5 | Reports light | `reports-light` | Yes |
| 6 | Analysis full | `analyze-full` | **No** |
| 7 | Reports full | `reports-full` | **No** |

**Run all** = 1 → 5 only (discover → catalog → captions → analyze-light →
reports-light). Same single `launch_all_*.log` chain as today, with light
analyze/report instead of today’s combined Part 1+2 “full-ish” pass.

**Each** (per-jurisdiction) stays catalog/captions/light-oriented unless we
explicitly extend it later; it does **not** run full by default.

### Light vs full (product meaning)

| | Light | Full |
|---|--------|------|
| Prompt | `policy_analysis_lite.md` (or successor short Part 1) | Current `policy_analysis_part_1.md` (deep) |
| Report | Short digest / lite Part 2 (or truncated Part 2) | Current `policy_analysis_part_2.md` |
| Model | Flash-Lite / free-tier friendly | Paid Flash (or configured full model) |
| Stamp | Prefer distinct paths or metadata so stage counts split (see Contract) | Distinct from light |
| Who | Broad transcript set (Jev meeting gate still allowed) | Subset of videos that already have **analysis light**, matching filter checkboxes |

### Full eligibility — multi-select checkboxes

On **Analysis full** and **Reports full** Run controls, show a **multi-select
checkbox group** (not a single dropdown). Operator may check zero or more;
**OR** semantics across checked filters (match any). Unchecked filters are
ignored.

**v1 filter keys (checkbox labels):**

| Key | Checkbox label | Default checked? | Match rule (v1) |
|-----|----------------|------------------|-----------------|
| `has_decisions` | Has decisions | **Yes** | Jev `has_decisions_p ≥ 0.5` **or** light analysis already extracted ≥1 decision |
| `interestingness` | High interestingness | **Yes** | Among light-analyzed videos in scope, `interestingness_score` in top **20%** **or** score ≥ tunable floor (seed/env; document default in schema) |
| `data_center` | Data-center mention | Yes if Filter cohort is `data_centers`; else No | Jev `mentions_data_center_p ≥ 0.5` |
| `force` | (later) Force video list | No | Explicit IDs — out of v1 UI |

**Require light first:** full never selects a video without a successful
**analysis light** stamp (except a future force list).

**Reports full:** only videos with **analysis full** (and still satisfying the
same checkbox set if re-applied, or inherit the set from the last analyze-full
launch stored on the launch meta).

**Empty selection:** if the operator unchecks all boxes, disable Run (or no-op
with a clear message) — do not interpret as “everyone.”

### UI sketch (Batch Job Status)

- Stage list shows all seven rows; 6–7 have **Run** but are **not** driven by
  Run all.
- Expanding 6 or 7 reveals:
  - Checkbox group (multi-select) with the v1 filters above
  - Short helper: “Full runs only on videos that already have analysis light and
    match any checked filter.”
  - Run button for that step only
- Persist last checkbox set in `localStorage` (per browser) so re-clicks keep
  defaults; send selected keys on `POST /api/batch-jobs/launch` as
  `full_filters: string[]`.

### Launch contract

```http
POST /api/batch-jobs/launch
{
  "step": "analyze-full",
  "states": ["AL", ...],
  "cohort": "data_centers",
  "n": 25,
  "parallel": 4,
  "full_filters": ["has_decisions", "interestingness"]
}
```

- `full_filters` required (non-empty) when `step` is `analyze-full` or
  `reports-full`; ignored otherwise.
- `analyze-light` / `reports-light` ignore `full_filters`.
- Shell / CLI: map light to `--prompt-file …/policy_analysis_lite.md` and a
  light report prompt; full to current Part 1 / Part 2; apply SQL/Jev filter
  from `full_filters` before the video loop.

### Stage progress

- **Analysis light / reports light:** count light stamps (new columns or path
  convention — prefer explicit `policy_analysis_light_at` /
  `policy_report_light_at` if we can migrate; interim: path suffix `_light` or
  `pipeline` tag in bronze). Grain remains one row per video.
- **Analysis full / reports full:** count full stamps only; denominator = videos
  with light analysis in scope (or full-eligible estimate), never the full
  transcript pile.
- Do **not** invent counts (No Fabricated Data).

### Out of scope (follow-ups)

- Blurb-only Jev stage (#705) as a separate stage 3.5
- Force-ID UI
- Auto-scheduling full after light
- Changing interestingness formula (use existing `item_interestingness`)

## Alternatives considered

1. **Single analyze step + mode flag** — easier to mis-click full; weaker stage
   progress. Rejected for operator clarity.
2. **Hard-coded Jev-only full gate** — no interestingness checkbox. Rejected;
   operators want multi-select choices.
3. **Keep today’s Part 1+2 as “light”** and add full later — faster ship but
   wrong names on the dashboard. Rejected once Run all is redefined as 1–5.

## Done when (implementation)

- Design this page linked from #755
- Seven stages on Batch Job Status; Run all = 1–5
- Full Run UI = multi-select checkboxes with v1 defaults
- Launch API accepts `full_filters`; full steps refuse empty selection
- Light/full stamps distinguishable in stage report
- Docs + tests for filter OR semantics and Run all composition
