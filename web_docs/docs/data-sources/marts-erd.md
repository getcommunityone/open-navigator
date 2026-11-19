---
displayed_sidebar: developersSidebar
sidebar_position: 2
---

# Marts ERD (data dictionary)

The dbt marts, the tables the API reads from the `public` schema, drawn as data-dictionary ERDs — **one
diagram per subject area**, so each file is a normal size you can open in the IDE or in draw.io. Generated from
the marts' `schema.yml` files: every column, its `data_type` and description, the primary key, and each foreign
key constraint (within the area).

- **Entity view**: the area's tables with headers (name, row count, grain) and key columns only, plus a line for
  every in-area foreign key.
- **Full view**: the same layout with every column's type and meaning.

| Subject area | Entity | Full |
|---|---|---|
| Jurisdictions | [png](pathname:///img/erd/marts_jurisdictions_entity.png) · [drawio](/img/erd/marts_jurisdictions_entity.drawio) | [png](pathname:///img/erd/marts_jurisdictions_full.png) · [drawio](/img/erd/marts_jurisdictions_full.drawio) |
| Events and meetings | [png](pathname:///img/erd/marts_events_and_meetings_entity.png) · [drawio](/img/erd/marts_events_and_meetings_entity.drawio) | [png](pathname:///img/erd/marts_events_and_meetings_full.png) · [drawio](/img/erd/marts_events_and_meetings_full.drawio) |
| Bills and policy | [png](pathname:///img/erd/marts_bills_and_policy_entity.png) · [drawio](/img/erd/marts_bills_and_policy_entity.drawio) | [png](pathname:///img/erd/marts_bills_and_policy_full.png) · [drawio](/img/erd/marts_bills_and_policy_full.drawio) |
| People and organizations (MDM) | [png](pathname:///img/erd/marts_people_and_organizations_mdm_entity.png) · [drawio](/img/erd/marts_people_and_organizations_mdm_entity.drawio) | [png](pathname:///img/erd/marts_people_and_organizations_mdm_full.png) · [drawio](/img/erd/marts_people_and_organizations_mdm_full.drawio) |
| Elections | [png](pathname:///img/erd/marts_elections_entity.png) · [drawio](/img/erd/marts_elections_entity.drawio) | [png](pathname:///img/erd/marts_elections_full.png) · [drawio](/img/erd/marts_elections_full.drawio) |
| Nonprofits and grants | [png](pathname:///img/erd/marts_nonprofits_and_grants_entity.png) · [drawio](/img/erd/marts_nonprofits_and_grants_entity.drawio) | [png](pathname:///img/erd/marts_nonprofits_and_grants_full.png) · [drawio](/img/erd/marts_nonprofits_and_grants_full.drawio) |
| Topics and tags | [png](pathname:///img/erd/marts_topics_and_tags_entity.png) · [drawio](/img/erd/marts_topics_and_tags_entity.drawio) | [png](pathname:///img/erd/marts_topics_and_tags_full.png) · [drawio](/img/erd/marts_topics_and_tags_full.drawio) |
| Browse and reports | [png](pathname:///img/erd/marts_browse_and_reports_entity.png) · [drawio](/img/erd/marts_browse_and_reports_entity.drawio) | [png](pathname:///img/erd/marts_browse_and_reports_full.png) · [drawio](/img/erd/marts_browse_and_reports_full.drawio) |
| Other | [png](pathname:///img/erd/marts_other_entity.png) · [drawio](/img/erd/marts_other_entity.drawio) | [png](pathname:///img/erd/marts_other_full.png) · [drawio](/img/erd/marts_other_full.drawio) |

The PNGs carry the diagram inside them, so draw.io (or diagrams.net) can open a PNG and edit it. They are stored
as normal git blobs (not LFS), so a checkout can preview them.

A foreign key that points at a table in another subject area is omitted from the area diagram (both ends must be
in the same file). Pass `--one-canvas` only when you need every area on one canvas for tooling; that output is too
large to open in most viewers.

## How to read it

- **Header colour**: green is an event table (one row per event or record), orange an entity table (one row per
  thing, the target of other tables' foreign keys), and blue a summary table (one row per measure or group).
  Tables are named by the entity they hold, never `dim_`/`fact_`.
- **Column names**: blue is the primary key, purple a foreign key, grey a column no key uses.
- **Lines**: right-angled, from the foreign-key row to the key row it points at. A crow's foot means many, a bar
  means one.
- **Row counts**: with `--dsn` the generator counts every mart that is built as a table in the `gold` schema
  (an exact `count(*)`) and shows `N rows` in its header. A mart that isn't built there says "rows not measured yet",
  never 0. The legend names the schema and the minute the counts were taken.
- **Subject-area totals**: each area's title shows its table count, its row total and how many of its tables have a
  primary key. The total adds up only the tables that were measured, and the title says how many that was when some
  weren't. For a measured table the key is Postgres's own (`pg_constraint`), so a model that declares a key the
  database doesn't hold shows as missing. For an unmeasured one it is the dbt declaration.
- **Views in `public`**: the API reads `public`, which holds views over `gold`. A view can't carry a primary key, so
  the keys are checked on the `gold` tables the views read.

## Regenerate

The drawer is the `erd` workspace package (`packages/erd`):

```bash
PYTHONPATH=packages/erd/src python -m erd --models dbt_project/models/marts --out web_docs/static/img/erd --name marts \
  --dsn postgresql://postgres:password@localhost:5433/open_navigator --schema gold
node packages/erd/src/erd/drawio_render.js web_docs/static/img/erd/marts_*_entity.drawio web_docs/static/img/erd/marts_*_full.drawio
```

Leave out `--dsn` to draw from the dbt declarations alone (no counts). `--dsn` needs `psycopg2`
(`pip install 'communityone-erd[db]'`). Per-area routing is seconds, not minutes; row counts still take a couple of
minutes on a large warehouse.

The second command needs Node 20.15 or later and `playwright` (`npm install playwright`). It loads draw.io's viewer
from viewer.diagrams.net. Where that site is blocked, set `VIEWER=` to a local copy of `viewer-static.min.js` from the
jgraph/drawio repository. Render is 1× by default (`SCALE=2` for denser print). PNGs are capped at 3500 px on the longer side
(`MAX_SIDE=`) so they open in the IDE; open the `.drawio` for full resolution.

Subject areas are set by name prefix in `SUBJECT_AREAS` (`packages/erd/src/erd/dbt_model.py`). A new mart lands in
the first area whose prefix matches its name, or in "Other". Add a prefix there to place it.
