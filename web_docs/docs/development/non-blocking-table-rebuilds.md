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
      {'sql': "CREATE EXTENSION IF NOT EXISTS pg_trgm", 'transaction': false},
      "{{ swap_guard() }}"
    ],
    post_hook=[
      {'sql': "{{ swap_guard_release() }}", 'transaction': false}
    ]
  )
}}
```

- **Indexes go in `indexes`, never in a post_hook.** dbt builds them on the tmp table before the swap, under a generated
  name, so they never collide with the backup's and never build under the lock.
- **`swap_guard()`** (`dbt_project/macros/swap_guard.sql`) does two things:
  - It takes a session advisory lock keyed on the relation, so a second build of the same model fails immediately with
    "swap_guard: another build of … is running".
  - It sets `lock_timeout` (10s), so a swap that can't get its lock fails fast instead of queuing every reader.
- **`swap_guard_release()`** resets `lock_timeout` and releases the advisory lock after the commit. If the build fails
  first, both end when dbt closes the connection.
- **Session scope, not `SET LOCAL`.** Measured on this dbt (1.13): a `SET LOCAL` from a hook was gone by the next
  statement (a probe read `lock_timeout = 0`), and a transaction advisory lock is released just as fast. In the first
  version of this fix that let a swap wait 365 seconds with readers queued behind it.
- **`ensure_search_indexes`** finds an index by definition when its entry has a `match` key, so it counts the config index
  (generated name) as present instead of building a duplicate.

## Measured on mdm_person (local warehouse, 25 Nov 2026)

| Check | Result |
|---|---|
| Full rebuild (13.8M rows, ~3-4 min) with a reader querying every 0.5s | 338 reads, slowest 0.175s, none over 1s, no errors |
| Trigram index after two consecutive builds | exactly one; `ensure_search_indexes` built nothing |
| Second build started while one runs | refused in 0.09s ("another build … is running"); the first finished normally |
| A reader transaction holds the table open through the swap | the swap gave up after 10s ("canceling statement due to lock timeout"); the slowest reader waited 9.95s; the old table kept serving; re-run the model afterwards |

The cost is the timeout case: a build that can't swap within 10 seconds fails and must be re-run. That's the intended
trade-off, since the alternative was freezing every reader for as long as the blocking query ran.

## Other models

About 30 other models still build named indexes in post_hooks, including `grant`, `mdm_organization`, `contact_official`,
`event_documents` and `jurisdictions`. They have the same lock and vanishing-index problems in proportion to their size.
Moving them to this pattern is
[#938](https://github.com/getcommunityone/open-navigator/issues/938).
