---
pr: 580
branch: fix/472-future-meeting-dates
title: "fix(dbt): a future video date becomes an unknown meeting date for data center mentions"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: fix(dbt): a future video date becomes an unknown meeting date for data center mentions

## Summary
The PR makes `data_center_meeting_mention.meeting_date` NULL when the video's date is later than the build date
(the wrong source date, such as 2029-10-12, from #472), and adds an error-severity singular dbt test that no
mention has a `meeting_date > current_date`. The change is one `CASE` in the mart's `videos` CTE plus
description, contract and test files. It does what the issue asks: the type and meaning stay the same, and an unknown
date already sorts last in the API (`ORDER BY m.meeting_date DESC NULLS LAST`, tested) and shows "Date not listed"
in the UI. The PR's numbers match the local warehouse (6,323 rows, 0 future, 254 null, latest 2026-11-13), and all
required CI checks pass. Verdict: approve-with-nits. The one real gap is test strength: the new data test passes
today whether or not the fix is present, so it won't catch a regression until bad source data comes back; a dbt unit
test would pin the `CASE` down.

## Scope of Change
- Files changed: 4 (+17 / -3, no generated files)
- Areas touched: dbt_project (mart model, schema.yml, singular test, ODCS contract)
- Commits:
  - `013b9651` fix(dbt): a future video date becomes an unknown meeting date for data center mentions
  - `de6e1b2a` chore(dbt): regenerate the data_center_meeting_mention ODCS contract
- Range reviewed: `0ba4fcd2..de6e1b2a` (merge base with `main`; the PR's base is `main`, not stacked)

## CI Status
Read on head `de6e1b2a`.

| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Detect Docker-relevant changes | success |
| Docker Build Test (Full Stack) | skipped (not required; no Docker files changed) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. No keys, URLs, tokens or `.env` content in the diff.
- **Fabricated data in a served path:** clean. The change removes a wrong value and leaves it empty; it invents
  none. The PR's example date (2029-10-12) is in a SQL comment and the PR text, not in a served path.
- **Personal data:** clean. Public meeting videos only.
- **Destructive or bulky data changes:** clean. No deletion, no large files. The model is a dbt table rebuilt by dbt
  (`materialized: table`); nothing was changed in the warehouse outside dbt. I ran only read-only queries.

## Strengths
- Smallest possible change in the right layer for this mart: the future date is dropped where the column is
  defined, so every reader of the mart (`/api/data-centers/meeting-mentions`, the project timeline, the Neon sync)
  gets the same value.
- "Unknown is better than wrong" is applied the way `CLAUDE.md` asks. The row, its title and its verbatim evidence
  are kept; only the date is dropped.
- Consumers already handle NULL. The mentions endpoint sorts `meeting_date DESC NULLS LAST`
  (`tests/test_api_data_center_meeting_mentions.py:118` asserts it); `build_timeline` sorts undated items after dated
  ones; `DataCenters.tsx` renders `Date not listed`. I traced all three, so the PR's "no API change needed" holds.
- Column type, name, `data_type: date` and the contract are unchanged. The description in `schema.yml` and the
  ODCS file say the same thing, and the ODCS file was regenerated.
- The PR body says `Closes #472`, has a before/after table, and lists what wasn't done (Neon not rebuilt).
- Conventional Commit subjects with the co-author trailer; branch name is `fix/472-...`.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`dbt_project/tests/assert_data_center_meeting_mention_no_future_dates.sql`: the test doesn't fail without the
   fix, so the `CASE` has no regression test.** The singular test reads the built mart, so it only fails when future
   source dates are present at build time. *Verified (read-only):* none of the videos in
   `gold.data_center_meeting_mention` has a source `event_date > current_date` now (0 of them; the 5 future-dated
   videos in `gold.event_youtube_with_jurisdiction` have no mention rows, and the 9 rows the PR nulled, video
   `v88gTVtscg0`, now carry `2026-10-13` in the source). So with the `CASE` reverted and the mart rebuilt, the test
   would still pass today. The test is a useful tripwire for the day a future date returns, but "a behaviour change
   has a test that would fail before it" (rubric) isn't met. The repo already uses dbt `unit_tests` on marts
   (`_schema_data_center_project.yml:458`). *Fix:* add a unit test on `data_center_meeting_mention` with a mocked
   `event_youtube_with_jurisdiction` row dated in the future (expect `meeting_date` null) and one dated in the past
   (expect it kept). The mart reads about eight refs, so the given block needs those inputs.

### 🔵 Nits / suggestions (Minor)
2. **`data_center_meeting_mention.sql:35` vs the issue's "Read first".** Issue #472's *Done when* says the future
   date is treated as unknown "in staging"; the fix is in the mart, and the issue points at
   `stg_event_youtube_transcript__data_center.sql`, which doesn't exist in this tree (the only data-center staging
   model is `stg_data_center_companies__org`). The mart is the sensible place for this model, since the future
   date originates in `event_youtube_with_jurisdiction`. But `AGENTS.md` asks for a dated line on the issue when the
   plan changes, and the upstream value is still wrong for any other reader of that table. *Fix:* add a dated line
   on #472 saying the guard lives in the mart (and, if wanted, open an `action-item` for the source dates).
3. **`data_center_meeting_mention.sql:35` and `:157`: the date is cast twice.** `event_date` is already `date` in
   `gold.event_youtube_with_jurisdiction` (checked in `information_schema`), so `event_date::date` is a no-op, and
   the outer `e.meeting_date::date` was there before. Harmless; the `CASE` can use `event_date` directly.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `fix/472-future-meeting-dates`; body says `Closes #472`; #472 has Problem, Done when, Contract and Read first (labels `bug`, `action-item`). See nit 2 for the staging/mart wording |
| Conventional Commits | Yes | Both subjects fit; co-author trailer present |
| No fabricated data | Yes | The change nulls a wrong value; no values added |
| New Python in `packages/` | n/a | No Python changed |
| dbt for transformations | Yes | The logic is in dbt SQL, in the mart |
| Naming | Yes | No new names; `state_code` + `state` untouched |
| Keys | Yes | PK and FKs on the mart are unchanged |
| Calendar years | n/a | A full `date`; serialized as an ISO string by the API |
| Scope label matches filter | n/a | No UI change |
| Match evidence on filtered tiles | n/a | Evidence untouched |
| Docs | n/a | No new docs; the column description is updated in `schema.yml` and the contract |
| Telemetry and logging | n/a | No API or script change |
| Tests | Partial | New singular test, but it doesn't fail without the fix today (finding 1) |
| Shared libraries | n/a | Nothing in `packages/` |

## Test Coverage
- **Run locally** (worktree code via `PYTHONPATH`; dbt read-only):
  - `pytest tests/test_api_data_center_meeting_mentions.py`: 7 passed.
  - `dbt ls --select data_center_meeting_mention+`: the dependents are `data_center_project_mention` and the model's
    own generic tests. No other model reads the mart's `meeting_date` (the API reads it and
    `data_center_project_mention` is joined for the date in the timeline query).
  - `dbt compile` of the mart and the new test: compiles; `current_date` appears as intended.
  - Not run: `dbt run|test|build` (not allowed here). I ran the test's query logic by hand instead (see below).
- **Warehouse (read-only SELECTs, local `open_navigator`):** `gold` and `public` copies of
  `data_center_meeting_mention` both show 6,323 rows, 0 with `meeting_date > current_date`, 254 NULL, latest
  2026-11-13. This matches the PR's "after" column; the "before" column (9 future, 245 null, 2029-10-12) can't be
  reproduced now, because the source date for those 9 rows has since changed (see finding 1).
- **Claims I could not confirm:** "the new test passes" (I can't run `dbt test`; the equivalent query
  `select ... where meeting_date > current_date` returns 0 rows on both copies). "Neon not rebuilt" is outside what I
  can check.
- **Covered:** NULL ordering in the API (`NULLS LAST` asserted in the SQL text). **Not covered:** the `CASE`
  itself (finding 1). Note for the author: the 9 NULL rows will get a date on the next rebuild, because the source
  now says 2026-10-13 for that video.
- `ruff`, `tsc` and `pytest` for packages: not applicable (no Python or TypeScript changed).

## Verdict
**approve-with-nits.** The fix is correct, small and verified against the warehouse, and CI is green. Before or soon
after merge: add a dbt unit test for the `CASE` (finding 1), and add the dated line on #472 about the mart vs
staging (nit 2). Nit 3 is optional.
