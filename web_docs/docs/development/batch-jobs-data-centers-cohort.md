---
sidebar_position: 47
title: Batch jobs data-centers cohort
description: Design for a Data centers launch cohort on the YouTube pipeline dashboard (left→right scope with Priority / All).
---

# Batch jobs data-centers cohort

Decision recorded 2026-11-21. Issue
[#676](https://github.com/getcommunityone/open-navigator/issues/676). Extends
the YouTube pipeline controls on `/admin/batch-jobs` so an operator can run
Discover → Reports for **data-center jurisdictions only**, with the same
left→right scoping used for priority states.

## Problem

The batch-jobs dashboard scopes launches by US state only (`Priority states` /
`All states` / one state). Operators who need the YouTube pipeline stages for
data-center governments must leave the UI and use separate CLIs
(`survey_meeting_sources --data-center-sites`, platforms `--data-center`, etc.).
There is no way to hit **▶ Run all** or a per-stage **Run** for the DC set from
the dashboard.

## Goal

Add **Data centers** as a third cohort in the existing left-hand scope dropdown.
Cascading controls (left → right): the cohort limits which states appear in the
state dropdown; launches and stage progress both honor **cohort ∩ state**.

## Chosen approach

**Cohort flag on the existing launch path** (not a separate DC CLI launcher, not
a UI-resolved `jurisdiction_ids[]` payload).

- Frontend sends `cohort` + `states[]` on `POST /api/batch-jobs/launch`.
- API sets `COHORT` and resolved `STATES` on the wrapper script environment.
- Jurisdiction listing filters to cohort membership ∩ states for every step that
  walks places (catalog, captions, analyze, each, all) and for discover / backfill.

## UI (left → right)

1. **Filter** (labeled control, always visible when launch is enabled) — the
   launch cohort:
   - `priority` — Priority states (`AL, GA, IN, MA, MT, WA, WI`)
   - `data_centers` — site belt ∪ meeting-mention jurisdictions
   - `all` — All states (50 + DC)

2. **Scope** (to the right of Filter): options are only states valid for the
   selected filter.
   - Priority → fixed priority list
   - Data centers → distinct `state_code`s that have ≥1 DC jurisdiction (from API)
   - All → full `STATE_CODES`
   - First option: **All in filter** (empty `states` / every state in the left set)

3. If the current state is not in the new filter’s list when Filter changes,
   reset Scope to **All in filter**.

4. Run button labels / confirmations name the cohort, e.g.
   `▶ Run all · data centers` or `▶ Run all · data centers · AL`.
   Scope chip next to the title mirrors the same filter.

## Data: Data centers membership

Union of distinct `jurisdiction_id`:

1. **Site belt** — `intermediate.int_data_center_site__jurisdiction`
2. **Mention widen** — `public.data_center_meeting_mention`

State options for the cohort = distinct `state_code` for those jurisdictions
(joined through the usual jurisdiction / events path the batch planner already
uses, or an equivalent lookup that yields a 2-letter code per JID).

Out of scope for this cohort: company town-hall search
(`ingestion.data_centers.video_search`) and agenda-platform CLIs — those remain
separate entry points.

## API contract

### `GET /api/batch-jobs/cohorts`

Returns the state lists the UI needs so DC states are not hard-coded:

```json
{
  "priority": ["AL", "GA", "IN", "MA", "MT", "WA", "WI"],
  "data_centers": ["AL", "GA", "..."],
  "all": ["AL", "AK", "...", "DC"]
}
```

Grain: one response; each array is sorted unique 2-letter state codes.

### `POST /api/batch-jobs/launch`

Existing body plus:

| Field | Type | Notes |
|---|---|---|
| `cohort` | `"priority" \| "data_centers" \| "all"` | Default `"priority"` for back-compat |
| `states` | `string[]` | Empty = all states in cohort; otherwise intersect with cohort |
| `step`, `n`, `parallel` | unchanged | |

Behavior:

- Resolve launch states = `states` if non-empty else full cohort state list;
  every code must be in the cohort’s allowed set.
- Empty cohort ∩ state → **400** with a clear message (UI shows it in the
  launch message bar).
- Set env `COHORT=<cohort>` and `STATES=<resolved>` on the wrapper (and pass
  equivalent args for discover / backfill so they never silently go national
  when `data_centers` is selected).
- Missing warehouse objects needed for the DC union → **500**; never fall back
  to all jurisdictions.

### Progress / stream

Stage totals and detail tables on `/admin/batch-jobs` follow the same
**cohort ∩ state** filter as launches. Selecting Data centers must not show
national discover progress while launching only DC places.

The status / SSE (or refetch) path the page already uses gains an optional
`cohort` query param (same enum). When omitted, behavior stays as today
(state filter only) for back-compat.

## Errors

| Case | Response |
|---|---|
| Unknown `cohort` | 400 |
| State code not in cohort | 400 |
| Cohort ∩ states empty | 400 |
| DC membership query fails / table missing | 500, no silent broaden |

## Tests

- **API:** cohort validation; DC membership = site ∪ mention; launch env includes
  `COHORT` + resolved `STATES`; empty intersect → 400; `GET /cohorts` shape.
- **Frontend:** cohort change resets invalid state; state `<option>`s limited by
  cohort; launch payload sends `cohort` + correct `states`; Run label reflects
  cohort.
- **Script / helper:** `COHORT=data_centers` restricts jurisdiction listing to the
  DC set (intersected with `STATES`).

## Files to change (expected)

- `web_app/src/pages/BatchJobStatusPage.tsx` — cohort UI, cascade, launch labels
- `web_app/src/api/batchJobs.ts` — `cohort` on launch; `fetchCohorts`
- `api/routes/batch_jobs.py` — `LaunchRequest.cohort`, `/cohorts`, env wiring
- `packages/scrapers/scripts/youtube_run_priority_states_last_n.sh` (and
  jurisdiction list helper it calls) — honor `COHORT`
- Discover / backfill entry points invoked by launch — same cohort ∩ states
- Tests under `tests/` / package tests as appropriate

## Read first

- `CLAUDE.md` — Frontend UX scope label must match the active filter; no
  fabricated data
- `web_docs/docs/development/data-center-agenda-first-design.md` — site belt +
  mention widen definition
- `api/routes/batch_jobs.py`, `web_app/src/pages/BatchJobStatusPage.tsx`
