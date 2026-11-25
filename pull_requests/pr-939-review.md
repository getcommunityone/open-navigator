---
pr: 939
branch: fix/935-mdm-person-nonblocking-rebuild
title: "fix(dbt): rebuild mdm_person without locking readers or losing its trigram index"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: data-dbt-specialist subagent (read-only) and coordinator
head_sha: 20e364b6
verdict: approve
---

# PR Review: fix(dbt): rebuild mdm_person without locking readers or losing its trigram index

## Summary

This PR moves `mdm_person`'s trigram GIN index from a post-hook (built inside the swap, under ACCESS EXCLUSIVE, and lost
on alternate builds) into the model's `indexes` config, which dbt builds on the tmp table before the swap. It also adds
`swap_guard()` / `swap_guard_check()`: a transaction-scoped `lock_timeout` and advisory lock, plus a check that the swap
ran in one transaction.

The first review found a **critical regression** in the branch as first pushed. A `transaction: false` `CREATE EXTENSION`
pre-hook made dbt send `commit;` first, after which psycopg2 never opened a transaction. The renames then autocommitted,
and a reader between them got `relation "gold.mdm_person" does not exist`. This was confirmed in the Postgres log at
19:25:19.280 during the author's own test, and it also explained why `SET LOCAL` "didn't survive". Fixed in `8d588c6d`
and re-measured; all findings are addressed. Verdict: **approve**.

## Scope of Change

- Files changed: 5 (+~190 / -~10), plus this review
- Areas touched: dbt_project (macros, one model), web_docs, api (docstring only)
- Commits:
  - 44d87998 fix(dbt): build mdm_person's trigram index before the swap and guard the swap (WIP, re-testing)
  - 18963eab docs(web_docs): rebuilding a large table without locking readers
  - 60cf19d4 docs(pr-939): auto-write rubric review [skip review] (CI bot)
  - 8d588c6d fix(dbt): keep the mdm_person swap in one transaction; transaction-scoped swap_guard with a check
- Range reviewed: `8fa69852..20e364b6`

## CI Status

| Check | Status |
|---|---|
| Required checks | see PR checks on the head (pending at time of writing) |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data in a served path: clean (no figures; the API change is a docstring).
- Personal data: clean (no new data; same `mdm_person` rows).
- Destructive or bulky changes: none. No table is dropped beyond dbt's own backup swap; `data/cache` is untouched.

## Strengths

- Moving the GIN index into `indexes` fixes both the build-under-lock and the vanishing-name problems at their cause.
- `swap_guard_check()` turns the dangerous misconfiguration (a before-begin hook) into a loud build failure. That's the
  regression test the first version lacked, and it protects #938's 29 models from copying the bug.

## Findings

### 🔴 Blocking (Critical)

1. `mdm_person.sql:9-12`: the `{'sql': "CREATE EXTENSION …", 'transaction': false}` pre-hook broke the swap's
   transaction, so the renames weren't atomic, and `SET LOCAL` and xact locks ended per statement. Verified:
   - the Postgres log shows `relation "gold.mdm_person" does not exist` from the probe reader at the rename, and "there
     is no transaction in progress" at the builds' COMMITs;
   - psycopg2 reproduces it on 5433.

   **Fixed:** the hook is removed (`pg_trgm` is created in-transaction); the guard is `SET LOCAL lock_timeout` +
   `pg_try_advisory_xact_lock` + a recorded txid; `swap_guard_check()` asserts the txid after the renames.

### 🟡 Should fix (Important)

2. With session scope, the post-commit `drop … cascade` of the backup ran under the 10s timeout. **Fixed** by the
   transaction scope, which ends at COMMIT.
3. No regression test. **Fixed** with `swap_guard_check()`, which fails any build whose swap leaves the guarded
   transaction.

### 🔵 Nits / suggestions (Minor)

4. The comment saying the timeout lasts "until dbt closes the connection at the end of the invocation" was wrong; dbt
   closes per node. **Moot**: session scope is removed.
5. `ensure_search_indexes`: `match` was unescaped, and partial or invalid indexes counted. **Fixed**: quotes are escaped,
   and the check requires `indisvalid and indpred is null`.
6. The issue's contract said transaction-scoped. **Now matches** the code again.
7. `api/routes/search_postgres.py:516` docstring named the old index. **Fixed** (docstring only; ruff findings in that
   file are 133 on both `main` and the branch).

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `fix/935-…`; `Closes #935`; four parts; follow-up #938 |
| Conventional Commits | ✅ | |
| No fabricated data | ✅ | |
| New Python in `packages/` | n/a | |
| dbt for transformations | ✅ | config and macros only |
| Naming / Calendar years | n/a | |
| Keys | ✅ | `mdm_person` PK and FKs unchanged |
| Scope label / match evidence | n/a | |
| Docs | ✅ | `web_docs/docs/development/non-blocking-table-rebuilds.md` (docs build passed locally on the prior head) |
| Telemetry and logging | n/a | |
| Tests | ✅ | `swap_guard_check()` runtime assertion, plus measured scenarios; `dbt test --select mdm_person` 10 pass, 1 pre-existing data warn (`assert_mdm_person_not_overmerged`) |
| Shared libraries | n/a | |

## Test Coverage

Local warehouse (localhost:5433), full `mdm_person` rebuilds (13.8M rows) on the fixed head:
- Reader every 0.1s during a build: 2,812 reads, slowest 0.087s, 0 errors; `swap_guard_check` passed; the Postgres log has
  no "does not exist" and no "no transaction in progress".
- Second build during the first's index phase: refused in 0.12s; the first finished.
- A reader transaction through the swap: rolled back after 10s on lock timeout; 3,012 reads, slowest 11.5s, 0 errors; the
  old table served all rows; no leftover tmp or backup table or advisory lock.
- The trigram index exists exactly once; `ensure_search_indexes` built nothing.
- `python -m models.odcs --check`: current.

## Verdict

**approve**: merge when the required CI checks are green on the head.
