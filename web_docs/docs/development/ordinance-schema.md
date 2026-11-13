---
title: Ordinance schema and status vocabulary
sidebar_label: Ordinance schema
---

# Ordinance schema and status vocabulary

Decision record for CORE-1.1, task CORE-1.1.1:
[ordinance text and status](https://github.com/getcommunityone/open-navigator/issues/237), in the
[CORE epic: meetings, legislation and officials](https://github.com/getcommunityone/open-navigator/issues/235).
Recorded November 13, 2026.

## What we chose

- **Two marts with enforced contracts.**
  - `ordinances` has one row per ordinance per jurisdiction per source platform, with primary key `ordinance_uid`
    and a foreign key to `jurisdictions`.
  - `ordinance_amendments` has one row per amendment, with primary key `amendment_uid` and a foreign key to
    `ordinances`.
  - Both build into `gold`, like every mart. `publish_public_serving` exposes them in `public` once the API serves
    them (task CORE-1.1.3).
- **A fixed status vocabulary, enforced by Postgres.** `status` is `introduced`, `awaiting_signature`, `signed`,
  `vetoed` or `failed`, or null. A CHECK constraint rejects anything else. The source's own label is kept verbatim in
  `status_raw`.
- **Every row is traceable.** `source_url` is required and must be an `http(s)` link: a second CHECK constraint.
  Rows without an identifier or a source link, and rows for an unknown jurisdiction, are left out of the mart.
  Warn-level tests on the staging models count them in every run.
- **The map never guesses.** The `ordinance_status_map` seed maps lowercased source labels to the vocabulary. It holds
  only unambiguous phrases ("signed by mayor", "vetoed", "failed to pass" and the like).
- **Empty until loaded.** The staging models read `bronze.bronze_ordinances` and `bronze.bronze_ordinance_amendments`
  only when those tables exist. Until the ingest (task CORE-1.1.2) creates them, the marts build empty and dbt runs
  keep passing.

## Why

- "Adopted" and "passed" mean final passage in a council–manager city, but "awaiting the mayor's signature" in a
  strong-mayor city. Mapping either one by default would show residents a status the record doesn't support, and the
  No Fabricated Data rule says an unknown is shown as unknown. Null with the raw label beside it is honest and
  checkable. The ingest decides per jurisdiction, from how that council actually publishes.
- Postgres enforces the vocabulary, the keys and the source link, so a loader bug fails loudly at build time instead
  of reaching a page.
- An empty table is a true answer before the data arrives ("no ordinances loaded yet"); stand-in rows would not be.

## How it was checked

dbt can't run in CI here, so the models were built against a throwaway Postgres 16, with dbt-postgres 1.11.

- **Without bronze tables:** both marts built empty.
- **With test rows:**
  - A re-loaded ordinance kept its newest row.
  - "Adopted" stayed null.
  - "  FAILED " mapped to `failed`.
  - The unknown jurisdiction and the row with no source link were left out, and the warn tests counted 3.
- **Direct inserts:** a status of "adopted" and an `ftp://` source link were both rejected by the CHECK constraints.

`tests/test_ordinance_schema.py` pins the contract in the model files.

## When to revisit

- When the ingest (CORE-1.1.2) lands the pilot councils' ordinances. Add their status labels to the seed, deciding
  "adopted" and "passed" per jurisdiction.
- If a source publishes a status the five words can't express.
