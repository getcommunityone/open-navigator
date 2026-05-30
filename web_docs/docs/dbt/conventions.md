---
sidebar_position: 4
---

# dbt conventions and governance (Stage 3 blueprint)

This document is the governance blueprint for the `open_navigator_dbt` project. It defines naming, directory layout, model contracts, intermediate decomposition patterns, and the rule for how the FastAPI app talks to the database.

## Grounding facts (current state, 2026-05-27)

This blueprint is grounded in what is actually in the repo today — not aspirational targets:

- **44 dbt models** under [dbt_project/models/](dbt_project/models/) (not 467; that figure is wrong).
- Existing directory layout: `staging/` (3 active + 3 `.bak`), `intermediate/` (17), `marts/` (14), `bronze/` (10 AI-extraction models that build bronze tables in-database from JSON).
- Existing naming: `int_*` is well adopted (17/17). `stg_*` is adopted for the 3 active staging models but with prefix `stg_bronze_*` (leaks the source layer name). `fct_*` / `dim_*` are not used at all — marts are named directly (e.g. `jurisdictions.sql`, `event.sql`).
- Sources live at [bronze schema](dbt_project/models/staging/_staging.yml) in `open_navigator` Postgres; no `raw_*` schemas exist yet. Stage 2 ingestion ports continue to write to `bronze.bronze_*` tables for behavior parity. The new ingestion layer (`packages/core-lib`) will produce `raw_<source>.*` tables in a later refactor — until then, **`bronze` is the only source layer dbt sees**.

The intent of this blueprint is to **establish standards going forward** and provide a concrete migration path for existing models. It does NOT mass-rename existing models — that work happens model-by-model in follow-up PRs.

---

## 1. Medallion directory & naming standards

### 1.1 Directory layout (target)

```
dbt_project/models/
├── staging/
│   ├── _sources.yml                       # all bronze/raw source declarations live here
│   ├── _schema.yml                        # per-model contracts + tests
│   └── stg_<source>__<entity>.sql         # one per (source, entity)
├── intermediate/
│   ├── _schema.yml
│   └── int_<topic>__<step>.sql            # business-logic glue; can fan out into steps
└── marts/
    ├── core/                              # cross-cutting facts/dims used by API + analytics
    │   ├── _schema.yml
    │   ├── fct_<event>.sql
    │   └── dim_<entity>.sql
    ├── quality/                           # data-quality summary marts (jurisdiction_mapping_quality_*)
    │   └── _schema.yml
    └── reporting/                         # ad-hoc reporting/aggregate marts
        └── _schema.yml
```

The `models/bronze/` directory in the repo is misnamed — its 10 files (`bronze_*_from_ai.sql`) build bronze tables from raw JSON inputs. They are *transformations* and should live under `staging/ai/`. **Proposed rename (separate PR):** `models/bronze/` → `models/staging/ai/`, files renamed to `stg_ai__<entity>.sql`. Until that PR lands, leave them where they are.

### 1.2 Naming conventions

| Prefix | Layer | Schema (in DB) | Materialization default | Example |
|---|---|---|---|---|
| `stg_<source>__<entity>` | Staging — 1:1 with a source table, light cleaning + type stabilization | `staging` | `view` | `stg_gsa__domains`, `stg_fec__contributions`, `stg_census__states` |
| `int_<topic>__<step>` | Intermediate — business glue, joins, dedup | `intermediate` | `table` | `int_jurisdictions__deduped`, `int_nonprofits__with_geo` |
| `fct_<event>` | Mart — event/transaction grain (one row per occurrence) | `marts` | `table` | `fct_meetings`, `fct_contributions`, `fct_ballot_measures` |
| `dim_<entity>` | Mart — entity grain (one row per noun, slowly changing) | `marts` | `table` | `dim_jurisdictions`, `dim_organizations`, `dim_mayors` |
| `rpt_<topic>` | Mart — reporting/aggregate (typically used by dashboards) | `marts` | `table` | `rpt_jurisdiction_mapping_quality_summary` |

Rules:
- **Double underscore (`__`)** separates the source/topic from the entity. This makes the lineage immediately obvious in `dbt ls` output and the docs site.
- `stg_*` references only `source()` — never another model.
- `int_*` references `stg_*` and other `int_*`. Never `source()` directly.
- `fct_*` / `dim_*` / `rpt_*` reference `stg_*` and `int_*`. Never `source()` directly.

### 1.3 Migration map for existing models

Don't rename in bulk. Apply during touch:

| Current name | Target name | Reason |
|---|---|---|
| `stg_bronze_decisions.sql` | `stg_ai__decisions.sql` | bronze is the source layer, not part of the model name; "decisions" come from the AI extraction source |
| `stg_bronze_events_cdp.sql` | `stg_cdp__events.sql` | source is CDP |
| `stg_bronze_events_text_ai.sql` | `stg_ai__transcripts.sql` | source is AI extraction |
| `int_jurisdictions.sql` | `int_jurisdictions__base.sql` | "base" makes its role in the chain clear |
| `int_jurisdictions_clean.sql` | `int_jurisdictions__deduped.sql` | name describes the operation |
| `int_jurisdictions_linked.sql` | `int_jurisdictions__matched.sql` | "linked" is ambiguous |
| `event.sql` (mart) | `fct_meetings.sql` | event-grain fact |
| `jurisdictions.sql` (mart) | `dim_jurisdictions.sql` | entity-grain dim |
| `organization_nonprofit.sql` | `dim_organizations.sql` | entity-grain dim |
| `ballot_measures.sql` | `fct_ballot_measures.sql` | event-grain fact |
| `jurisdiction_mapping_quality_summary*.sql` | `rpt_jurisdiction_mapping_quality_*.sql` | reporting aggregate |

**Migration recipe per file (preserves blame):**

```bash
git mv dbt_project/models/marts/event.sql dbt_project/models/marts/core/fct_meetings.sql
# Commit the rename alone, then in a second commit:
#   - Update ref('event') → ref('fct_meetings') across the project
#   - Add contract + tests in _schema.yml
git grep -l "ref('event')" dbt_project/ | xargs sed -i "s|ref('event')|ref('fct_meetings')|g"
```

---

## 2. dbt model contract specification

### 2.1 Contracts on every staging model

Every `stg_*` model **must** declare a contract with explicit `data_type` on every column. This is dbt's native [model contract](https://docs.getdbt.com/docs/collaborate/govern/model-contracts) feature: when `contract: enforced: true`, the model is built with the database's `CREATE TABLE (…)` syntax that pins column types, and a build aborts if the SELECT produces columns of incompatible types. This is the mechanism that prevents an upstream Python scraper from silently shifting a column from `VARCHAR(2)` to `VARCHAR(3)` and quietly breaking joins three layers downstream.

### 2.2 Example: contracted `stg_gsa__domains`

A working example lives at:

- [dbt_project/models/staging/stg_gsa__domains.sql](dbt_project/models/staging/stg_gsa__domains.sql) — the model
- [dbt_project/models/staging/_schema_stg_gsa.yml](dbt_project/models/staging/_schema_stg_gsa.yml) — the contract + tests

Pattern:

```yaml
# _schema_stg_gsa.yml
version: 2

models:
  - name: stg_gsa__domains
    description: "GSA .gov domain registry — 1 row per registered .gov domain."
    config:
      contract:
        enforced: true
    columns:
      - name: domain_name
        data_type: varchar(255)
        constraints:
          - type: not_null
          - type: primary_key
        tests: [unique, not_null]
      - name: domain_type
        data_type: varchar(50)
      - name: state
        data_type: varchar(2)
        tests:
          - dbt_utils.not_empty_string
```

When this model builds, dbt issues `CREATE TABLE staging.stg_gsa__domains (domain_name varchar(255), domain_type varchar(50), …) AS SELECT …` and fails the build if the SELECT produces any column with a mismatched type. Upstream Python schema drift is caught at build time, not at downstream query time.

### 2.3 Contract enforcement levels

| Layer | Contract requirement |
|---|---|
| `stg_*` | `enforced: true` — types on every column. PK columns must declare `constraints: [primary_key, not_null]`. |
| `int_*` | `enforced: true` for any int model that fans out (multiple downstream consumers). `enforced: false` is acceptable for single-use intermediates. |
| `fct_*` / `dim_*` | `enforced: true` always. These are the public API surface. Treat them like a versioned schema. |
| `rpt_*` | `enforced: true` if any external dashboard/BI tool consumes them. |

### 2.4 Tests required at minimum

Per model, in `_schema.yml`:
- `unique` and `not_null` on every primary key column
- `relationships` for every foreign key to its parent dim (e.g., `fct_meetings.jurisdiction_id` → `dim_jurisdictions.jurisdiction_id`)
- `accepted_values` for any enum-shaped column (e.g., `jurisdiction_type in ('state', 'county', 'city', 'school_district')`)

Use `dbt_expectations` (already in [packages.yml](dbt_project/packages.yml)) for richer checks: row-count thresholds, regex patterns, distribution checks.

---

## 3. Intermediate entity resolution strategy

The repo today has several intermediate models in the 200–800 line range that try to do everything in one statement (joining ~5 sources, deduplicating, scoring, applying business rules). Two examples worth refactoring as the standard pattern: [int_jurisdictions.sql](dbt_project/models/intermediate/int_jurisdictions.sql) and [int_jurisdiction_websites.sql](dbt_project/models/intermediate/int_jurisdiction_websites.sql).

### 3.1 The decomposition rule

A model is too big when **any** of the following is true:
- >150 lines of SQL,
- more than one `JOIN` per CTE,
- a single CTE doing both deduplication AND business-rule scoring,
- the model name doesn't fit a single `int_<topic>__<step>` (you find yourself wanting to call it `int_jurisdictions_with_websites_deduped_and_scored`).

Split each responsibility into its own intermediate. Name them with the `__<step>` suffix so the chain is readable:

```
int_jurisdictions__base.sql              -- union of all source rosters (census, openstates, wikidata)
int_jurisdictions__deduped.sql           -- collapse to canonical row per natural_key
int_jurisdictions__matched.sql           -- attach external IDs (OCD, Wikidata QID)
int_jurisdictions__with_websites.sql     -- join website discovery picks
int_jurisdictions__scored.sql            -- apply completeness/quality score
dim_jurisdictions.sql                    -- final mart, exposes only stable columns
```

Each file is < 100 lines, has a single CTE doing real work, and is independently testable.

### 3.2 SQL pattern: the four-CTE template

Every intermediate (and staging) model uses the same four-CTE skeleton. This is non-negotiable — it makes models scannable and reviewable:

```sql
{{ config(materialized='table') }}

with

source as (
    -- ONE select from each upstream model. No filtering yet.
    select * from {{ ref('stg_census__counties') }}
),

renamed as (
    -- Column renames, type casts, NULL handling. NO joins, NO business rules.
    select
        geoid                                       as county_geoid,
        upper(coalesce(usps, ''))                   as state_code,
        nullif(trim(name), '')                      as county_name,
        ingestion_date                              as source_ingested_at
    from source
),

filtered as (
    -- Business rules expressed as filters. ONE CTE per rule family.
    select *
    from renamed
    where state_code is not null
      and county_name is not null
),

final as (
    -- Final projection. The columns here MUST match the contract in _schema.yml.
    select
        county_geoid,
        state_code,
        county_name,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from filtered
)

select * from final
```

For models with joins, add named CTEs between `renamed` and `final` — one CTE per logical join. Don't chain three joins in one CTE.

### 3.3 Macro for repeated patterns

Move repeated patterns (state-code normalization, FIPS padding, name-deduping) into `dbt_project/macros/`. Existing macros to lean on; new ones to add:

- `normalize_state_code(col)` — uppercase + trim + validate length 2
- `pad_fips(col, length)` — left-pad with zeros
- `latest_per_natural_key(table, key, ts)` — keep only the latest row per natural_key by `ts`

Each macro gets one corresponding unit test under `dbt_project/tests/`.

---

## 4. API exposure layer

### 4.1 The rule

**The FastAPI application must only read from the `marts` schema.** Reading from `staging`, `intermediate`, `bronze`, or `public` from API code is a bug — it bypasses the contracted surface, ties API behavior to upstream churn, and makes dbt's lineage no longer load-bearing.

Treat dbt's marts as the **semantic backend**. If a column doesn't exist in `fct_*` / `dim_*` / `rpt_*`, it doesn't exist for the API.

### 4.2 Mechanism: a database role with grants scoped to `marts`

Create an `api_reader` role in the database, grant it `SELECT` on `marts.*` only, and have the FastAPI app connect as that role:

```sql
-- dbt_project/migrations/050_api_reader_role.sql (proposed)
create role api_reader login password :api_password;

-- Default deny: revoke everything granted by public to api_reader.
revoke all on database open_navigator from api_reader;
revoke all on schema public, bronze, staging, intermediate from api_reader;

-- Grant only marts.
grant connect on database open_navigator to api_reader;
grant usage on schema marts to api_reader;
grant select on all tables in schema marts to api_reader;
alter default privileges in schema marts grant select on tables to api_reader;
```

In [api/database.py](api/database.py), the connection URL becomes:

```python
# Reads as api_reader. Cannot see bronze/staging/intermediate — Postgres will refuse.
DATABASE_URL = os.getenv("OPEN_NAVIGATOR_API_DATABASE_URL")
```

Day-2 enforcement: if a route accidentally references `bronze.*` or `staging.*`, the query fails with `permission denied for schema bronze` — loud, immediate, and impossible to ignore.

### 4.3 Migration plan for existing API code

A quick audit of the existing [api/routes/](api/routes/) directory:

```bash
grep -rE "FROM (bronze|staging|intermediate|public)\." api/routes/
```

Every match is a violation. For each:

1. Identify the missing mart that should serve the data.
2. Either consume an existing `fct_*` / `dim_*`, or add a new one to `dbt_project/models/marts/`.
3. Update the route to query the mart.
4. Run the route's tests; ensure latency is acceptable (marts are materialized as tables, so they should be faster than the joined-on-read queries common in bronze-direct routes).

### 4.4 dbt as the schema versioning surface

When a mart's shape needs to change in a way that would break consumers, use dbt's [model versions](https://docs.getdbt.com/docs/collaborate/govern/model-versions):

```yaml
# _schema.yml
models:
  - name: fct_meetings
    latest_version: 2
    versions:
      - v: 2
        defined_in: fct_meetings  # current
      - v: 1
        defined_in: fct_meetings_v1
        deprecation_date: 2026-08-01
```

The FastAPI app pins to a specific version (`ref('fct_meetings', v=2)` from intermediate models, or `SELECT * FROM marts.fct_meetings_v2` from raw SQL). Old versions stick around until their deprecation date, giving consumers a window to migrate.

---

## What this PR ships

This PR is **documentation + one worked example**. It does not rename existing models or modify the API — those are follow-ups, one per affected model/route.

- `dbt_project/CONVENTIONS.md` — this document
- `dbt_project/models/staging/stg_gsa__domains.sql` — one example contracted staging model demonstrating the pattern from §2.2
- `dbt_project/models/staging/_schema_stg_gsa.yml` — the contract + tests for that model

## Follow-up PRs

Once this lands, work proceeds one model at a time:

1. **Migration of `models/bronze/` → `models/staging/ai/`** — rename + ref updates in one PR.
2. **Per-mart `fct_` / `dim_` renames** — one PR per mart with downstream ref updates.
3. **`api_reader` role + permission grants + DATABASE_URL switch** — one PR with rollback playbook.
4. **API-route audit and bronze-leak remediation** — one PR per offending route.
5. **Stage 2 raw schema bridge** — when `packages/core-lib` starts writing to `raw_<source>.*`, add `stg_<source>__*` models reading from those raw tables instead of `bronze.*`.
