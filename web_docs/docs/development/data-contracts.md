---
title: Data contracts for the public API
sidebar_label: Data contracts
---

# Data contracts for the public API

Decision record for [#270](https://github.com/getcommunityone/open-navigator/issues/270): every table the public API
serves gets a data contract, generated from dbt and checked in CI. The contracts are gathered into one data product by
[#274](https://github.com/getcommunityone/open-navigator/issues/274) (see [The data product](#the-data-product-odps)).
[#276](https://github.com/getcommunityone/open-navigator/issues/276) made their foreign keys resolve and vendored the
schemas from their release tags.

A data contract is a file that says what a table holds and what a reader can rely on: its columns and their types, its
keys, and the data-quality rules it passes. Ours follow the
[Open Data Contract Standard](https://github.com/bitol-io/open-data-contract-standard) (ODCS), so tools other than ours
can read them.

## What we chose

| Choice | Why |
|---|---|
| **ODCS v3.1.0** (`apiVersion: v3.1.0`) | An open standard from Bitol (a Linux Foundation AI & Data project, Apache-2.0) with an official JSON Schema. [Ontos](https://github.com/databrickslabs/ontos), a catalog we may use later, reads v3.1.0. Version 3.2.0 exists; moving to it is a later upgrade: vendor the schema at its release tag, update the `NOTICE`, change `API_VERSION` in `models.odcs`, regenerate. |
| **Generated from dbt, never written by hand** | dbt's `schema.yml` files stay the one place a table's structure is declared. A contract can't drift from its model, because CI regenerates it and compares. |
| **One file per table, in `dbt_project/contracts/`** | Beside the dbt project the contracts come from, so a `schema.yml` change and its contract land in the same diff. dbt reads only its own paths (`models/`, `macros/` and so on), so the folder doesn't affect dbt. |
| **The official schemas vendored from their release tags** | `dbt_project/contracts/_schema/odcs-json-schema-v3.1.0.json` is the copy at Bitol's `v3.1.0` tag, unchanged, so validation works offline in CI. It is byte for byte the copy Ontos bundles. The copy on Bitol's `main` branch differs from it in five places, the `id` and reference patterns among them, and can change again under the same file name. The `NOTICE` gives each file's release-tag URL, licence and SHA-256, and a test fails when a file's SHA-256 isn't the one stated or its source isn't the release tag in its name. |
| **Code in `packages/datamodels`** | `models.odcs` in the `communityone-datamodels` package, run with `python -m models.odcs`: new Python goes in `packages/`, never `scripts/`. |
| **ODPS v1.0.0 for the data product** (`apiVersion: v1.0.0`) | The Open Data Product Standard is Bitol's companion to ODCS (Apache-2.0). Ontos bundles the ODPS v1.0.0 JSON Schema, the copy at Bitol's `v1.0.0` tag, so we use v1.0.0, not v1.1.0. That copy is vendored beside the ODCS one, with the same `NOTICE` details. |
| **Fully qualified references for foreign keys** | ODCS v3.1.0's [references page](https://github.com/bitol-io/open-data-contract-standard/blob/v3.1.0/docs/references.md) leaves out the file part only for a reference within the same contract, and recommends fully qualified references across contracts. Each of our contracts holds one table, so the shorthand `<model>.<column>` would name a table that isn't in the file. A foreign key whose parent has no contract holding the column is left out, because there is nothing to point at (see [Foreign keys left out](#foreign-keys-left-out)). |

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

### Foreign keys left out

A foreign key points at a column in its parent's contract, so these 13 are left out of their contracts while the parent
has none. Each one comes back by itself once the parent's contract holds the column: the generator writes every
foreign key it can resolve. `python -m models.odcs --write` lists the ones it leaves out, and a test fails when one is
left out but isn't listed here.

| Column | Points at | Comes back when |
|---|---|---|
| `event_meeting_document.event_meeting_id` | `event_meeting.event_meeting_id` | `event_meeting` gets a contract ([#271](https://github.com/getcommunityone/open-navigator/issues/271)) |
| `mdm_bridge_event_analysis.event_meeting_id` | `event_meeting.event_meeting_id` | the same |
| `meeting_browse.event_meeting_id` | `event_meeting.event_meeting_id` | the same |
| `meeting_question_link.event_meeting_id` | `event_meeting.event_meeting_id` | the same |
| `meeting_topic_link.event_meeting_id` | `event_meeting.event_meeting_id` | the same |
| `decision_speakers.event_decision_id` | `event_decision.event_decision_id` | `event_decision` gets a contract (#271) |
| `event_decision_place.event_decision_id` | `event_decision.event_decision_id` | the same |
| `item_interestingness.event_decision_id` | `event_decision.event_decision_id` | the same |
| `question_instance.source_id` | `event_decision.event_decision_id` | the same |
| `event_decision_place.place_id` | `event_place.place_id` | `event_place`, a dbt model that isn't served, is published in `public` with a contract |
| `canonical_argument.frame_id` | `policy_frame.frame_id` | `policy_frame`, a dbt seed that isn't served, is published with a contract |
| `policy_question.topic_code` | `cap_topic.code` | the same, for the seed `cap_topic` |
| `topic_money_and_talk.canonical_theme` | `policy_theme_cofog.primary_theme` | the same, for the seed `policy_theme_cofog` |

## What a contract holds

- **The table:** `id` `open-navigator-public-<model>`, `version` `1.0.0`, `status` `active`, `dataProduct`
  `open-navigator-public-api`, and one schema object with `physicalName` `public.<model>`, the model's description, and
  its grain (its "one row per" sentence) as `dataGranularityDescription`.
- **Columns:** each column's Postgres type as dbt declares it (`physicalType`) and its ODCS type (`logicalType`:
  `string`, `integer`, `number`, `boolean`, `date`, `timestamp`, `time`, `object` for `json` and `jsonb`, `array` for
  types such as `text[]`).
- **Ids:** the schema object's `id` is the model's name, and each property's `id` is its column's name. References
  point at these ids.
- **Keys:** the primary key (`primaryKey`, with `primaryKeyPosition` for a composite key). Foreign keys from dbt
  constraints and `relationships` tests become `relationships`. Each `to` is a fully qualified reference into the
  parent's contract, relative to the contract file, such as
  `to: jurisdictions.odcs.yaml#/schema/jurisdictions/properties/jurisdiction_id`. Within the same contract the file
  part is left out: `tag`'s `parent_tag_id` has `to: schema/tag/properties/tag_id`. A composite key is a schema-level
  relationship with lists for `from` and `to`. A target that only a warn-level test asserts carries
  `dbtTestSeverity: warn` in the relationship's `customProperties`, because nothing guarantees it. A foreign key whose
  parent has no contract holding the column is left out ([Foreign keys left out](#foreign-keys-left-out)).
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

`packages/datamodels/tests/test_odcs.py` covers the mapping. It also resolves every foreign key in the committed
contracts to a property in a committed contract file, and checks each vendored schema against the SHA-256 and release
tag in `_schema/NOTICE`.

Every contract's `version` is `1.0.0`. While the contracts live only in this repository, git history is their change
record. A version policy, such as bumping the major version on a breaking column change, comes when they are published
to a catalog.

## Later: Ontos and DQX

Both are Databricks Labs projects, which Databricks provides for exploration without formal support. Open Navigator
runs on Postgres, so neither is in use, and nothing here depends on them.

- **[Ontos](https://github.com/databrickslabs/ontos)** ("a business catalog for Unity Catalog") reads ODCS v3.1.0 and
  bundles the ODCS v3.1.0 and ODPS v1.0.0 schemas: the release-tag copies vendored here, byte for byte. The contracts
  and the product file could be imported unchanged, to catalog the public API's tables as one data product
  (`open-navigator-public-api`).
- **[DQX](https://github.com/databrickslabs/dqx)** validates the data quality of PySpark DataFrames and tables. If these
  tables were ever processed on Databricks, DQX checks could be generated from the contracts' quality rules (not-null,
  uniqueness, accepted-value and range checks), with each rule's `severity` as the check's criticality.
