---
sidebar_position: 45
title: Why declared foreign keys disappeared, and the fix
description: dbt's drop-with-cascade silently removed foreign keys on rebuild; ensure_declared_foreign_keys puts them back after every run (#783).
---

# Why declared foreign keys disappeared, and the fix

Issue [#783](https://github.com/getcommunityone/open-navigator/issues/783). Decision recorded 2026-11-23.

## What happened

A read-only audit of the local warehouse on 2026-11-23 found that 135 of 136 `gold` tables have a primary key,
but 27 tables declare a foreign key in dbt that Postgres does not have.

The cause is in dbt itself. When dbt rebuilds a table it renames the new table in and then drops the old relation
with `drop ... if exists ... cascade` (`dbt/include/global_project/macros/relations/drop.sql`). The `CASCADE`
removes every child foreign key that pointed at the old parent. A table that is never dropped (an incremental
model such as `event_meeting`) keeps its keys, which is why the loss looked random:
`gold.jurisdictions` had 1 live inbound key of about 20 declared.

## The decision

Keep the keys declared in `schema.yml`, and restore any that a rebuild removed.

- `ensure_declared_foreign_keys` (`dbt_project/macros/ensure_declared_foreign_keys.sql`) reads every
  `type: foreign_key` constraint in the dbt graph, model-level or column-level, and runs
  `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY` for each one Postgres lacks.
- It runs from `on-run-end` after `ensure_search_indexes()`, so a `dbt run` cannot leave keys missing.
- Run it by hand with `dbt run-operation ensure_declared_foreign_keys`, or add
  `--args '{dry_run: true}'` to see what it would add.

It never deletes rows. A key is skipped, with a log line naming the table and the count, when:

| Case | What the log says |
|---|---|
| The child or parent table is not built yet | `child or parent table not built yet` |
| The parent has no unique key on the referenced columns | `has no unique key on (...)` |
| The child has rows with no matching parent | `N orphan row(s); not added` |
| `to:` is not written as `ref('model')` | `cannot resolve parent or columns` |

A key that already exists on the same child columns and the same parent is left alone, whatever its name.

`gold.ballot_measures` was the one gold table without a primary key. It is now in the
`ensure_gold_primary_keys` list on `ballot_measure_uid`. That macro stops with an error if it finds NULL keys, and
Postgres refuses the key if two rows share one, so it cannot attach a wrong key silently. Run it with
`dbt run-operation ensure_gold_primary_keys --args '{dry_run: false}'`.

## Audit query

After a `dbt run`, this should return no rows for keys declared in dbt. Compare it with the models that declare a
`foreign_key` constraint:

```sql
select conrelid::regclass as child, conname, confrelid::regclass as parent
from pg_constraint
where contype = 'f' and connamespace = 'gold'::regnamespace
order by 1, 2;
```

## Finding the tables with orphan rows (#786)

`ensure_declared_foreign_keys` skips a key when the child has rows with no parent. To list every such candidate
with its orphan count and a few sample values in one run, read-only:

```bash
dbt run-operation audit_orphan_foreign_keys
dbt run-operation audit_orphan_foreign_keys --args '{schema: gold, samples: 5, show_clean: false}'
```

A candidate is a `*_id` column whose name and type match another table's single-column primary key, with no foreign
key between them. It matches by name only, so check that a pair is a real relationship before declaring it. It only
runs `SELECT` queries, and it is not part of `on-run-end` because it scans every candidate table.

What the model code says about two of the four tables named in #786 (the counts still need your warehouse):

| Table | Why orphans can exist |
|---|---|
| `events_text_search.event_id` | The model uses `COALESCE(event mart id, the id already on bronze)`. A transcript whose video has no row in the event mart keeps its bronze id, which points at nothing. |
| `event_person.person_id` | The model header says the extracted person is resolved to `civic_person` "later", so orphans may be expected until that step runs. |

`localview_events` and the `civic_*` tables are loaded by Python, not built by dbt, so the cause is in their loaders.

## Not fixed here

Tables whose `*_id` columns match another table's key but have orphan rows keep no key, and each needs its own
follow-up: the `civic_*` loader tables, `event_person.person_id` (102,840 orphans), `events_text_search.event_id`
(11,424) and `localview_events.event_id` (217). `dim_jurisdictions_master` also breaks the no-`dim_` naming rule in
`CLAUDE.md`.
