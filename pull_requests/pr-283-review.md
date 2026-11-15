---
pr: 283
branch: fix/282-sqlalchemy-psycopg2-driver
title: "fix(api): name the psycopg2 driver so the API starts on SQLAlchemy 2.1"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: fix(api): name the psycopg2 driver so the API starts on SQLAlchemy 2.1

## Summary

Fixes the production outage in #282. The ORM engine now gets an explicit `postgresql+psycopg2://` URL, and SQLAlchemy
is capped below 2.2. The cause was traced from the Space's container log (`import psycopg` → `ModuleNotFoundError`)
and reproduced with SQLAlchemy 2.1.8 on Python 3.11. The new test fails without the fix and passes with it. Approve.

## Scope of Change

- Files: `api/database.py`, `requirements.txt`, `tests/test_api_database_url.py`.
- Areas: api.

## Scans

- Secrets: clean (the test uses a dummy URL and `JWT_SECRET_KEY=test-only`).
- Fabricated data: none. Personal data: none. Destructive changes: none.

## Findings

### 🔴 Blocking
None.
### 🟡 Should fix
None.
### 🔵 Nits
- `api/database.py` has an import-order warning (ruff I001) that predates this change; left alone to keep the fix small.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #282 with four parts; `Closes #282` |
| Conventional Commits | Yes | |
| Tests | Yes | Regression test fails before, passes after |

## Verdict

Approve. Merging starts nothing by itself; production deploys from the `deploy` branch, which the owner updates.
