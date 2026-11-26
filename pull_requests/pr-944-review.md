---
pr: 944
branch: feat/933-dc-uncontested-decisions
title: "feat(data-centers): show the decisions meetings took on data center items, debated or passed without debate"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: general-purpose subagent (read-only) and coordinator
head_sha: be296f15
verdict: approve-with-nits
---

# PR Review: feat(data-centers): show the decisions meetings took on data center items

## Summary

This PR adds `data_center_decision`, one row per decision on a data center item: debated decisions from `event_decision`
and decisions taken up without debate from `event_uncontested_item`. It also adds `GET /api/data-centers/decisions` and a
**Decisions** screen in the Data Story.

The first review found two important problems:
- **Double counting.** One action listed in both of the analysis's lists was counted twice: Wayne County's ordinance and
  Spalding County's FLUME item.
- **Wrong wording.** "Passed without debate" was false for tabled, denied and noted items.

It also found four minor ones. All six are fixed in `be296f15` and re-verified. Two broader issues were split out as #945
(looser data center matches) and #946 (site-wide city substring filter). Verdict: **approve-with-nits**. The nits are the
two follow-ups and the hub count row (below).

## Scope of Change

- Files changed: 16 (dbt 4 + contracts 2, api 1 + test 1, hosting 1, web_app 6, web_docs 2), plus this review
- Areas touched: dbt_project, api, packages/hosting, web_app, web_docs
- Commits:
  - 9d1d035e feat(data-centers): show the decisions meetings took on data center items, debated or passed without debate
  - 45e2630e docs(pr-944): auto-write rubric review [skip review] (CI bot)
  - be296f15 fix(data-centers): count one action once, say "taken up without debate", and keep to the preferred analysis
- Range reviewed: `origin/main...be296f15`

## CI Status

| Check | Status |
|---|---|
| Required checks | see PR checks on the head |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: clean. Votes come only from a tally with both sides as whole numbers, an uncontested vote stays as said,
  and a missing date stays null. An unloaded table gives null counts and "not loaded yet", never 0.
- Personal data: clean (public meeting records).
- Destructive or bulky changes: none.

## Strengths

- The rule for what counts lives in dbt (a test asserts the route has no regex), and the API keeps `available:false`
  separate from zero.
- Every number on the new screen traces to a row, and each dot links to its decision page or recording.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

All fixed in `be296f15`:

1. `data_center_decision.sql`: `union all` with no cross-source de-duplication counted one action twice. **Fixed:** an
   uncontested row is dropped when a debated data center decision in the same meeting reads like it (`word_similarity`
   at least 0.4). Measured on the 3 pairs: the 2 duplicates scored 0.44-1.00 and were dropped; the real second action
   scored 0.18-0.30 and was kept. The threshold and sample are documented in the SQL and in
   `data-center-who-spoke-up.md`.
2. "Passed without debate" was the label for tabled, denied and noted items. **Fixed:** the copy now says "taken up
   without debate", the group is "Without debate", and each dot's title carries the recorded `outcome`. A test asserts
   that a tabled item's title reads "… · Tabled" and that the headline never says "passed".

### 🔵 Nits / suggestions (Minor)

3. Some regex matches aren't data center decisions (a vendor name, public comment, procedural items). **Split out** as
   #945.
4. Debated rows skipped the preferred-analysis filter. **Fixed:** both sources join `int_preferred_event_analysis`; 3
   rows from superseded analyses dropped.
5. An unloaded mart read as "no data, broaden". **Fixed:** "Decisions on data center items are not loaded yet." (tested).
6. City filter by substring (Jefferson matches Jefferson County). It's the existing pattern on every data center endpoint,
   so it's **split out** as #946.
7. Two sentence orders. **Fixed:** one shared `decisionsSentence`, debated first.
8. Docs missed the screen in the meeting-sourced list. **Fixed.** The hub's count row (`COUNT_CHARTS`) does not include
   decisions; the story screen is the surface this PR adds.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `feat/933-…`; `Closes #933`; four parts; follow-ups #945, #946 |
| Conventional Commits | ✅ | |
| No fabricated data | ✅ | see scans |
| dbt for transformations | ✅ | rule and de-duplication in dbt; the route only reads |
| Naming | ✅ | `state_code` and `state`; no dim/fact |
| Keys | ✅ | PK `data_center_decision_id`, enforced FK to `event_meeting`; ODCS contract |
| Scope label matches filter | ✅ (see #946) | same `?state=&city=` handling as the other screens |
| Match evidence on filtered tiles | ✅ | each dot is the decision's own headline (which names the data center) and outcome |
| Docs | ✅ | `guides/data-stories.md`, `development/data-center-who-spoke-up.md` |
| Telemetry and logging | ✅ | OTel span `data-centers.decisions`; frontend `withSpan` |
| Tests | ✅ | 6 API tests; vitest for finding, chart, screen text and not-loaded |

## Test Coverage

- dbt on the local warehouse: 49 decisions (40 debated, 9 without debate); `dbt test` 13/13. The endpoint SQL against
  `public.data_center_decision` at national, GA and Camden scope.
- `pytest` (API + hosting + datamodels): 98 passed before the fixes, and 52 passed for the re-run subset (API + hosting).
- `npx vitest run`: 379 passed. `tsc --noEmit` clean, `vite build` OK, docs build OK, `models.odcs --check` current.
- Not covered: a screenshot in the running site (the local API process runs older code).

## Verdict

**approve-with-nits**: merge when the required checks are green; #945 and #946 follow.
