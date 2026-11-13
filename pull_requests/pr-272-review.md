---
pr: 272
branch: feat/270-odcs-data-contracts
title: "feat(dbt): generate ODCS v3.1.0 data contracts for the public API's tables"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: maintainer session (self-review; this session can't start a reviewer subagent, so the rubric's coordinator path)
verdict: approve-with-nits
---

# PR Review: feat(dbt): generate ODCS v3.1.0 data contracts for the public API's tables

## Summary

This PR gives each relation the public API serves an Open Data Contract (ODCS v3.1.0), when its `schema.yml` enforces
a dbt contract: 45 of the 55 relations in `publish_public_serving`.

- **Generated, not written:** `python -m models.odcs --write` builds the contracts from dbt's own `schema.yml` and the
  macro.
- **Checked in CI:** `--check` fails when a contract is stale, missing, extra or not valid against the vendored
  official schema. The package's tests also run there.
- **Contents:** keys, foreign keys and quality rules, guarantees only where something enforces them, redacted columns
  marked.

The review found two real problems, both fixed on the branch with a test:

- composite-key columns were marked unique (`894ae5f`);
- the test that guards the docs page's list didn't run in CI (`2feffc6`).

Three nits remain. Each was verified not to affect today's output, and each fails loudly if it ever does. The verdict
is approve with nits.

## Scope of Change

- Files changed: 56 including this review. Hand-written: 7 files, about +1,100 / -3, plus this review. Generated and
  vendored: 45 contracts, the ODCS JSON Schema and its `NOTICE`, and one `uv.lock` entry.
- Areas touched: `packages/datamodels` (new module and tests), `dbt_project/contracts` (generated; no dbt model or
  macro changed), `ci`, `web_docs/docs/development`, and root config (`pytest.ini`, `requirements.txt`, `uv.lock`).
- Commits:
  - 5f0ceff feat(dbt): generate ODCS v3.1.0 data contracts for the public API's tables
  - 2feffc6 ci(dbt): run the data-contract tests in Backend Tests
  - 894ae5f fix(dbt): a composite-key column is not unique on its own
- Range reviewed: `55db346..894ae5f`

## CI Status

Read on `894ae5f`:

| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | ✅ success |
| Documentation Build (Docusaurus) | ✅ success |
| Backend Tests (Python) | ✅ success. The new step logged "45 ODCS v3.1.0 contracts are current and valid", then `27 passed` (Python 3.11.18) |
| API Types (OpenAPI -> TypeScript) | ✅ success |
| PR conventions (linked issue) | ✅ success |
| Docker Build Test (Full Stack) | not required; it runs because `requirements.txt` changed, and it is checked before merging |

The four required checks are confirmed again on the commit that adds this review before merging.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean. The diff was grepped for keys, tokens, passwords, credentialed URLs, `.env` content and cookies.
  The two hits are harmless: the word "password" in the ODCS JSON Schema's list of example string formats, and
  "token" in a column description. The contracts name no server, host or database: ODCS `servers` is left out on
  purpose.
- **Fabricated data in a served path:** clean. Nothing under `api/` or `web_app/src/` changes. The contracts are
  structure only. The only numbers in them are bounds copied from dbt tests and figures already in the dbt
  descriptions.
- **Personal data:** clean. The contracts name columns, never values. The officials' `email` and `phone` columns are
  marked `redactedInPublic`, matching the macro's projection.
- **Destructive data changes:** none. No deletions, no warehouse changes, nothing under `data/cache/`. The largest new
  file is the 88 KB vendored schema.

## Strengths

- **One place to declare structure.** The contracts are generated from `schema.yml`, and CI's `--check` stops them
  drifting from it.
- **Guarantees are honest:**
  - `required` and `unique` appear only when a Postgres constraint or an error-level, unfiltered dbt test enforces
    them;
  - warn-level and filtered tests become quality rules with their severity, not guarantees;
  - a foreign key that only a warn-level test asserts is marked `dbtTestSeverity: warn`.
- **The two builds of the serving layer are told apart.** The contracts describe the default view mode, which the
  hosted copy mirrors. The seven relations that the materialize mode slims say so: five keep their columns, while
  `bills` and `event_documents` lose some.
- **Offline validation, with provenance.** The official schema is vendored unchanged, with its source, licence and
  SHA-256.
- **Left-out relations are tracked.** The 10 served relations without a contract are listed with reasons and a
  follow-up (#271). A test fails if the list falls behind.

## Findings

### 🔴 Blocking (Critical)

1. **Fixed in `894ae5f`: composite-key columns were marked `unique: true`.**
   - **Where:** `packages/datamodels/models/odcs.py`, `_property`. `name in keys` made every primary-key column
     unique.
   - **Why it's wrong:** in a composite key only the combination is unique.
   - **Verified** in the generated output: `cpi_annual.year`, one half of the key `(series_id, year)`, carried
     `unique: true`. So did the key columns of five more contracts: `browse_directory_summary`,
     `browse_entity_state_transcript_count`, `browse_transcript_count`, `opportunity_atlas_mobility` and
     `opportunity_atlas_mobility_national`.
   - **Fix:** only a one-column key makes its column unique; every key column stays required. A new assertion in
     `test_composite_keys` failed before the fix and passes after. Regenerating removed 16 `unique: true` lines from
     those 6 files and changed nothing else. The docs page now says this.

### 🟡 Should fix (Important, non-blocking)

1. **Fixed in `2feffc6`: the docs-listing guard ran only locally.**
   - **The gap:** `test_left_out_relations_are_documented` ran only under a local `pytest`, and CI runs no pytest. So
     the page's list of relations without a contract could fall behind the served list unnoticed.
   - **Fix:** the Backend Tests step now also runs `pytest packages/datamodels/tests`.
   - **Verified** on Python 3.11 from the repo root: the root `conftest.py` imports `agents`, which needs only pydantic
     and loguru, both in `requirements.txt`; 27 passed.

### 🔵 Nits / suggestions (Minor)

1. **A `source()` relationship target isn't resolved.**
   - **Where:** `_ref` (`odcs.py`) reads `ref('x')` only.
   - **What would happen:** a foreign key or `relationships` test pointing at `source('schema', 'table')` would give a
     target that breaks ODCS's `table.column` pattern.
   - **Verified harmless today:** no served model uses one, and all 45 contracts validate. `--write` refuses to write
     an invalid contract and names it, so this would fail loudly.
2. **A projection with a function call would mis-split.**
   - **Where:** `projections()` splits the projection's select list on commas, so `coalesce(a, b) as c` would split
     wrongly.
   - **Verified harmless today:** both projections are plain columns and `null::text` aliases. A mis-split would
     surface as the warning "the public projection selects columns its schema.yml lacks".
3. **The new dependencies have lower bounds rather than pins.** #270's Contract said "pinned in
   `requirements.txt`", but `PyYAML>=6.0` and `jsonschema>=4.18` are lower bounds. The file mixes both styles, and an
   exact pin can clash with the rest of the tree, whereas these bounds resolved cleanly in CI's install. What `--check`
   compares does depend on PyYAML's output, but its emitter has been stable across 6.0.x. A release that changed it
   would fail `--check` loudly, and `--write` would fix it. The change from "pinned" is recorded as a dated line on
   #270.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | #270 has Problem, Done when, Contract and Read first; branch `feat/270-odcs-data-contracts`; `Closes #270` |
| Follow-ups are issues | ✅ | #271 for the 10 relations without a contract, linked from the PR and the docs page |
| Conventional Commits | ✅ | `feat(dbt)`, `ci(dbt)`, `fix(dbt)`, each with the co-author trailer |
| No fabricated data | ✅ | Scan above |
| New Python in `packages/` | ✅ | `packages/datamodels/models/odcs.py`, run as `python -m models.odcs`; nothing in `scripts/` |
| dbt for transformations | ✅ | No SQL or JSONB logic in Python. The module reads dbt's YAML and the macro's text; it transforms no data |
| Naming | ✅ | No new tables or columns |
| Keys | ✅ | Every contract has its primary key; foreign keys come from dbt constraints and `relationships` tests |
| Calendar years | n/a | |
| Scope label matches filter, match evidence | n/a | No UI change |
| Docs | ✅ | `web_docs/docs/development/data-contracts.md`: kebab-case, frontmatter; MDX-safe (the docs build passes) |
| Telemetry and logging | ✅ | loguru throughout the module |
| Tests | ✅ | Written first and seen failing: collection error, then 7 failures, then the composite-key assertion |
| Shared libraries | ✅ | datamodels' tests run. Its only importers, two legacy `scripts/` files, use `models.meeting_event`, which is unchanged and still imports |

## Test Coverage

- **`packages/datamodels/tests/test_odcs.py`, 27 tests.** They cover:
  - the served list read from the macro, and 14 type mappings;
  - keys, relationships and quality rules on a sample model, and composite keys;
  - redaction, with projection order and dropped columns;
  - test severity and `where:` filters;
  - the grain sentence (an abbreviation like "U.S." and an unbalanced bracket);
  - the materialize-mode notes;
  - every real contract validating against the official schema;
  - the committed contracts being current;
  - `--check` catching stale, missing and extra files;
  - the docs page listing every relation left out.
- **Run locally:**
  - **Package tests:** 27 passed on Python 3.13, and on 3.11 from the repo root.
  - **`python -m models.odcs --check`:** 45 contracts current and valid, on 3.13 and in a fresh 3.11 venv.
  - **Root suite:** 856 passed, against 829 on `main`. The same 56 failures and 43 collection errors occur on both,
    from modules and network this environment lacks.
  - **ruff:** clean, with this environment's rules and with `--isolated` defaults; `ruff format --check` clean.
  - **Docs:** `npm ci && npm run build` succeeds and builds the page.
  - **`uv lock --check`:** passes.
- **Not run:** `dbt ls` and `dbt build`. There is no warehouse here, and no model, macro or `schema.yml` changed.

## Verdict

**Approve with nits.** The blocking and should-fix findings are fixed on the branch. Merge when the four required checks
are green on the latest commit.
