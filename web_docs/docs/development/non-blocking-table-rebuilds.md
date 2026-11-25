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
    pre_hook=["{{ swap_guard() }}"],
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
- **`swap_guard_check()`** must be the **first** post-hook. It runs right after the renames, before COMMIT, and does two
  things:
  - It fails the build if the swap didn't run in the transaction `swap_guard()` started.
  - It ends the `lock_timeout` window (`set local lock_timeout to default`). The timeout is meant for the renames only.
    Later post-hooks lock other tables that models running in parallel in the same dbt run may hold, and they must wait
    as before.

  In #938 the timeout was still on when `mdm_bridge_org_jurisdiction`'s `ADD CONSTRAINT … REFERENCES mdm_organization`
  ran. It timed out and threw away a 10-minute build.
- **`pg_trgm`** is created once per invocation in `on-run-start` (`dbt_project.yml`). Trigram indexes now build before
  any hook, so a per-model hook would come too late on a fresh warehouse.
- **No before-begin hooks** (`{'sql': ..., 'transaction': false}` in `pre_hook`) on these models. dbt sends a literal
  `commit;` before those, and psycopg2 then never opens another transaction on that connection. Every later statement
  autocommits, including the two renames, so they stop being atomic, and `SET LOCAL` and transaction locks end with
  their own statement. The first version of this fix had one (for `CREATE EXTENSION`), and it cost two things:
  - A reader caught between the renames got `relation "gold.mdm_person" does not exist`.
  - `lock_timeout` never applied, so one swap waited 365 seconds with readers queued behind it.

  `swap_guard_check()` now catches this. An after-commit post-hook (`'transaction': false` in `post_hook`) is harmless.
- **`ensure_search_indexes`** finds an index by definition when its entry has a `match` key, so it counts the config index
  (generated name) as present instead of building a duplicate. Only valid, non-partial indexes count.

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

[#938](https://github.com/getcommunityone/open-navigator/issues/938) moved every other model's index hooks into `indexes`
config (29 files), plus `event_uncontested_item`'s unnamed one. It also gave `swap_guard` to the largest tables:

| Model | Size |
|---|---|
| `event_documents` | 8.5 GB |
| `grant` | 4.1 GB |
| `mdm_organization` | 2.2 GB |
| `mdm_bridge_org_jurisdiction` | 1.7 GB |
| `mdm_bridge_person_jurisdiction` | 1.5 GB |
| `bills` | 0.8 GB |
| `mdm_organization_nonprofit` | 0.7 GB |

`event_documents`' `ANALYZE` became an after-commit post-hook, so it no longer runs under the swap's lock. No model in
`dbt_project/models` builds an index in a hook any more.

## Still open: views over a rebuilt table

The swap is atomic and short, but dbt then runs `drop table … __dbt_backup cascade`. Views are bound to the old table's
OID, so the views over it (the `public` serving views, and dbt view models) are dropped with it:
- the `public` ones come back only when `publish_public_serving` runs at the end of the run;
- unselected dbt view models don't come back at all after a selected run.

Readers of `public` views can therefore still get "relation does not exist" while a rebuild runs. That is
[#940](https://github.com/getcommunityone/open-navigator/issues/940). Until it's fixed, after a selected run, recreate the
views with `./scripts/dbt.sh run --select config.materialized:view`.
