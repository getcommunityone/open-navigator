---
pr: 306
branch: fix/304-lighthouse-report-500
title: "fix(api): read stored Lighthouse reports with the existing results helper"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: fix(api): read stored Lighthouse reports with the existing results helper

## Summary

`GET /api/lighthouse/report` answered 500 whenever an audit row existed. `_lhr_from_row` called `_dict_from_row`,
which was never defined. The PR calls `_dict_from_results`, the helper defined just above it, and adds a regression
test that stubs the database pool. The fix is one line and the test failed before it. No other caller of the
missing name remains. Closes #304. Approve.

## Scope of Change

- Files changed: 2 (+112 / -1)
- Areas touched: api, tests
- Commits: 3b9c096b fix(api): read stored Lighthouse reports with the existing results helper
- Range reviewed: `e32e3cdc..3b9c096b`

## CI Status

| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success (it doesn't run `tests/`, see #305) |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Docker Build Test (Full Stack) | skipped (no Docker files changed; not required) |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: clean. The scores in the test (0.91, 0.88 and so on) live only in the test file and never reach a served path.
- Personal data: none. The test uses `example.gov`.
- Destructive or bulky changes: none.

## Strengths

- The test goes through the real route with httpx's ASGI transport, so it checks the response the endpoint serves.
  It doesn't just unit-test the helper.
- It covers both ways a stored report arrives (a dict, or JSON text), that a score column wins over the report, and
  that the 404 path didn't change.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None in this PR. The gap that let the bug through (CI never runs `tests/`) is #305.

### 🔵 Nits / suggestions (Minor)

None.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #304 has Problem, Done when, Contract and Read first; branch `fix/304-...`; `Closes #304` |
| Conventional Commits | Yes | `fix(api): ...` with the co-author trailer |
| No fabricated data | Yes | Scan above |
| New Python in `packages/` | n/a | No new modules; the test is in `tests/` like its neighbours |
| Telemetry and logging | n/a | No new route or job |
| Tests | Yes | The regression test failed before the fix (3 of 4, `NameError`) and passes after |
| Shared libraries | n/a | No change in `packages/` |

## Test Coverage

Run locally on Python 3.12.3, with the repo root and every `packages/*` folder (and its `src`) on `PYTHONPATH`:

- `tests/test_api_lighthouse_report.py`: 4 passed. Before the fix, 3 failed with `NameError`.
- `tests/test_api_states.py`: 7 passed.
- `ruff check --select F821` on the route: clean. Both files pass `py_compile`. `from api.app import app` imports.

CI will not run the new test until #305 adds `tests/` to Backend Tests.

## Verdict

Approve. Every required check is green on `3b9c096b`. The owner merges.
