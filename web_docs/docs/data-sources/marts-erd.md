---
displayed_sidebar: developersSidebar
sidebar_position: 2
---

# Marts ERD (data dictionary)

The dbt marts, the tables the API reads from the `public` schema, drawn as two ERDs in the data-dictionary
format. Both are generated from the marts' `schema.yml` files, so they show what the models declare: every column,
its `data_type` and description, the primary key, and each foreign key constraint.

- **Entity view**: tables grouped into subject areas, each table's header (name and grain) and its key
  columns only, with a line for every foreign key.
- **Full view**: the same subject areas and table order, with every column's type and meaning.

| View | PNG | draw.io (editable) |
|---|---|---|
| Entity | [marts_entity.png](/img/erd/marts_entity.png) | [marts_entity.drawio](/img/erd/marts_entity.drawio) |
| Full | [marts_full.png](/img/erd/marts_full.png) | [marts_full.drawio](/img/erd/marts_full.drawio) |

The PNGs carry the diagram inside them, so draw.io (or diagrams.net) can open a PNG and edit it.

![Marts ERD, entity view](/img/erd/marts_entity.png)

## How to read it

- **Header colour**: green is an event table (one row per event or record), orange an entity table (one row per
  thing, the target of other tables' foreign keys), and blue a summary table (one row per measure or group).
  Tables are named by the entity they hold, never `dim_`/`fact_`.
- **Column names**: blue is the primary key, purple a foreign key, grey a column no key uses.
- **Lines**: right-angled, from the foreign-key row to the key row it points at. A crow's foot means many, a bar
  means one.
- **Row counts**: the headers say "rows not measured yet". The diagrams are drawn from the dbt declarations, not
  from the warehouse, so they show no counts.

## Regenerate

The drawer is the `erd` workspace package (`packages/erd`):

```bash
PYTHONPATH=packages/erd/src python -m erd --models dbt_project/models/marts --out web_docs/static/img/erd --name marts
node packages/erd/src/erd/drawio_render.js web_docs/static/img/erd/marts_entity.drawio web_docs/static/img/erd/marts_full.drawio
```

The second command needs Node 20.15 or later and `playwright` (`npm install playwright`). It loads draw.io's viewer
from viewer.diagrams.net. Where that site is blocked, set `VIEWER=` to a local copy of `viewer-static.min.js` from the
jgraph/drawio repository.

Subject areas are set by name prefix in `SUBJECT_AREAS` (`packages/erd/src/erd/dbt_model.py`). A new mart lands in
the first area whose prefix matches its name, or in "Other". Add a prefix there to place it.
