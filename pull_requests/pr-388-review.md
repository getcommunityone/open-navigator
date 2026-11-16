---
pr: 388
branch: fix/387-neon-sync-data-center-tables
title: "fix(hosting): mirror the data center tables to Neon, and check the 512 MB budget before every sync"
author: coordinator (Claude Code)
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve
---

# PR Review: Neon sync for the data center tables, with a size budget (#388)

## Summary
The Neon sync copied only allow-listed tables, and none of the four data center marts were on the list, so production `/data-centers` would have stayed empty. They're added. `job_application_link` (written by the prod admin screen) is named runtime-owned, so it's never overwritten, and the `Makefile` mirror matches. Because allow-listed tables grow with each crawl, the sync now projects Neon's size before copying and stops (exit 4) if the result passes 480 MB or the swap's peak passes 512 MB. Approve.

## Scope of Change
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`: allow-list and runtime list; `SizeProjection`, `estimate_copy_bytes`, `budget_problem`, `_local_object_bytes`, `_target_sizes`; `--max-mb`; dry run prints sizes.
- `Makefile`: `PII_EXCLUDE_TABLES` gains `job_application_link`.
- Tests: `packages/hosting/tests/test_neon_sync_data_center_tables.py` (7).
- Docs: `neon-serving-scope.md`, "The size check before each sync".

## CI Status
Checked on the head commit before merge; see the PR's Checks tab.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: none.
- Fabricated data: none.
- Personal data: makes it harder for app-owned data to be copied over.
- Destructive changes: the check only stops a copy; nothing new is dropped.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- The incoming estimate excludes indexes, which is correct for these plain copies; a future copy that adds indexes should add them to the estimate.
- `pg_database_size` measures the database, not other Neon branches; branches share the project cap, so keep the 32 MB headroom or lower `--max-mb` if branches are used.
- `proximity_alerts` is app-owned and also missing from `RUNTIME_OWNED`. It's skipped today because it's unclassified; worth adding in a follow-up.

## Repo-Rule Compliance
Issue first (#387, four parts), branch `fix/387-…`, `Closes #387`, Conventional Commits, loguru, docs in `web_docs/docs/`: ✅

## Test Coverage
- 7 tests: the allow-list and runtime list pinned; the Makefile mirror equals `RUNTIME_OWNED`; estimate arithmetic; final vs budget; peak vs cap.
- Both size queries ran against local PostgreSQL.
- Not covered: a run against Neon itself.

## Verdict
**approve.**
