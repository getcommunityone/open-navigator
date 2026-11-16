---
pr: 431
branch: feat/402-crawl-homepage-linked-channels
title: "feat(youtube): crawl cities and counties whose channel is linked from their website"
author: jcbowyer
reviewed_at: 2026-11-16
reviewer: coordinator (Claude Code session; no reviewer subagent, as the rubric allows)
verdict: approve-with-nits
---

# PR Review: feat(youtube): crawl cities and counties whose channel is linked from their website

## Summary
The PR is stacked on #430 (`fix/420-youtube-catalog-all-states`), so this review covers only its own commits. It adds
`include_homepage_channels` to `fetch_batch_plan_jurisdictions`. When it is on, the crawl plan also lists cities and
counties whose primary channel is a `website_scrape` link, even when they have no videos yet. Both runner scripts turn
it on by default (`HOMEPAGE_CHANNELS=0` turns it off). The plan query is rewritten as equality joins: the old one
never ran, because a bare `%` in `LIKE '%\_'` broke psycopg2's parameter formatting. `/user/` and `/c/` channel URLs
now resolve from the channel page. The code works and is tested. One 🟡 finding (the query error was still swallowed
silently) was fixed on the branch in 4bc9df8d. The verdict is approve-with-nits.

## Scope of Change
- Files changed: 6 (+238 / -24, including the review fix)
- Areas touched: api (batch_jobs), packages (scrapers), tests
- Commits:
  - 9d54c7c8 feat(youtube): crawl cities and counties whose channel is linked from their website
  - 64054aea fix(youtube): resolve /user/ and /c/ channel URLs from the channel page
  - 2c9dfbc2 test(youtube): plan a channel-only jurisdiction; national runner counts it too (#402)
  - 4bc9df8d fix(youtube): report a failed batch plan query instead of swallowing it (review fix)
- Range reviewed: `e1feedbc..4bc9df8d` (the #430 head up to this branch's head)

## CI Status
| Check | Status |
|---|---|
| PR conventions (linked issue) | pass |
| Frontend Build, Documentation Build, Backend Tests, API Types | not run: CI runs these only on PRs into `main`. They run once the PR is retargeted to `main` after #430 merges |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean. `api/batch_jobs/` is an operator CLI and plan builder, with no
  hard-coded counts.
- Personal data: clean.
- Destructive or bulky data changes: clean. The changes are read-only queries.

## Strengths
- Found and fixed the real root cause: the old `LIKE '%\\_' || j.geoid` broke psycopg2's `%s` formatting. A test
  renders the SQL with its four parameters and checks that no stray `%` is left.
- I confirmed the equality-join rewrite against the warehouse: `geoid` is text in both scraped tables and varchar in
  `int_jurisdictions`, and no `int_jurisdictions.geoid` has a non-digit character, so `substring(... '_([0-9]+)$')`
  matches everything the old `LIKE` did.
- The `/user/` and `/c/` regex leaves `/channel/` URLs alone, and a test checks that they need no lookup.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- **Fixed in 4bc9df8d.** `api/batch_jobs/batch_job_status.py:344` still had `except Exception: rows = []` around the
  main plan query. A silent catch is exactly what hid the `%` bug, so any future error in the new query would again
  send every plan to the fallback without a word. Verified by reading the code: nothing was logged or printed. The fix
  prints a `WARN:` line to stderr. It goes to stderr because the runner scripts read stdout as TSV. A regression test,
  `test_failed_plan_query_is_reported_not_silent`, checks that the fallback still runs and that the warning reaches
  stderr.

### 🔵 Nits / suggestions (Minor)
- `api/batch_jobs/batch_job_status.py` (`with_videos`): the first union arm (`yt.jurisdiction_id = j.jurisdiction_id`)
  no longer requires `yt.state_code = j.state_code`, which the old `EXISTS` applied to every arm. Both sides are
  already limited to the requested states and the id carries the place, so this changes nothing in practice.
- The runner's message `No jurisdictions with YouTube bronze for states: ...` is now slightly wrong when homepage
  channels are included. It's cosmetic.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `feat/402-...`; `Refs #402` (the guide line follows in #399); #402 has all four parts |
| Conventional Commits | Yes | All scoped, with co-author trailers |
| No fabricated data | Yes | Scan clean |
| New Python in `packages/` | Yes | Changes are in `api/` and `packages/scrapers`; nothing new in `scripts/` |
| dbt for transformations | Yes | Read-only plan selection, not a transformation |
| Naming | N/A | |
| Keys | N/A | |
| Calendar years | N/A | |
| Scope label matches filter | N/A | |
| Match evidence on filtered tiles | N/A | |
| Docs | N/A | The guide line is deferred to #399, as the PR says |
| Telemetry and logging | Yes | The query failure is now reported (stderr; the module has no logger) |
| Tests | Yes | Channel-only plan, SQL parameter safety, legacy URL resolution, and the silent-failure regression |
| Shared libraries | Yes | `packages/scrapers` and `packages/ingestion` suites run |

## Test Coverage
Ran locally with the worktree's packages on `PYTHONPATH`: `pytest tests/test_batch_job_plan.py
tests/test_batch_job_status.py packages/scrapers/tests packages/ingestion/tests`, 771 passed (including the new
test). `ruff check` on the changed Python adds no new errors: the same errors are reported before and after, all already on `main`.
`bash -n` passes on both runner scripts. The live Delaware run in the PR description was not repeated.

## Verdict
approve-with-nits. The one 🟡 finding is fixed. Retarget to `main` after #430 merges and let the required checks run.
