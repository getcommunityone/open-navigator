---
pr: 828
branch: feat/827-load-promote-step
title: "feat(batch-jobs): promote videos to events as the first step of a Load run"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: coordinator
verdict: approve
---

# PR Review: feat(batch-jobs): promote videos to events as the first step of a Load run

## Summary
Adds promotion (`bronze_event_youtube` → `civic_event`) as the first step of a Load run, so analyses are no longer
skipped as `no_event` until someone runs a command by hand. The part that matters most is the database rule: the
promote command's default resolution can fall back to production, so the step runs with a new `--local-warehouse` flag
that uses the loader's rule and never reads `NEON_DATABASE_URL`. That rule is tested directly and against the loader's
own constant. Approve. It has not run against a real warehouse.

## Scope of Change
- Files changed: 9 (excluding this review)
- Areas touched: packages (ingestion, hosting) / api / web_app / tests / web_docs
- Commits: `993bc7ee` feat(batch-jobs): promote videos to events as the first step of a Load run; `d1314a01` style
- Range reviewed: `origin/main...origin/feat/827-load-promote-step`

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | Read on the commit that carries this file before merging. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean. The database URL is resolved inside the child process; it is not placed on the command line, so the
  password does not reach the step's `cmd` field or log.
- Fabricated data: clean.
- Personal data: clean.
- Destructive or bulky data changes: none. The step upserts event rows; it deletes nothing. It writes outside dbt, as
  the existing manual command already did; that is ingestion, not a transformation.

## Strengths
- Production cannot be reached from the Load tab's promote step: verified by a test that sets `NEON_DATABASE_URL` and
  `OPEN_NAVIGATOR_DATABASE_URL` and still gets the local URL.
- A test reloads the loader under both environments and asserts the two steps resolve the same database.
- Without the new flags the command behaves exactly as before.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- Traced: promotion writes `gold.civic_event` (its `search_path` is `gold, public`) and the loader's lookup reads
  `gold.civic_event`, so the rows the first step writes are the rows the second step finds.
- The step's database rule is duplicated from the loader rather than imported, to avoid `ingestion` depending on
  `llm`; the equality test guards the copy.
- Step metadata is still declared twice (runner and API), as before this PR; both were updated.
- Promotion covers only videos with an analysis stamp and a date, so some `no_event` skips can remain. The advice text
  and the docs say so.
- If promotion fails (for example the database is down), the run stops before the load, which is the right outcome:
  the load would fail on the same connection.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #827 with the four parts; branch `feat/827-load-promote-step`; `Closes #827` |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |
| New Python in `packages/` | Yes | |
| dbt for transformations | Yes | Ingestion upsert, unchanged in kind |
| Docs | Yes | `web_docs/docs/development/batch-load-tab.md` |
| Telemetry and logging | Yes | loguru |
| Tests | Yes | Step order, argv, database rule, counts, CLI |
| Shared libraries | Yes | Runner, loader and API tests run together: 77 passed |

## Test Coverage
`pytest tests/test_load_tab_counts_823.py tests/test_load_tab_steps_796.py tests/test_deployments_groups_796.py
tests/test_loader_gate_796.py`: 77 passed. `npx tsc --noEmit` passes. Not run: the step against a real warehouse.

## Verdict
approve. On the first real run, confirm the promote step's log shows the local database and that the `no_event` count
falls.
