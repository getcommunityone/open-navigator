---
pr: 824
branch: feat/823-load-tab-counts
title: "feat(batch-jobs): counts and error drill-downs on the Load tab"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: api-specialist subagent (read-only, ran the tests) and coordinator
verdict: approve-with-nits
---

# PR Review: feat(batch-jobs): counts and error drill-downs on the Load tab

## Summary
Gives the Load tab what tab 1 has: counts per step and a drill-down into what was skipped or failed and why. The loader
writes a result file, the job runner records counts per step and dbt's per-model results, an endpoint serves them, and
the tab renders chips and a filterable table. The first review pass at `3fb49ace` returned **request-changes**: one
blocking UI defect, five should-fix items and several nits. All were fixed on the branch and re-checked, so the verdict
is approve-with-nits. It has not run against a real cache and warehouse.

## Scope of Change
- Files changed: 10 (excluding this review)
- Areas touched: packages (llm, hosting) / api / web_app / tests / web_docs
- Commits: `2721d571`, `3fb49ace`, plus the review-fix commit that carries this file
- Range reviewed: `origin/main...origin/feat/823-load-tab-counts` at `3fb49ace`; fixes verified by the coordinator

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | Read on the commit that carries this file before merging. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data: the docs table used invented numbers that did not add up. **Fixed** (placeholders). A step with no
  result shows "No counts recorded", never zeros; a missing cache is now an error, not an all-zero success.
- Personal data: clean (file paths and public video ids).
- Destructive data changes: clean. The loader still only reads the cache; result files are written beside the job logs.

## Strengths
- Loader accounting was traced: every discovered file is loaded, listed exactly once, or is the other tier;
  `errors == errors_unreadable + errors_upsert`; nothing is double counted.
- Old status files still load (new fields are optional); the route is admin-protected and not shadowed.
- The end-to-end runner test really runs a subprocess that writes a result and exits 1.

## Findings
### 🔴 Blocking (Critical)
1. `StepResultPanel.tsx`: `q`, `reason` and `page` were in the query key with no placeholder data, so every keystroke
   replaced the panel with "Loading counts…" and the search box lost focus. **Fixed** with `keepPreviousData` and by
   showing the loading text only before the first data. Verified in Chromium: typing nine characters keeps focus and text.

### 🟡 Should fix (Important, non-blocking)
All fixed.
2. A step that had just finished could keep the cached "No counts recorded" answer, because polling stopped when it
   ended. Fixed: whether the step has recorded counts is part of the query key, so the panel refetches when they land.
3. Exit rule: with only database-write errors failing the run, a cache where **every** file is unreadable loaded
   nothing, exited 0 and let dbt run. Fixed in `exit_code()`: the run also fails when files were unreadable and nothing
   loaded, and when the cache folder is missing (which previously produced an all-zero "nothing failed" report).
   Unchanged from `main`, and documented: every file skipped as `no_event` still exits 0.
4. The result file was not written when the run raised, and a failure to write it could fail a good load. Fixed:
   written in `finally`, with a caught and logged `OSError`.
5. Docs example numbers looked real and did not sum. Fixed: placeholders.
6. Docs said errors come first, but only the reason chips were ordered. Fixed: the API sorts rows errors-first (stable).

### 🔵 Nits / suggestions (Minor)
Fixed: the job id check is one regex (`[A-Za-z0-9_-]{1,80}`); dead clause in the singular-label expression removed;
"read" no longer counts files of the tier a `--tier` run was not asked for; tests added for gate reasons, a failed
database write through the real `run()`, a missing cache, a raising run, and an unwritable report.

Left as is:
- The endpoint re-reads the result file per request (a few MB at 12,000 items, tens of milliseconds).
- The other endpoints in the file take `job_id` unchecked; Starlette's path matching already blocks traversal.
- `web_app/src/lib/api.types.ts` was not regenerated; the new code uses hand-written types and the API Types check
  does not diff that file.
- A dbt run started from another terminal while the step runs could be read as this step's results; avoiding it needs
  a per-run dbt target path.
- No frontend unit test for the panel.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #823 with the four parts; branch `feat/823-load-tab-counts`; `Closes #823` |
| Conventional Commits | Yes | |
| No fabricated data | Yes | After the docs fix; explicit "no counts" state |
| New Python in `packages/` | Yes | |
| Scope label matches filter | Yes | The item count line names the active reason and search text |
| Docs | Yes | `web_docs/docs/development/batch-load-tab.md` |
| Telemetry and logging | Yes | loguru in the loader; the runner stays stdlib-only by design |
| Tests | Yes | 72 pass across the new and neighbouring files |
| Shared libraries | Yes | The loader's and runner's existing tests still pass |

## Test Coverage
`pytest tests/test_load_tab_counts_823.py tests/test_load_tab_steps_796.py tests/test_deployments_groups_796.py
tests/test_loader_gate_796.py`: 72 passed. `npx tsc --noEmit` passes; `eslint` on the new files is clean. In Chromium
against the dev server with a mocked API: chips, reasons, advice, search (focus kept), reason filter and paging work
with no page errors. Not run: a real load.

## Verdict
approve-with-nits. Nothing must change first. Confirm on the first real run that the counts add up to the files read.
