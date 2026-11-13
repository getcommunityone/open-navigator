---
title: Data contracts for the public API
sidebar_label: Data contracts
---

# Data contracts for the public API

Decision record for [#270](https://github.com/getcommunityone/open-navigator/issues/270): every table the public API
serves gets a data contract, generated from dbt and checked in CI. The contracts are gathered into one data product by
[#274](https://github.com/getcommunityone/open-navigator/issues/274) (see [The data product](#the-data-product-odps)).

A data contract is a file that says what a table holds and what a reader can rely on: its columns and their types, its
keys, and the data-quality rules it passes. Ours follow the
[Open Data Contract Standard](https://github.com/bitol-io/open-data-contract-standard) (ODCS), so tools other than ours
can read them.

## What we chose

| Choice | Why |
|---|---|
| **ODCS v3.1.0** (`apiVersion: v3.1.0`) | An open standard from Bitol (a Linux Foundation AI & Data project, Apache-2.0) with an official JSON Schema. [Ontos](https://github.com/databrickslabs/ontos), a catalog we may use later, reads v3.1.0. Version 3.2.0 exists; moving to it is a later upgrade: vendor its schema, change `API_VERSION` in `models.odcs`, regenerate. |
| **Generated from dbt, never written by hand** | dbt's `schema.yml` files stay the one place a table's structure is declared. A contract can't drift from its model, because CI regenerates it and compares. |
| **One file per table, in `dbt_project/contracts/`** | Beside the dbt project the contracts come from, so a `schema.yml` change and its contract land in the same diff. dbt reads only its own paths (`models/`, `macros/` and so on), so the folder doesn't affect dbt. |
| **The official schema vendored** | `dbt_project/contracts/_schema/odcs-json-schema-v3.1.0.json`, unchanged, with a `NOTICE` giving its source, licence and SHA-256, so validation works offline in CI. |
| **Code in `packages/datamodels`** | `models.odcs` in the `communityone-datamodels` package, run with `python -m models.odcs`: new Python goes in `packages/`, never `scripts/`. |
| **ODPS v1.0.0 for the data product** (`apiVersion: v1.0.0`) | The Open Data Product Standard is Bitol's companion to ODCS (Apache-2.0). Ontos bundles the ODPS v1.0.0 JSON Schema, identical to Bitol's apart from one description string, so we use v1.0.0, not v1.1.0. The official schema is vendored beside the ODCS one, with the same `NOTICE` details. |

## Which tables

The public API reads only what `publish_public_serving` (`dbt_project/macros/publish_public_serving.sql`) puts in
`public`. A served relation gets a contract when its `schema.yml` enforces a dbt contract (`contract: enforced: true`)
and gives every column a type. When this was written, 45 of the 55 served relations did; their contracts are in
`dbt_project/contracts/`.

### Served without a contract

These 10 have nothing typed to generate from.
[#271](https://github.com/getcommunityone/open-navigator/issues/271) gives them typed, enforced dbt contracts, or takes
them out of `served`. A test fails when a served relation has no contract and isn't listed here.

| Relation | Why it has no contract |
|---|---|
| `event_meeting` | declared in `_schema_event_extractions.yml` with no column types and no enforced contract |
| `event_decision` | the same; it is also partitioned with a composite primary key |
| `event_financial_item` | declared in `_schema_event_extractions.yml` with no column types and no enforced contract |
| `event_bill` | the same |
| `event_topic` | the same |
| `event_place_geocoded` | declared in `_schema_event_place_geocoded.yml` with no column types and no enforced contract |
| `jurisdiction_state_aggregate` | declared in `_schema_jurisdiction_state_aggregate.yml` with no column types and no enforced contract |
| `meeting_document` | not a dbt model: a Python loader (`packages/llm/src/llm/gemini/meeting_document_enrichment.py`) writes it |
| `civic_jurisdiction` | no dbt model in `dbt_project/models` |
| `jurisdiction_mapping_analysis` | a dbt model with no `schema.yml` entry |

## What a contract holds

- **The table:** `id` `open-navigator-public-<model>`, `version` `1.0.0`, `status` `active`, `dataProduct`
  `open-navigator-public-api`, and one schema object with `physicalName` `public.<model>`, the model's description, and
  its grain (its "one row per" sentence) as `dataGranularityDescription`.
- **Columns:** each column's Postgres type as dbt declares it (`physicalType`) and its ODCS type (`logicalType`:
  `string`, `integer`, `number`, `boolean`, `date`, `timestamp`, `time`, `object` for `json` and `jsonb`, `array` for
  types such as `text[]`).
- **Keys:** the primary key (`primaryKey`, with `primaryKeyPosition` for a composite key). Foreign keys from dbt
  constraints and `relationships` tests become `relationships` with `to: <model>.<column>`, using ODCS shorthand and the
  dbt model name. A target that only a warn-level test asserts carries `dbtTestSeverity: warn`, because nothing
  guarantees it.
- **Guarantees:** `required` and `unique` appear only when something enforces them. That is either a Postgres
  constraint or a dbt test that fails the build on every row. Every primary-key column is `required`, but only a
  one-column key makes its column `unique`: in a composite key, only the combination is unique. A test with
  `severity: warn` or a `where:` filter reports problems but guarantees nothing.
- **Quality rules**, each with its dbt test's severity: `error`, or `warning` for `severity: warn`.
  - `not_null`, `unique` and `accepted_values` become ODCS library rules (`nullValues`, `duplicateValues`, and
    `invalidValues` with the accepted values), each with `mustBe: 0`.
  - Range tests (`dbt_utils.accepted_range`, `dbt_expectations.expect_column_values_to_be_between`), filtered tests and
    Postgres CHECK constraints become text rules.
- **Redaction:** columns that `publish_public_serving` redacts in `public` (the officials' `email` and `phone`, published
  as `null::text`) are marked `redactedInPublic: true` and carry no quality rules. Columns its projection leaves out
  don't appear.

A contract never holds rows, example values, row counts, server or host names, credentials or personal data. The ODCS
sections for servers, service levels, teams and pricing are left out on purpose: they describe hosting and people, not
structure.

### Which build the contracts describe

`publish_public_serving` has two modes. The contracts describe the default, view mode, where each relation is a view over
`gold`. That is also what `sync_public_to_neon` copies to the hosted database, for the relations on its allow-list.
With the `public_serving_launch_scope` var on, rows may be limited to the launch jurisdictions; the columns stay the
same.

The macro's materialize mode (`--vars '{public_serving_mode: materialize}'`) builds standalone tables, slimmed to the
Neon serving scope. Each affected contract says so in `description.limitations`:

- `event`, `grant`, `mdm_organization`, `mdm_organization_nonprofit` and `mdm_bridge_org_jurisdiction` keep their
  columns but fewer rows.
- `bills` and `event_documents` keep fewer rows, and drop or null some columns.

## The data product (ODPS)

Every contract names the data product it belongs to: today all of them say `dataProduct: open-navigator-public-api`.
Each product named there gets a file, `dbt_project/contracts/products/<product>.odps.yaml`, generated from the
contracts by the same command. So there is one file today, `products/open-navigator-public-api.odps.yaml`.

- **The product:** `apiVersion: v1.0.0`, `kind: DataProduct`, `id` (the contracts' `dataProduct`), `name`,
  `version: 1.0.0`, `status: active`, `domain: civic`, a `description` with `purpose`, `usage` and `limitations`, and
  `tags`. The name, domain and description come from `PRODUCTS` in `models.odps`.
- **One output port per contract:** `name` (the table), `version` (the contract's version), `contractId` (exactly the
  contract's `id`), `type: table`, and `description` (the first sentence of the table's dbt description).
- **No input ports:** the tables' sources have no contracts to point at.

`--check` fails when a product file is stale, missing, extra or not valid ODPS v1.0.0, or when one of its ports names a
`contractId` that matches no contract file. `packages/datamodels/tests/test_odps.py` covers it.

## Regenerate and check

Regenerate after you change a served model's `schema.yml`, or the macro's `served` list or `projections`:

```bash
pip install -e packages/datamodels   # once (or set PYTHONPATH=packages/datamodels)
python -m models.odcs --write        # regenerate dbt_project/contracts/ and its products/
python -m models.odcs --check        # what CI runs
```

Commit the contracts and the product file with the change. The CI job **Backend Tests (Python)** runs `--check`. It
fails, naming each problem, when a contract is:

- stale;
- missing;
- extra (its relation is no longer served with an enforced contract);
- not valid ODCS v3.1.0.

`packages/datamodels/tests/test_odcs.py` covers the mapping.

Every contract's `version` is `1.0.0`. While the contracts live only in this repository, git history is their change
record. A version policy, such as bumping the major version on a breaking column change, comes when they are published
to a catalog.

## Later: Ontos and DQX

Both are Databricks Labs projects, which Databricks provides for exploration without formal support. Open Navigator
runs on Postgres, so neither is in use, and nothing here depends on them.

- **[Ontos](https://github.com/databrickslabs/ontos)** ("a business catalog for Unity Catalog") reads ODCS v3.1.0 and
  bundles the ODPS v1.0.0 schema. The contracts and the product file could be imported unchanged, to catalog the public
  API's tables as one data product (`open-navigator-public-api`).
- **[DQX](https://github.com/databrickslabs/dqx)** validates the data quality of PySpark DataFrames and tables. If these
  tables were ever processed on Databricks, DQX checks could be generated from the contracts' quality rules (not-null,
  uniqueness, accepted-value and range checks), with each rule's `severity` as the check's criticality.
