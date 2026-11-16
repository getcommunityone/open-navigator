---
pr: 397
branch: fix/393-loader-keeps-suiteone-rows
title: "fix(meetings): keep SuiteOne rows when reloading crawl manifests"
author: jcbowyer
reviewed_at: 2026-11-16
reviewer: coordinator (read-only review subagent; findings reproduced against a throwaway Postgres 16)
verdict: approve-with-nits
---

# PR Review: keep SuiteOne rows when reloading crawl manifests (#397)

## Summary
The manifest loader used to run `DELETE ... WHERE jurisdiction_id = %s` before each insert. That wiped Tuscaloosa's
SuiteOne agenda and minutes rows, which share `bronze.bronze_events_meetings_municipalities_scraped`. The loader now
deletes only rows without a SuiteOne marker and inserts with `ON CONFLICT (jurisdiction_id, url_sha256) DO NOTHING`.
The SuiteOne upsert now also claims `manifest_relative_path` on a row the crawl inserted first. I traced the
DELETE/ON CONFLICT logic and replayed it in Postgres. Rows are no longer lost or duplicated, the `%%` escaping is
correct, and both new tests fail on the old loader. Verdict: approve with nits. Before merge, three things should
change: the live test commits a destructive migration that its `rollback()` can't undo; the issue's third Done-when
item isn't met although the PR closes the issue; and the `scrape.py` change has no test.

## Scope of Change
- Files changed: 3 (+129 / -1)
- Areas touched: packages (`scrapers`), scripts (legacy loader, minimal edit), tests
- Commits:
  - `7681446e` fix(meetings): keep SuiteOne rows when reloading crawl manifests
- Range reviewed: `61d2a870..7681446e`

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Docker Build Test (Full Stack) | skipped (not required) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. The only DSN is a test placeholder read from `TEST_DATABASE_URL`.
- **Fabricated data in a served path:** clean. No `api/` or `web_app/src/` changes.
- **Personal data:** clean. The data is public meeting documents.
- **Destructive data changes:** no `data/cache/` deletion and no bulk files. The one destructive step is the live
  test's DDL, which commits a `DROP TABLE ... CASCADE` (see the first 🟡 finding). It is opt-in, behind
  `RUN_LIVE_TESTS=1` plus `TEST_DATABASE_URL`, so it doesn't block.

## Strengths
- The delete predicate is right in its edge cases. `COALESCE` makes rows with NULL markers count as the loader's own
  and get deleted. Without it, `NOT (NULL LIKE ...)` would be NULL and stale crawl rows would pile up.
- It checks both markers, so a row that an older SuiteOne upsert re-tagged (path left as the manifest's, date source
  `suiteone_listing`) is also protected.
- No rows lost and no duplicates. The DELETE and the INSERT run in one transaction for each manifest (`main` commits
  after each `_load_manifest_to_table`). Because the loader's own rows are deleted first, `DO NOTHING` can only skip
  rows SuiteOne owns. All three target tables declare `UNIQUE (jurisdiction_id, url_sha256)` in migration 020, so
  `ON CONFLICT` has a matching arbiter on every table in `TABLE_FOR_PREFIX`. `_dedupe_rows_by_url_sha256` removes
  in-batch duplicates before the insert.
- psycopg2 `%` escaping is correct. The statement always runs with a parameter tuple, so `%%` becomes `%`. Checked
  with `cursor.mogrify`: `... AND NOT (COALESCE(manifest_relative_path, '') LIKE 'suiteone:%' OR ...)`.
  `_FOREIGN_ROW_SQL` has no `{`/`}`, so the `.format(table=...)` call is safe.
- The change to the legacy `scripts/` file is a minimal in-place bug fix, not new code, and the PR says so.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`tests/test_scraped_meetings_loader_keeps_suiteone.py:81` (with `:99-100`): the live test permanently drops and
   recreates the three bronze scraped-meeting tables, but its `finally: conn.rollback()` suggests it leaves no trace.**
   Migration 020 has its own `BEGIN; ... COMMIT;`. Running it through `cur.execute(ddl)` commits
   `DROP TABLE ... CASCADE` (dependent views go too) and the new tables. psycopg2 still thinks a transaction is open,
   so the inserts that follow also commit one statement at a time, and the final `rollback()` does nothing.
   *Verified:* after one run on an empty `loadertest` database, the three `bronze.*_scraped` tables still exist and
   the municipalities table holds 3 rows. If `TEST_DATABASE_URL` ever points at a warehouse with real data (for
   example the local `open_navigator` on 5433), the test would destroy the SuiteOne and crawl rows this PR is meant
   to protect.
   *Fix:* don't run the full migration. Create a uniquely named schema, or `CREATE TEMP TABLE ... (LIKE ...)`, with
   the unique constraint, and point the loader at that table name. Or strip `BEGIN`/`COMMIT` and refuse to run
   unless the database name ends in `test`.
2. **Issue #393, third Done-when item, isn't met, but the PR says `Closes #393`.** The issue asks that "the loader is
   ported into `packages/` as a `python -m` CLI, **or** the fix is noted on the cleanup roadmap". The PR puts the port
   under "Not in this PR", and `web_docs/docs/development/cleanup-roadmap.md` has no mention of the loader or #393
   (checked with grep). *Fix:* add a line to the roadmap's backlog for porting
   `load_scraped_meetings_manifests_to_bronze.py` that notes this fix (#393), or change the PR to `Refs #393`.
3. **`packages/scrapers/src/scrapers/suiteone/scrape.py:107`: the new `manifest_relative_path = EXCLUDED...` claim
   has no test** (rubric: every behaviour change has a test). The live test inserts the re-tagged row by hand and
   never runs `_UPSERT`. *Verified that it works:* on a fresh database I loaded the crawl first, then ran
   `scrape.load_bronze` for the same URL, then reloaded the crawl twice. The row moved to
   `suiteone:tuscaloosa_0177256` / `suiteone_listing` with the listing date and survived both reloads, with no
   duplicate. *Fix:* add that sequence (crawl, then SuiteOne upsert, then crawl again) to the live test so the claim
   is checked.

### 🔵 Nits / suggestions (Minor)
1. **`tests/test_scraped_meetings_loader_keeps_suiteone.py:62`: the unit test only matches substrings.** It would
   still pass if the predicate were wrong, for example `LIKE 'suiteone:%'` with a single `%` (psycopg2 would raise on
   that only at execute time) or `AND` in place of `OR`. Asserting `cur.mogrify(...)` output against the exact
   expected SQL would make the CI-run test meaningful. Only the live test checks behaviour, and CI doesn't run it.
2. **`scripts/discovery/load_scraped_meetings_manifests_to_bronze.py:515`: the count is overstated.**
   `_load_manifest_to_table` returns `len(rows)`, so `total_url_rows` in the summary log now includes rows that
   `DO NOTHING` skipped. Consider renaming it to something like "attempted", or noting the skips in the docstring.
3. **Pre-existing, out of scope:** `MIGRATION_PATH` (`load_scraped_meetings_manifests_to_bronze.py:67`) points to
   `scripts/deployment/neon/migrations/020_...sql`, which no longer exists. The file is now under
   `packages/hosting/scripts/neon/migrations/`, so `--apply-ddl` raises `FileNotFoundError`. Under AGENTS.md this
   should be its own `action-item` issue, linked from the PR.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Partial | Branch name and `Closes #393` are right, and the issue has all four parts. Its third Done-when item isn't met (🟡 2) |
| Conventional Commits | Pass | One commit, `fix(meetings): ...`, with co-author trailer |
| No fabricated data | Pass | Scan clean |
| New Python in `packages/` | Pass | Minimal bug fix to an existing legacy file; no new `scripts/` file; port deferred |
| dbt for transformations | Pass | Ingestion-side ownership only; no transformation logic moved into Python |
| Naming | Pass | No new columns or models |
| Keys | N/A | Bronze table; natural key `UNIQUE (jurisdiction_id, url_sha256)` already declared; no schema change |
| Calendar years | N/A | |
| Scope label matches filter | N/A | |
| Match evidence on filtered tiles | N/A | |
| Docs | Pass | No new docs (roadmap note still owed, see 🟡 2) |
| Telemetry and logging | Pass | No new logging; existing code uses loguru |
| Tests | Partial | Regression test for the loader fails before the fix and passes after. No test for the `scrape.py` claim (🟡 3) |
| Shared libraries | Pass | `packages/scrapers/tests` run locally: 83 passed. No package depends on `scrapers.suiteone.scrape._UPSERT`, and dbt only filters on `meeting_date_source` (`stg_suiteone_meeting_documents`, `jurisdiction_minutes_publish_lag`), which the claim doesn't change |

## Test Coverage
Run locally on `7681446e`:
- `TEST_DATABASE_URL=postgresql://postgres@localhost:5499/loadertest RUN_LIVE_TESTS=1 pytest tests/test_scraped_meetings_loader_keeps_suiteone.py`:
  2 passed.
- The same command with the loader swapped back to the `origin/main` version: 2 failed (`:61` and `:103`). The
  regression test catches the bug.
- Without `RUN_LIVE_TESTS`: 1 passed, 1 skipped, which is what CI runs.
- `pytest packages/scrapers/tests` (with the worktree's `scrapers` on the path): 83 passed.
- Ad-hoc Postgres scenario (crawl, then SuiteOne upsert, then crawl twice) confirmed the claim works and that rows
  are neither lost nor duplicated. It's described under 🟡 3.
- `ruff check`: the new test is clean. No new findings on the changed lines in the loader or `scrape.py`. Those files
  already had findings (S110 in `scrape.py`, typing/BLE001 in the loader).
- Note: the shared `.venv` resolves `scrapers` to the main checkout's editable install, so running the code outside
  pytest (whose `pytest.ini` `pythonpath` fixes this) can pick up the old `scrape.py`.
- Not run against the home warehouse (5433), and `dbt ls` was not run: the warehouse isn't reachable from this
  session, and no dbt model changed.

## Verdict
**approve-with-nits.** The fix is correct. The DELETE/ON CONFLICT logic no longer loses SuiteOne rows or creates
duplicates, and the `%%` escaping is right. Before merge, fix the live test so it can't commit a
`DROP TABLE ... CASCADE` (🟡 1). Then add the roadmap line, or switch to `Refs #393` (🟡 2), and add the
crawl, SuiteOne, crawl sequence to the live test (🟡 3). Open an `action-item` issue for the broken `MIGRATION_PATH`.
