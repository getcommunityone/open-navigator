---
pr: 338
branch: fix/337-async-engine-traced-twice
title: "fix(telemetry): trace each async engine once"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: fix(telemetry): trace each async engine once

## Summary

Backend Tests on `main` fail with four errors in `test_telemetry_db.py`. The cause is in `instrument_databases`, not
the test. On the `api.main` import path, `sqlalchemy.ext.asyncio` is first imported after tracing has wrapped
`create_engine`, so it binds the wrapped function, and `create_async_engine` traces each async engine twice. Each
query then starts two spans and ends one. Turning tracing off removes a shared listener twice and raises, which
breaks the test fixture whenever an async engine from an earlier test is still alive. The PR imports the asyncio
extension before tracing starts and adds a fresh-interpreter test of the production path. Closes #337. Approve.

## Scope of Change

- Files changed: 2: `api/telemetry.py` (6 lines and an import) and `tests/test_telemetry_db.py` (a new test, and a
  helper the two subprocess tests share)
- Areas touched: API telemetry, tests

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: none. The counts in the PR text (2 spans started, 1 ended; 14 listener entries against 7) were
  measured locally with the pinned `opentelemetry-instrumentation-sqlalchemy` 0.63b0.
- Personal data: none.
- Destructive or bulky changes: none. The test's database is in memory.

## Findings

None blocking, none to fix. Two notes:

- The import has to happen before the first instrumentation in the process, and that's what it does: every caller
  goes through `instrument_databases`, and nothing in the repository calls `SQLAlchemyInstrumentor().instrument()`
  directly.
- A module that imports `create_async_engine` itself before `setup_telemetry` runs still gets the unwrapped function,
  so its engines go untraced. That's the instrumentor's documented limit, the same one the existing end-to-end test
  guards for `create_engine`. Nothing in the app does that today, and this PR doesn't change it.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #337 has all four parts, with the failing run and error line; `Closes #337` |
| Conventional Commits | Yes | `fix(telemetry): ...` with the co-author trailer |
| Test first | Yes | The new test failed before the fix (`started: 2`, `InvalidRequestError`) and passes after |
| No fabricated data | Yes | Measured numbers only, with the version they came from |
| Tests | Yes | Whole suite: 1372 passed, 40 skipped, 2 xfailed, no errors |

## Verdict

Approve once the required checks are green.
