---
pr: 587
branch: fix/403-manifest-loader-ddl
title: "fix(meetings): --apply-ddl finds its migration and refuses to drop populated tables"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: fix(meetings): --apply-ddl finds its migration and refuses to drop populated tables

## Summary
The PR fixes #403 in the legacy manifest loader. `MIGRATION_PATH` now points at the migration's real location under
`packages/hosting/scripts/neon/migrations/`, and `--apply-ddl` refuses when any of the three scraped-meetings tables
exists and holds rows. The refusal names each populated table with its count. A new `--drop-existing` is the explicit
way to delete and rebuild them, and it is a usage error without `--apply-ddl`. The guide's warning is rewritten to
match. I ran the new tests (7 passed, 1 skipped with the neighbouring SuiteOne test file) and confirmed that 4 of the
5 new tests fail against `main`'s loader. All required CI checks are green. The guard is sound for what the issue
asked, with two small gaps (the guard counts rows but the migration's `CASCADE` also drops dependent dbt views, and
`main()`'s wiring of the flag is untested). Neither blocks the merge, so the verdict is approve-with-nits.

## Scope of Change
- Files changed: 3 (+134 / -8, no generated files)
- Areas touched: scripts (legacy loader, fixed in place) / tests / web_docs
- Commits:
  - `2b1b83b7` fix(meetings): --apply-ddl finds its migration and refuses to drop populated tables
- Range reviewed: `0ba4fcd2..2b1b83b7` (merge base with `main`; the PR's base is `main`, so it is not stacked)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | SUCCESS |
| Documentation Build (Docusaurus) | SUCCESS |
| Backend Tests (Python) | SUCCESS |
| API Types (OpenAPI -> TypeScript) | SUCCESS |
| PR conventions (linked issue) | SUCCESS |
| Detect Docker-relevant changes | SUCCESS |
| Docker Build Test (Full Stack) | SKIPPED (not required) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. No credentials, URLs or `.env` content in the diff. The loader still gets its DSN from
  `resolve_database_url()`.
- **Fabricated data in a served path:** clean. No `api/` or `web_app/` change. The only numbers are row counts read
  from the database for the refusal message, and test fixtures.
- **Personal data:** clean.
- **Destructive or bulky data changes:** clean, and the PR makes the flag safer. It deletes nothing from the repo,
  does not touch `data/cache/`, and does not change a table outside the migration it already ran. The destructive
  path (`--drop-existing`) is opt-in, named, and logs a warning that lists the dropped tables.

## Strengths
- The refusal is checked before any write: `_tables_with_rows` runs only `to_regclass` and `count(*)`, and
  `_apply_ddl` raises `SystemExit` before `cur.execute(sql)`. A test asserts `conn.executed == []` and
  `commits == 0` on refusal.
- The message says what would be lost ("SuiteOne rows included"), gives a row count per table, and names both ways
  forward (leave `--apply-ddl` off, or add `--drop-existing`). Missing and empty tables are skipped.
- `--drop-existing` is a usage error without `--apply-ddl` (exit code 2, tested through `main()`), so it cannot be
  passed by accident on its own.
- The tests pin the real migration file (`MIGRATION_PATH.is_file()` and a `DROP TABLE IF EXISTS` check), so a future
  move of the migration fails a test rather than breaking `--apply-ddl` at run time. That is the original bug.
- The guide, the module docstring example and the `--help` text were all updated, so the three places that
  describe the flag agree.
- Honest PR body: it says the checks were not run against a real database and that ruff's 6 E402 errors are
  pre-existing.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
1. **`scripts/discovery/load_scraped_meetings_manifests_to_bronze.py:448-468`: the guard counts rows, but the
   migration's `DROP TABLE … CASCADE` also drops dependent views, and it does so even when the tables are empty.**
   *Verified:* in the local warehouse (read-only `pg_depend`/`pg_rewrite` query) `staging.stg_scraped_meeting_documents`
   depends on the counties and municipalities tables, and `staging.stg_suiteone_meeting_documents` depends on the
   municipalities table (both are views). So `--apply-ddl` on empty tables, or `--drop-existing`, silently removes
   those views (and any view built on them) until the next `dbt run`. This is not a regression (`main` did the same
   thing, and worse), and the issue's Done-when list doesn't ask for it. But the new docs say the flag only
   "creates the three tables", and the message lists only tables. *Fix:* add one sentence to the guide and the
   `--drop-existing` help ("dependent staging views are dropped too; re-run dbt"). Or list dependent views in the
   refusal and warning text.
2. **`tests/test_scraped_meetings_loader_apply_ddl.py`: nothing tests that `main()` passes `args.drop_existing` on to
   `_apply_ddl`.** The four behaviour tests call `_apply_ddl` directly, and the only `main()` test is the usage
   error. *Verified by reading:* if `main()` stopped forwarding the flag (`_apply_ddl(conn)` as before), every test
   would still pass, and `--drop-existing` would be refused even though the user asked for it. *Fix:* one test that
   monkeypatches `psycopg2.connect` and `_apply_ddl`, runs `main()` with `--apply-ddl --drop-existing`, and asserts
   `drop_existing=True` arrives.
3. **`:456-468`: the check and the drop are two steps on a cursor, not one atomic statement.** A load into one of
   the tables between `_tables_with_rows` and the migration would still be dropped. For a manual, run-once admin
   flag this is acceptable, and the migration's own `BEGIN … COMMIT` is separate from the `count(*)` read. *Optional
   fix:* `LOCK TABLE … IN ACCESS EXCLUSIVE MODE` on the existing tables in the same transaction before counting.
4. **`scripts/` is frozen (`CLAUDE.md`).** This PR edits the legacy loader in place and adds only a test, no new
   file in `scripts/`. That is consistent with what #393 did and with the PR's own note that porting to `packages/`
   is a separate roadmap job, so it passes the rule. If the port isn't already an issue under
   `web_docs/docs/development/cleanup-roadmap.md`, add it.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `fix/403-manifest-loader-ddl`; body says `Closes #403`; #403 has Problem, Done when, Contract and Read first; PR conventions check is green |
| Conventional Commits | Yes | `fix(meetings): …` with the co-author trailer |
| No fabricated data | Yes | Scan above |
| New Python in `packages/` | Yes, with nit 4 | Nothing new in `scripts/`; the in-place fix of a legacy file is stated in the PR |
| dbt for transformations | n/a | No dbt change; see nit 1 for dbt views the migration cascades to |
| Naming | n/a | |
| Keys | n/a | No table or model change |
| Calendar years | n/a | |
| Scope label matches filter | n/a | No UI change |
| Match evidence on filtered tiles | n/a | |
| Docs | Yes | Edits an existing page under `web_docs/docs/guides/`; no new root `.md` |
| Telemetry and logging | Yes | The loader already uses loguru; the new warning uses `logger.warning` with `{}` formatting |
| Tests | Mostly | Behaviour tests would fail without the change (4 of 5 verified); `main()` wiring untested (nit 2) |
| Shared libraries | n/a | No `packages/` change; the migration SQL file is read, not modified |

## Test Coverage
- **Run locally** (worktree code forced via `PYTHONPATH`):
  - `pytest tests/test_scraped_meetings_loader_apply_ddl.py tests/test_scraped_meetings_loader_keeps_suiteone.py`:
    7 passed, 1 skipped (the live test that needs `RUN_LIVE_TESTS=1`).
  - **Revert check:** restoring `main`'s loader into the worktree made 4 of the 5 new tests fail (migration path,
    refusal, empty-table run, `--drop-existing`). The usage-error test passes on `main` because argparse already
    rejects the unknown flag with exit code 2, so it checks the flag's contract and not the new code. The PR body
    says the same ("four of them fail"). I restored the file with `git checkout` afterwards.
  - `ruff check` on the changed files: 6 E402 errors in the loader. `main`'s copy gives the same 6, so none are new.
  - No frontend, API or dbt change, so `tsc` and `dbt ls` were not needed.
- **Read-only warehouse check:** the local warehouse was reachable. The three scraped-meetings tables exist there,
  and the dependent-view query behind nit 1 ran against it. I did not run `--apply-ddl` or any write.
- **Unverified claim:** "Not run against a real database" is the PR's own caveat, and I did not run it either. The
  `to_regclass` and `count(*)` calls are standard, and the fake cursor answers them as the tests expect, but the
  real-connection path is untested. The migration's trailing `COMMIT;` plus the loader's `conn.commit()` is the
  pre-existing behaviour.
- **Not covered:** `main()` forwarding the flag (nit 2); a populated table and a concurrent writer (nit 3).

## Verdict
**approve-with-nits.** The fix does what #403 asks, is covered by tests that fail on the old code, and CI is green.
Nits 1 and 2 are worth a line of doc and one small test, and can land with this PR or as `action-item` issues.
