---
pr: 586
branch: fix/564-youtube-mart-future-dates
title: "fix(dbt): a transcript dated after tomorrow takes the video's upload day or null"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: fix(dbt): a transcript dated after tomorrow takes the video's upload day or null

## Summary
The PR fixes #564, where 10 transcripts in `event_documents` carried a future `event_date` (up to 2926-04-01) parsed from
video titles. It fixes the date at its source, the `event_youtube_with_jurisdiction` view: a bronze date after
`current_date + 1` becomes the video's upload day, or NULL when the video has no upload time. It adds an error-severity
test on `event_documents` and updates the column description and ODCS contract. The fix is correct and I reproduced
the PR's numbers. The 10 video ids and their new dates match the body's table, and no served row is after tomorrow. The
new test fails on today's un-rebuilt table (10 rows) and would pass after the rebuild (simulated, 0 rows). Everything
the change touches downstream only reads the date for display or sorting. I found no blocking or should-fix issues, only
three nits: the upload-day and NULL branches have no test of their own, the substituted upload day is not the meeting
date, and the bronze-parser follow-up has no issue yet. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 4 (+26 / -3, no generated files)
- Areas touched: dbt_project (mart model, schema, singular test, ODCS contract)
- Commits:
  - `be7be661` fix(dbt): a transcript dated after tomorrow takes the video's upload day or null
- Range reviewed: `0ba4fcd2..be7be661` (PR base is `main`; not a stacked PR)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Detect Docker-relevant changes | success |
| Docker Build Test (Full Stack) | skipped (not required) |

CI does not run `dbt test` or build the warehouse, so the new test's result comes from my simulation below, not from CI.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. SQL, YAML and a test only; no keys, URLs or credentials.
- **Fabricated data in a served path:** clean. No literal values are introduced. Replacement dates come from real bronze
  columns (`published_at`), and a missing upload time gives NULL, not a guess. The three December 2026 videos
  stay NULL instead of being "corrected" to a guessed year, which is the right call under "No Fabricated Data".
- **Personal data:** clean. Public meeting-video metadata only.
- **Destructive or bulky data changes:** clean. A `CASE` in a view and a read-only test. Nothing touches `data/cache/` or
  bronze, and the warehouse is changed only through dbt. (The author's local rebuild of the view is outside the diff.)

## Strengths
- The fix sits at the source of the transcripts' date. `event_documents` (via `COALESCE(e.event_date, y.event_date)`),
  `recent_transcribed_meeting`, `data_center_meeting_mention` and `event_policy_decision` all read this view, so one
  change cleans them all. The PR checked the DAG first: `dbt ls --select event_youtube_with_jurisdiction+` lists only
  date consumers, and I confirmed no key or join uses `event_date` (`event_policy_decision` carries it as a plain
  column; its key is an md5 of source ids).
- The `<= current_date + 1` guard on `published_at::date` also stops an upload day in the future from being used.
  Bronze has none today (0 rows), but the guard is correct.
- The test is an invariant on the served table (every transcript `video_id`, including Granicus `platform:uid` rows), not
  only on the view. It therefore also catches a bad date arriving through the golden `event` side of the `COALESCE`.
- The PR body is candid: it lists the 10 video ids with before and after dates, says why 7 are NULL, and says what is
  not fixed (the bronze title parser) and what is unfinished (the `event_documents` rebuild and test run).
- The description in `_schema_event.yml` and the regenerated ODCS contract agree: `python -m models.odcs --check`
  passes (64 contracts current and valid).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
1. **`dbt_project/models/marts/event_youtube_with_jurisdiction.sql:100-107`: the upload-day and NULL branches of the new
   `CASE` are not asserted anywhere.** The only new test checks the invariant "no transcript after tomorrow". That test
   would also pass if every bad row became NULL, or if the upload day were used when it is itself in the future. The
   `<= current_date + 1` guard on `published_at` and the "exactly tomorrow passes through" boundary are untested too.
   *Verified:* the test file only selects `event_documents` rows with `event_date > current_date + 1`. The repo already
   uses dbt `unit_tests` (for example `_schema_data_center_project.yml`, `_schema_decision_context.yml`). *Fix:* add a
   unit test on `event_youtube_with_jurisdiction` with rows for title 2926 with upload time, title 2036 without upload
   time, title exactly tomorrow, and a normal past date, expecting upload day, NULL, unchanged, unchanged. The view has
   several `ref`s and a `source`, so it needs mocks for each. If that is too heavy, a small macro for the `CASE`
   would be easier to unit-test.
2. **`event_youtube_with_jurisdiction.sql:100-107`: the upload day is shown as the meeting date.** For video
   `ZOemQ_WclcI` ("March 16, 2926") the result is 2026-04-03, the upload date, while the title's day is almost certainly
   2026-03-16, 18 days earlier. A video's upload day is often far from its meeting date: in bronze, 1,507 videos have a
   title date more than three years before the upload (`published_at`). The PR and the column description disclose the
   substitution, and the issue's "Done when" allows it, so this is not a defect. A stricter alternative is to correct only
   a recognisable century typo (29xx to 20xx) and use the upload day otherwise. Consider recording that choice under
   `web_docs/docs/development/` if the team wants a standing rule for bad title dates.
3. **Follow-ups are not filed and the prod copy is not mentioned.** The PR says the bad dates still land in
   `bronze.bronze_event_youtube.event_date` (the loader's title parser, `fix_bronze_event_dates_from_titles` /
   `apply_resolved_event_date` in `packages/scrapers`) and that this change works "at read time, as #580 did". `AGENTS.md`
   says an out-of-scope finding becomes an `action-item` issue. I searched for one and found none (38 bronze rows
   have a date after tomorrow, 10 of them with transcripts). The PR also doesn't say that the hosted copy of
   `event_documents` needs a re-sync after the local rebuild (`sync_event_documents_to_neon`). I could not check the hosted
   data (out of scope for this read-only review), so I don't know whether it has the bad dates. *Fix:* open the
   `action-item` issue for the parser, link it from the PR, and add a line about the sync.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `fix/564-youtube-mart-future-dates`; body says `Closes #564`; #564 has Problem, Done when, Contract, Read first, and the 10 `video_id`s are listed in the PR as it asks |
| Conventional Commits | Yes | `fix(dbt): …`; co-author trailer present |
| No fabricated data | Yes | Real upload day or NULL; see scans |
| New Python in `packages/` | n/a | No Python changed |
| dbt for transformations | Yes | The date fix is SQL in a mart view |
| Naming | n/a | No columns added or renamed |
| Keys | n/a | No `public` model added; keys and constraints are unchanged |
| Calendar years | n/a | `event_date` stays `date` (no year column) |
| Scope label matches filter | n/a | No UI change |
| Match evidence on filtered tiles | n/a | No UI change |
| Docs | Yes | Column description and ODCS contract updated and consistent; no new doc needed (see nit 2 on a decision record) |
| Telemetry and logging | n/a | No API or Python code |
| Tests | Partial | Invariant test would fail before the fix; branch behaviour is untested (nit 1) |
| Shared libraries | n/a | No `packages/` change |

## Test Coverage
- **Run locally** (worktree `be7be661`, read-only against the local warehouse):
  - `dbt ls --select event_youtube_with_jurisdiction+`: lists the downstream marts and tests. `dbt compile` of
    `event_youtube_with_jurisdiction` and `assert_event_documents_event_date_not_future`: both compile.
  - `python -m models.odcs --check`: 64 contracts current and valid.
  - Test SQL run read-only on the current `gold.event_documents` (not yet rebuilt): **10 rows**, the same 10 ids as the issue,
    so the test would fail without the fix.
  - Simulating the rebuild (orphan transcripts take the view's date): **0 rows** after tomorrow. All 10 rows have
    `event_id IS NULL`, so none depends on the golden `event` date, and `gold.event` has 0 rows after tomorrow.
  - No Python or frontend files changed, so `pytest`, `ruff` and `tsc` were not needed.
- **PR claims checked:**
  - "Rebuilt `gold.event_youtube_with_jurisdiction`": reproduced. The live view contains the new `current_date` logic and has
    214,765 rows, 0 after tomorrow, max date 2026-11-19.
  - "The 10 rows above are as shown": reproduced. The 3 with `published_at` get 2026-04-03, 2026-04-03, 2026-10-13, and the 7
    without it give NULL (`published_at` is empty in bronze for those 7).
  - "DAG checked, no key or join uses `event_date`": reproduced.
  - **Not verified:** that `event_documents` rebuilds cleanly and that the new test passes on the rebuilt table. The PR says
    this is still running and I may not run `dbt run|test`. My simulation is read-only SQL, not the real test run. The
    live `gold.event_documents` still has the 10 old dates until the rebuild finishes.
- **Not covered by a test:** the upload-day branch, the NULL branch, the `<= current_date + 1` guard on `published_at` and the
  tomorrow boundary (nit 1).

## Verdict
**approve-with-nits.** The fix is correct, minimal and placed at the right layer, and the PR's claims reproduce, except the
rebuilt-`event_documents` test run, which is still pending. Before merge, confirm that run is green (the test should
return 0 rows). The three nits (a unit test of the `CASE` branches, the upload-day choice, and the follow-up issue and
sync note) can follow as `action-item` issues.
