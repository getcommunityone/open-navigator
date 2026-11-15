---
pr: 343
branch: refactor/261-api-package-lazy
title: "refactor(api): stop api/__init__.py loading the whole app"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: refactor(api): stop api/__init__.py loading the whole app

## Summary

`api/__init__.py` imported `api.main`, so loading any one API module built the whole app: routes, agents, the
logger's file sink and telemetry. The package file now imports nothing. A new test checks, in fresh interpreters,
that `import api.database` leaves `api.main` unloaded and that `import api` loads no submodule. Closes #261.
Approve.

## Scope of Change

- Files changed: 3: `api/__init__.py` (the import removed, a docstring saying why), new
  `tests/test_api_package_import.py`, and `tests/test_telemetry_db.py` (one fixture docstring)
- Areas touched: API package, tests

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: none.
- Personal data: none.
- Destructive or bulky changes: none.

## Findings

None blocking, none to fix. Checked:

- **Nobody used the package-level import.** `from api import app` appears nowhere. Root `main.py` and the tests import
  from `api.main`.
- **Start commands.** Every start command names a module: `api.main:app` in `supervisord.conf`, `app.yaml`,
  `databricks.yml` and `main.py`, and `api.app:app` in `Dockerfile.app`. uvicorn imports that module itself, so none
  of them needed the package import. `api.app:app` used to build `api.main`'s app too, as a side effect, which it
  never used. `api/app.py` imports nothing from `api.main`.
- **The telemetry fixture stays.** Other test modules import `api.main` at collection, so the drivers can already be
  instrumented when it runs. Only its explanation changed.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #261 has all four parts; `Closes #261` |
| Conventional Commits | Yes | `refactor(api): ...` with the co-author trailer |
| Test first | Yes | The 2 new tests failed before the change and pass after |
| Tests | Yes | Whole suite on top of #338: 1376 passed, 40 skipped, 2 xfailed, no errors |
| Contract | Yes | "`api/__init__.py` no longer imports `api.main`. Nothing is renamed." |

## Verdict

Approve once the required checks are green.
