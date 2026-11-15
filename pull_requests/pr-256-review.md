---
pr: 256
branch: feat/237-core-1-1-ordinance-schema
title: "feat(dbt): ordinance and amendment schema with CHECK constraints (CORE-1.1.1)"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: maintainer session (self-review, verified by a build on a throwaway Postgres 16)
verdict: approve-with-nits
---

# PR Review: feat(dbt): ordinance and amendment schema with CHECK constraints (CORE-1.1.1)

| Attribute | Value |
|---|---|
| Epic | [CORE · Meetings, Legislation and Officials](https://github.com/getcommunityone/open-navigator/issues/235) |
| User story | [CORE-1.1 · Ordinance text and status](https://github.com/getcommunityone/open-navigator/issues/237) |
| Task | CORE-1.1.1 · Ordinance and amendment schema with CHECK constraints |

## Summary

This PR adds the ordinance schema for CORE-1.1: two marts with enforced contracts (`ordinances`,
`ordinance_amendments`) and a CHECK constraint that holds `status` to the story's five-word vocabulary or null.
Every row needs an `http(s)` source link. A status map seed never guesses, and the staging models build empty until
the ingest creates the bronze tables. It was built and tested for real against a throwaway Postgres 16: the
constraints exist and reject bad rows, and the filtering and de-duplication behave. It touches nothing that exists
except one source block in `_staging.yml`. The verdict is approve, with two nits.

## Scope of Change

- Files changed: 10 (+~500): 2 mart SQL files and their schema, 2 staging SQL files and their schema, 1 seed, the
  `_staging.yml` source block, 1 test file, 1 docs page, and this review
- Areas touched: `dbt_project` (new models, a seed, a source block), `tests`, `web_docs/docs/development`
- Commits: b90171f feat(dbt): ordinance and amendment schema with CHECK constraints (CORE-1.1.1)

## CI Status

Checked green on the head before merging (Frontend Build, Documentation Build, Backend Tests, API Types). CI doesn't
run dbt or the root pytest suite, so both were run by hand (below).

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data in a served path:** clean. The marts are empty until the ingest lands, and an unmapped status is
  null with the raw label kept. The test rows lived only in the throwaway database, which is deleted.
- **Personal data:** clean.
- **Destructive data changes:** none. New tables only. Nothing existing is altered or dropped.

## Strengths

- Postgres itself enforces the vocabulary, the keys and the source link. A direct insert of "adopted", or of an
  `ftp://` link, is rejected.
- The guard calls `source()` and `ref()` before the `if`, so dbt records the dependencies at parse time. The parsed
  manifest confirms it.
- Dropped rows are counted, not hidden. The warn tests gave exactly the 3 planted bad rows.
- The "adopted / passed" ambiguity is written down with its reason (`ordinance-schema.md`) and deferred to the
  ingest, where each council's real labels can decide it.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

1. **Constraint names carry `__dbt_tmp`.** Postgres names the CHECKs after dbt's temp table
   (`ordinances__dbt_tmp_status_check1`). That's cosmetic, but the error a loader sees would read better with names
   like `ordinances_status_check`. dbt allows a `name:` on each constraint.
2. **Bronze dates are cast directly.** `cast(... as date)` fails the whole view if the loader writes a non-ISO date
   string. The source description asks for ISO dates. CORE-1.1.2's loader should write `date` values, or staging
   could switch to a safe parse.

## Repo-Rule Compliance

| Rule | Status |
|---|---|
| Issue first, Contract as a dated line (AGENTS.md) | ✅ #237, plus a dated correction for `gold` vs `public` |
| Epic and User story links (Attributes) | ✅ in the PR and in this review |
| Branch and PR link | ✅ `feat/237-core-1-1-ordinance-schema`, `Refs #237` (one task of the story) |
| Test first | ✅ `tests/test_ordinance_schema.py` failed (7) before the models existed |
| Transformations in dbt, not Python (CLAUDE.md) | ✅ |
| Public tables declare PK and FKs | ✅ enforced contracts; the marts reach `public` via `publish_public_serving` |
| No `dim_` / `fact_` names | ✅ `ordinances`, `ordinance_amendments` |
| No Fabricated Data | ✅ |
| Decisions written down | ✅ `web_docs/docs/development/ordinance-schema.md` |
| Conventional Commits | ✅ |

## Test Coverage

- `tests/test_ordinance_schema.py` has 7 tests: the contracts are enforced and typed; ordinances have their PK, FK
  and not-nulls; the status CHECK holds exactly the vocabulary plus null; amendments have their PK and FK; the seed
  never guesses and reaches every status; the guard comes before the source read; the bronze sources are declared.
- By hand, against Postgres 16:
  - `dbt seed`, then `dbt run` without bronze: 4 models built, both marts empty.
  - With test rows: 3 ordinances and 1 amendment, all as expected.
  - `dbt test`: 7 passes and 3 warnings.
  - Direct inserts: both CHECK constraints reject.

## Verdict

**Approve with nits.** Merge when the four required checks are green.
