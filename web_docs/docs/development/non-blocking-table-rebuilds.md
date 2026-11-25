---
sidebar_position: 39
title: Rebuilding a large table without locking readers
description: Why a dbt table rebuild froze the API and lost its indexes, the pattern that fixes it (indexes in config, swap_guard), and how it was measured on mdm_person.
---

# Rebuilding a large table without locking readers

[Issue #935](https://github.com/getcommunityone/open-navigator/issues/935). Rebuilding `gold.mdm_person` (13.8M rows)
used to freeze every API query on people for minutes, and on every other build it lost its trigram search index. This
page explains why and gives the pattern any large `table` model should use.

## Why it locked

dbt's `table` materialization (`dbt/include/global_project/macros/materializations/models/table.sql`) does this:

1. Build `<model>__dbt_tmp` with the model's SQL. This doesn't lock the live table.
2. Build the indexes declared in the model's **`indexes` config** on `<model>__dbt_tmp`. This doesn't lock the live
   table either.
3. Rename the live table to `<model>__dbt_backup` and rename `<model>__dbt_tmp` in. Each rename takes an ACCESS
   EXCLUSIVE lock.
4. Run the **post_hooks**, then commit.
5. Drop `<model>__dbt_backup`.

Three things went wrong:

- **An index built in a post_hook builds under the lock.** `mdm_person` built its GIN `gin_trgm_ops` index in a post_hook,
  so the index ran in step 4, after the renames. Every query on `mdm_person` waited while it built over 13.8M names.
- **A named index in a post_hook vanishes on every other build.** In step 4 the backup still owns the index name, so
  `CREATE INDEX IF NOT EXISTS <name>` finds the name taken and skips. Step 5 then drops the index along with the backup.
  `ensure_search_indexes` (on-run-end) rebuilt it after the run, so the index alternated between "built under the lock"
  and "missing until the backstop". This is the "trigram index drops after a rebuild" seen before.
- **The renames wait with no limit, and readers queue behind them.** A rename can't get its lock while any query is
  reading the table. While the rename waits, every new query waits behind it too. Two overlapping builds of the same
  model made this worse.

## The pattern

For a large `table` model:

```sql
{{
  config(
    materialized='table',
    indexes=[
      {'columns': ['state_code'], 'type': 'btree'},
      {'columns': ['full_name gin_trgm_ops'], 'type': 'gin'}   -- operator classes pass through as written
    ],
    pre_hook=[
      "CREATE EXTENSION IF NOT EXISTS pg_trgm",
      "{{ swap_guard() }}"
    ],
    post_hook=[
      "{{ swap_guard_check() }}"
    ]
  )
}}
```

- **Indexes go in `indexes`, never in a post_hook.** dbt builds them on the tmp table before the swap, under a generated
  name, so they never collide with the backup's and never build under the lock.
- **`swap_guard()`** (`dbt_project/macros/swap_guard.sql`) is an in-transaction pre-hook. It does three things:
  - It sets `SET LOCAL lock_timeout = '10s'`, so a swap that can't get its lock rolls back fast (the old table keeps
    serving) instead of queuing every reader.
  - It takes `pg_try_advisory_xact_lock` on the relation, so a second build of the same model fails immediately with
    "swap_guard: another build of … is running".
  - It records the transaction id.

  All of this ends at the swap's COMMIT, so none of it applies to the backup drop or to other models.
- **`swap_guard_check()`** is an in-transaction post-hook that runs after the renames and before COMMIT. It fails the build
  if the swap didn't run in the transaction `swap_guard()` started.
- **No before-begin hooks** (`{'sql': ..., 'transaction': false}` in `pre_hook`) on these models. dbt sends a literal
  `commit;` before those, and psycopg2 then never opens another transaction on that connection. Every later statement
  autocommits, including the two renames, so they stop being atomic, and `SET LOCAL` and transaction locks end with
  their own statement. The first version of this fix had one (for `CREATE EXTENSION`), and it cost two things:
  - A reader caught between the renames got `relation "gold.mdm_person" does not exist`.
  - `lock_timeout` never applied, so one swap waited 365 seconds with readers queued behind it.

  `swap_guard_check()` now catches this. An after-commit post-hook (`'transaction': false` in `post_hook`) is harmless.
- **`ensure_search_indexes`** finds an index by definition when its entry has a `match` key, so it counts the config index
  (generated name) as present instead of building a duplicate. Only valid, non-partial indexes count.

## Primary keys added in hooks (#941)

Models whose key isn't a dbt contract constraint add it with `gold_pk_post_hook('<cols>')`. Two rules, both learned the
hard way ([#941](https://github.com/getcommunityone/open-navigator/issues/941)):

- **Pass the hook as a string:** `post_hook=["{{ gold_pk_post_hook('word') }}"]`. Called directly inside `config()`
  (`post_hook=[gold_pk_post_hook('word')]`), the macro renders when the model is parsed, when `{{ this }}` still points
  at `public.<model>` instead of the `gold` table. All 15 callers had that bug, so their keys were never attached.
- **Don't name the key.** Post-hooks run after the old table is renamed to `__dbt_backup`, which still owns an index
  called `<model>_pkey`. A fixed name fails every rebuild after the first ("relation … _pkey already exists"). The macro
  now runs `add primary key …` and lets Postgres pick a free name (`<model>_pkey`, or `_pkey1` while the backup holds
  the first).

## Measured on mdm_person (local warehouse, 25 Nov 2026)

| Check | Result |
|---|---|
| Full rebuild (13.8M rows, ~5 min) with a reader querying every 0.1s | 2,812 reads, slowest 0.087s, none over 1s, no errors; `swap_guard_check` passed; nothing new in the Postgres log (no "does not exist", no "no transaction in progress") |
| Trigram index after consecutive builds | exactly one; `ensure_search_indexes` built nothing |
| Second build started during the first's index phase | refused in 0.12s ("another build … is running"); the first finished normally |
| A reader transaction holds the table open through the swap | the swap rolled back after 10s ("canceling statement due to lock timeout"); 3,012 reads, slowest 11.5s, none errored; the old table kept serving all rows; no tmp or backup table and no advisory lock left behind; re-run the model afterwards |

The cost is the timeout case: a build that can't swap within 10 seconds fails and must be re-run. That's the intended
trade-off, since the alternative was freezing every reader for as long as the blocking query ran.

## Other models

About 30 other models still build named indexes in post_hooks, including `grant`, `mdm_organization`, `contact_official`,
`event_documents` and `jurisdictions`. They have the same lock and vanishing-index problems in proportion to their size.
Moving them to this pattern is
[#938](https://github.com/getcommunityone/open-navigator/issues/938).
