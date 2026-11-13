---
pr: 218
branch: fix/api-routes-and-states
title: "fix(api): resolve states from active bills and harden router route inspection"
author: BlueHopper6
reviewed_at: 2026-11-13
reviewer: maintainer session (coordinator) + helper agent
verdict: approve-with-nits
---

# PR Review: fix(api): resolve states from active bills and harden router route inspection

## Summary

`GET /states` returned a hard-coded placeholder, `["CA", "NY", "TX", "FL", "IL"]`, as "states with active
opportunities". This PR replaces it with a query for distinct `state_code` values in `bills` whose titles mention
fluoride, dental, oral health or water treatment, and adds `GET /api/states` with a typed `StatesResponse`. The
first version fell back to a different hard-coded list of eleven states when the database had no answer, which is
fabricated data under CLAUDE.md. The maintainer commit `5917416` changes the fallback to `settings.target_states` (the
real setting), else an empty list with a warning. It also hardens three route-existence tests to read
`app.openapi()["paths"]`. It works and the tests pass. The verdict is approve, with two nits.

## Scope of Change

- Files changed: 6 (+226 / -13), no generated files
- Areas touched: api (`api/main.py`), tests, README
- Commits:
  - af9f4e4 fix(web): resolve TypeScript CI errors
  - dc1eaaa fix(api): resolve states from active bills and harden router route inspection
  - 5917416 fix(api): return no states instead of a hard-coded list when the database has none (maintainer)
  - two merges of `main`
- Range reviewed: merge base with `main` to `5917416`, then the sync with `main` at `3369986`

## CI Status

| Check | Status (on 5917416) |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| Docker Build Test | skipped (no Docker files changed) |

The sync with `main` re-runs them. They are checked green on the final head before merging.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data in a served path:** fixed. The original placeholder list on `main` and the eleven-state fallback
  in the first version are both gone. The endpoint now returns only states found in `bills`, or the configured
  `settings.target_states`, or nothing.
- **Personal data:** clean.
- **Destructive data changes:** clean. Read-only query.

## Strengths

- Removes a placeholder from a served path that `main` has carried since the endpoint was written.
- The query is parameter-free and read-only, normalises case and blanks, and logs a warning instead of raising when
  the pool is down, so offline and CI runs don't return 500.
- Seven tests cover route registration, the database result, normalisation, the database error, the configured
  fallback and the empty fallback.
- The `openapi()["paths"]` change makes three existing route tests independent of Starlette's router internals.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

1. **The response doesn't say where the list came from.** When the database is down and `target_states` is set, the
   configured states are returned as "states with active opportunities". They are real configuration, but a caller
   can't tell them from a database answer. A `source` field (`"database"`, `"configured"` or `"none"`) would make
   that visible. Follow-up issue, not this PR.
2. **The keyword filter is in two places.** The four title keywords repeat the policy topics in `settings`. Reading
   them from one place would keep the two from drifting.

## Repo-Rule Compliance

| Rule (CLAUDE.md) | Status |
|---|---|
| No Fabricated Data | ✅ after `5917416` |
| Conventional Commits | ✅ |
| Never push to `main`, never force-push | ✅ (merges only) |
| Required checks green | ✅ on `5917416`; re-checked on the final head |
| Docs in `web_docs/docs/` | n/a (README example only) |
| New Python in `packages/`, not `scripts/` | n/a (API route) |
| Issue first, `Closes #<issue>` (AGENTS.md) | n/a: opened Nov 3, before the rule's start date of Nov 14 |

## Test Coverage

`tests/test_api_states.py` (7 tests) plus the three hardened route tests: 18 passed locally on the synced branch,
with the workspace packages on the path as CI installs them.

## Verdict

**Approve with nits.** Merge when the four required checks are green on the final head. The two nits can be follow-up
issues.
