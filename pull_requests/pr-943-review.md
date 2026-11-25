---
pr: 943
branch: fix/941-pk-post-hook-target
title: "fix(dbt): render gold_pk_post_hook at run time and let Postgres name the key"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: data-dbt-specialist subagent (read-only) and coordinator
head_sha: 706fff0f
verdict: approve
---

# PR Review: fix(dbt): render gold_pk_post_hook at run time and let Postgres name the key

## Summary

Two fixes to the primary-key post-hooks, with a regression test:
- **Run-time rendering.** All 15 callers of `gold_pk_post_hook` (plus `serving_mdm_organization`) pass the hook as a
  string, so it renders at run time against the `gold` table instead of the parse-time `public.<model>`.
- **Unnamed keys.** The macro adds the key without a fixed name, so it no longer collides with the `__dbt_backup`'s
  `<model>_pkey` on every rebuild after the first.

The read-only review found no critical issues; its findings are addressed below. Verdict: **approve**.

## Scope of Change

- Files changed: 19 (macro, 16 models, 1 schema yml, 1 test), docs page
- Areas touched: dbt_project, tests, web_docs
- Commits: 2ae7c577 (fix), docs commit, 79a582bf (review fixes), plus CI bot review commits
- Range reviewed: `origin/main...706fff0f`

## CI Status

| Check | Status |
|---|---|
| Required checks | see PR checks on the head |

## Scans (secrets, fabricated data, personal data, destructive data changes)

All clean. Keys only; no data or rows change.

## Strengths

- A small, consistent fix at the root cause. `serving_mdm_organization` now uses the shared macro.
- The macro docstring, the docs and a static test cover both failure modes.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

1. Issue #941 asked for two consecutive builds of four named models. **Done** on the local warehouse:
   - `serving_mdm_organization` and `serving_mdm_organization_nonprofit` built twice;
   - `event_document_lexicon` built twice (key `_pkey1` then `_pkey`: Postgres picking a free name);
   - `jurisdiction_state_aggregate` built twice (about 25 min each).

   Each ends with exactly one primary key.
2. Once the key hook stops failing, these models' rebuilds commit, so their remaining **named post-hook indexes** start
   vanishing on alternate builds. On `main`, the failing hook rolled those rebuilds back. **Handled by sequencing:** #938
   moves exactly these models' indexes into `indexes` config, and it merges right after this PR.
3. No regression test. **Fixed:** `tests/test_dbt_pk_hooks.py` fails if a model calls `gold_pk_post_hook` unquoted inside
   `config()`, or if any hook adds a named primary key. Both checks fail on `main`'s model files and pass here.

### 🔵 Nits / suggestions (Minor)

4. A promoted unique index keeps its own name, not `<table>_pkey`. **Fixed** in the docs and macro comment.
5. The docs overstated the old bug. **Fixed:** builds failed where `public.<model>` was a view or missing, and silently
   skipped only where it was a table with a key. The hook is a no-op on contracted callers.
6. `serving_mdm_organization` declared no primary key anywhere. **Fixed** in `_schema_gold_primary_keys.yml`, with
   `unique`/`not_null` tests.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `fix/941-…`; `Closes #941`; four parts |
| Conventional Commits | ✅ | |
| dbt for transformations | ✅ | |
| Keys | ✅ | the fix's whole point: keys actually attach on the gold tables |
| Docs | ✅ | `web_docs/docs/development/non-blocking-table-rebuilds.md` |
| Tests | ✅ | `tests/test_dbt_pk_hooks.py` (fails on `main`) |

## Test Coverage

- `dbt parse`, then the manifest: all 15 hooks kept for run time, none targeting `public`.
- Two consecutive builds of each of the 4 models above, each with one primary key; no tmp or backup tables left.
- `pytest tests/test_dbt_pk_hooks.py`: 3 passed (2 fail on `main`'s files).

## Verdict

**approve**: merge when the required checks are green, then merge #938 right after.
