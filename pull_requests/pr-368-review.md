---
pr: 368
branch: fix/367-orm-neon-pooler
title: "fix(api): don't send a startup search_path to Neon's pooler, so sign-in works"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve
---

# PR Review: fix(api): don't send a startup search_path to Neon's pooler, so sign-in works

## Summary
Fixes the production sign-in outage (#367). The Space's container log shows every ORM connection failing with `unsupported startup parameter in options: search_path`. Neon's pooled endpoint (host `…-pooler…`) rejects the libpq startup `options` that `api/database.py` sent to pin `search_path`. The fix sends no `options` on a pooled host. The server default `"$user", public` already resolves the ORM tables to `public`. Unpooled and local hosts keep the pin. A warning is logged if a private (`API_DB_SCHEMA=gold`) instance runs through the pooler, since the pin can't be applied there.

## Scope of Change
`api/database.py` (+~25), `tests/test_orm_neon_pooler.py` (new, 3 tests).

## Scans
Secrets: clean (test URLs use placeholder credentials). No data, PII or destructive changes.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- Detection is by hostname (`-pooler`), which is Neon's documented naming for pooled endpoints. A non-Neon PgBouncer would still need the unpooled URL.

## Test Coverage
- `tests/test_orm_neon_pooler.py`: 3 passed (pooled → `{}`, unpooled and local → pin kept).
- `tests/test_route_gating.py`, `tests/test_oauth_account_link.py`: 24 passed.
- Not exercised against Neon from here. Confirmation is a successful sign-in after deploy.

## Repo-Rule Compliance
Issue #367 (four parts), `Closes #367`, branch `fix/367-…`, Conventional Commits, loguru for the warning.

## Verdict
**approve.** Merge as soon as CI is green (production sign-in is down).
