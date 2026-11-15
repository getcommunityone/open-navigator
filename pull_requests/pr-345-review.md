---
pr: 345
branch: feat/246-data-center-job-claims
title: "feat(dc): DC-1.1 jobs claims split by phase, from meeting to page"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: general-purpose read-only subagent and coordinator; every finding reproduced in the code before it was written down
verdict: approve-with-nits
---

# PR Review: feat(dc): DC-1.1 jobs claims split by phase, from meeting to page

## Summary

The PR records every jobs claim made in an analyzed meeting, split into construction and operations, with the
speaker and the verbatim quote. It runs from the Part 1 prompt through a dbt staging view and the `job_claim` mart
(published to `public`) to `GET /api/data-centers/job-claims` and the `/data-centers` page.

The first review pass found two Important defects:
- the city filter could show an empty list under a correct label;
- the page counted only the claims it had loaded, as if they were the total.

It also found four Minor ones. All six are fixed in 9323651 with tests.

The SQL, API and page could not be run against the warehouse from this session. Verdict: **approve-with-nits**.
The remaining nits are the unverified database path and one timestamp slip in the cheaper model.

## Scope of Change

- Files changed: 20 (+1,754 / -2 at the first commit; the fixes add about 100 lines), excluding the generated
  `api.types.ts` from the count.
- Areas touched: prompts, dbt_project (staging, marts, macros, contracts, publish), api, tests, web_app, web_docs.
- Commits:
  - 5562e64 feat(dc): DC-1.1 jobs claims split by phase, from meeting to page
  - 9323651 fix(dc): review fixes for job claims: city scope, real totals, one-sided figures
- Range reviewed: `origin/main..9323651`

## CI Status

| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | running on the fix commit at the time of writing |
| PR conventions | branch `feat/246-data-center-job-claims` and `Closes #246` meet the rule |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data in a served path:** clean.
  - Every figure on the page comes from the API. Unknown headcounts and dates show "Not stated" or "Dates not
    stated", never 0.
  - One-sided figures read "Up to N" or "At least N", never as exact.
  - Counts are the scope's real totals, and a cut list says so.
  - The only numbers in served code are HTTP status codes and limits.
- **Personal data:** clean. Speaker names are public meeting records. The frontend span records only the scope
  level, not the place.
- **Destructive or bulky data changes:** clean. The new tables come only from dbt, and nothing is deleted.

## Strengths

- **The dbt layer never guesses.** Guarded casts (`safe_json_casts.sql`) turn bad values into NULL, rows that break
  the rules stay in staging where warn tests count them, and the mart enforces a PK, an FK to `jurisdictions` and a
  phase CHECK.
- **The UI wording follows the contract exactly and is unit-tested.** It uses "Not stated", "Up to N", "At least N"
  and "Dates not stated", formats dates without timezone shifts, and never adds the two phases together.
- **The API is easy to test and safe.** `build_scope`, `_scope_where` and the two query builders are pure
  functions, all values are bound parameters, and a missing table returns an empty list. It is traced with
  OpenTelemetry.
- **The decisions and gaps are written down.** `data-center-jobs.md` records the choices (`person_id` left null, the
  link to `event_meeting` kept as a test) and says plainly what hasn't been checked against real data.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

- **Fixed in 9323651: the city filter didn't match like the rest of the site.**
  - Where: `api/routes/data_centers.py`.
  - What: `?city=` was an exact case-insensitive match on `jurisdiction_name`, while `meeting_browse` and
    `decision_browse` match a substring of `city` or `jurisdiction_name`. A scope carried over from another page
    could return nothing under a "Tuscaloosa" label.
  - Fix: `job_claim` now projects `city`, and the predicate is `(city ILIKE $n OR jurisdiction_name ILIKE $n)`.
    Tests updated.
- **Fixed in 9323651: the per-phase counts covered only the loaded page.**
  - Where: `DataCenters.tsx`.
  - What: the "(N claims)" header counted the first 100 rows.
  - Fix: the API returns `totals` per phase from a `GROUP BY phase` query over the same scope. The page shows them
    and adds "showing the latest N" when the list is cut. Test:
    `test_totals_count_the_whole_scope_not_just_the_page`.

### 🔵 Nits / suggestions (Minor)

- **Fixed: the prompt could turn "at least 200" into an exact 200.** "At least / more than N" now sets only
  `headcount_low`.
- **Fixed: `event_meeting_id` was a string on the wire.** It is now the mart's integer, required.
- **Fixed: the page label used the raw URL.** It now follows the scope the API applied, so `?state=Alabama` reads
  "Alabama".
- **Fixed: a stale comment** in `_schema_job_claim.yml` said the model wasn't published.
- **Open: one timestamp slip.**
  - What: on the made-up meeting, `gemini-3.5-flash-lite` put one claim 20 s before its transcript cue, so its
    "Hear it" link would start early.
  - Status: worth watching in the real-meeting comparison (#267).
- **Open: not run against the warehouse.** `dbt build --select +job_claim`, the API on real rows, and extraction on
  real meetings remain.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | #246 has the four parts plus dated contract refinements; branch `feat/246-…`; `Closes #246`; the PR repeats the Attributes table |
| Conventional Commits | ✅ | Both commits, with the co-author trailer |
| No fabricated data | ✅ | See the scans |
| New Python in `packages/` | n/a | API code is in `api/`, as the layout says |
| dbt for transformations | ✅ | JSON extraction in dbt staging; layers run bronze → staging → mart |
| Naming | ✅ | `state_code` and `state` both; entity name `job_claim`; no `dim_`/`fact_` |
| Keys | ✅ | PK `job_claim_id`; FK `jurisdiction_id` → `jurisdictions`; `event_meeting` as a warn test, with the reason documented; ODCS contract generated |
| Scope label matches filter | ✅ | URL → query → label, with the label following the API's applied scope; broaden control |
| Match evidence on filtered tiles | ✅ | Each claim tile shows its verbatim quote |
| Docs | ✅ | `web_docs/docs/development/data-center-jobs.md` |
| Telemetry | ✅ | API spans, and a frontend `withSpan` on the data load |
| Tests | ✅ | API 20, frontend 36, plus the existing llm 165 |

## Test Coverage

Run locally on 9323651:

- **API:** `tests/test_api_data_center_job_claims.py`, 20 passed. `from api.app import app` and `import main`
  succeed.
- **Frontend:** `npx tsc --noEmit` clean; `npx vitest run` 36 passed; eslint clean; `npm run build` passes.
- **dbt:** `dbt parse` passes.
- **Contracts:** `python -m models.odcs --check` reports 46 contracts current.
- **Docs:** `web_docs` build succeeds (on the first commit).
- **`pytest packages/llm`:** 165 passed.
- **Live extraction:** on the made-up meeting, both default models returned the correct claims (see the PR
  description).

## Verdict

**approve-with-nits.** Merge once the required checks are green. Run `dbt build --select +job_claim` against the
warehouse at the first chance, and re-analyze meetings with the new prompt so `job_claims` fills in.
