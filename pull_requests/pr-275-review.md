---
pr: 275
branch: feat/274-odps-data-product
title: "feat(contracts): publish an ODPS data product for the public API's tables"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: maintainer session (self-review; this session can't start a reviewer subagent, so the rubric's coordinator path)
verdict: approve-with-nits
---

# PR Review: feat(contracts): publish an ODPS data product for the public API's tables

## Summary

This PR gathers the 45 ODCS contracts from #270 into one ODPS v1.0.0 data product,
`dbt_project/contracts/products/open-navigator-public-api.odps.yaml`. The product has one output port per contract,
each pointing at its contract by `contractId`.

- **Generated with the contracts:** the same `python -m models.odcs --write` writes it.
- **Checked with the contracts:** `--check`, which CI already runs, now also fails on a stale, missing, extra or
  invalid product file, and on a port whose `contractId` matches no contract file.
- **Schema:** v1.0.0 because Ontos bundles that schema, which was verified against Bitol's copy. The schema is vendored
  with its provenance.

The tests were written first, and every check passes locally and on Python 3.11. The review found no blocking or
should-fix problems, and three nits. The verdict is approve with nits.

## Scope of Change

- Files changed: 8 including this review: 3 Python files (`models/odps.py` new, `models/odcs.py`, `tests/test_odps.py`
  new), 1 docs page, `NOTICE`, the vendored ODPS schema, and the generated product file. About +1,155 / -17 before
  this review, about half of it the vendored schema and the generated product.
- Areas touched: `packages/datamodels`, `dbt_project/contracts` (generated and vendored files only), and
  `web_docs/docs/development`. No dbt model, macro, CI or dependency change.
- Commits: 5649072 feat(contracts): publish an ODPS data product for the public API's tables
- Range reviewed: `a1bc2fb..5649072`

## CI Status

Read on `5649072`:

| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | ✅ success |
| Documentation Build (Docusaurus) | ✅ success |
| Backend Tests (Python) | ✅ success. The step logged "45 ODCS v3.1.0 contracts and their ODPS v1.0.0 data products are current and valid", then `33 passed` (Python 3.11.18) |
| API Types (OpenAPI -> TypeScript) | ✅ success |
| PR conventions (linked issue) | ✅ success |
| Docker Build Test (Full Stack) | skipped (no Docker-relevant change; not required) |

The four required checks are confirmed again on the commit that adds this review before merging.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean. The diff was grepped for keys, tokens, passwords, credentialed URLs, `.env` content and cookies,
  with no hits. The product names no server or host.
- **Fabricated data in a served path:** clean. Nothing under `api/` or `web_app/src/` changes. The product is
  structure only: names, versions, ids and sentences copied from the dbt descriptions.
- **Personal data:** clean.
- **Destructive data changes:** none. No deletions. The 17 removed lines are code and docs lines rewritten in place.

## Strengths

- **One source.** The product comes from the contracts, which come from `schema.yml`. Nothing is hand-maintained
  except the product's name, domain and description (`PRODUCTS` in `models.odps`).
- **Links are checked against what's on disk.** A port must point at a contract file that exists, so a hand-edited or
  outdated product can't name a contract that has gone. The test edits a `contractId` and confirms the reason is
  logged.
- **Fails loudly.** A contract that names an undefined product raises an error naming it, instead of getting a
  half-filled product.
- **The version choice is verified.** Ontos's bundled ODPS v1.0.0 schema was compared with Bitol's, and they differ in
  one description string (`productCreatedTs`).

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

1. **An undefined product surfaces as a traceback.** In `check()` (`odcs.py`), `odps.products_for` raises `ValueError`
   when a contract names an undefined product. The command still exits non-zero, with the product's name in the
   message, but as a traceback rather than the problem list. Verified by `test_a_data_product_with_no_definition_fails`.
   Today every contract names the one defined product.
2. **`domain: civic` is this PR's choice.** Neither the issue nor the standard prescribes a domain value. It is
   written down in the docs page and lives in `PRODUCTS`, so changing it means one edit and a `--write`.
3. **Product definitions live in Python.** `PRODUCTS` is a Python dict, not a YAML file beside the product. That is
   fine for one product; a YAML file would read better if there are ever several.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | #274 has Problem, Done when, Contract and Read first; branch `feat/274-odps-data-product`; `Closes #274` |
| Conventional Commits | ✅ | `feat(contracts)`, with the co-author trailer |
| No fabricated data | ✅ | Scan above |
| New Python in `packages/` | ✅ | `packages/datamodels/models/odps.py`; no new command, it runs through `python -m models.odcs` |
| dbt for transformations | ✅ | No SQL or data transformation in Python |
| Naming, Keys, Calendar years | n/a | No new tables or columns |
| Scope label, match evidence | n/a | No UI change |
| Docs | ✅ | The existing `data-contracts.md`, extended; MDX-safe (the docs build passes) |
| Telemetry and logging | ✅ | loguru for every problem and success |
| Tests | ✅ | Written first; the import failed before the module existed |
| Shared libraries | ✅ | datamodels' tests run (33), the root suite matches `main` apart from the new tests, and the only other importers (two legacy scripts) use `models.meeting_event`, which is unchanged |

## Test Coverage

- **`packages/datamodels/tests/test_odps.py`, 6 tests.** They cover:
  - product shape and port order, fields and descriptions, including the stripped `public.<model> —` lead-in and the
    "e.g." abbreviation;
  - an undefined product failing;
  - the real product validating, with two negative cases (wrong `kind`, missing `status`);
  - `dangling_ports`;
  - the committed product being current;
  - `--check` catching an unmatched `contractId` (with the reason logged), a stale file, a missing file and an extra
    file, and `--write` removing the extra file.
- **Run locally:**
  - **Package tests:** 33 pass, on Python 3.13 and 3.11.
  - **`python -m models.odcs --check`:** current and valid, on both.
  - **Root suite:** 862 passed. The same 56 failures and 43 collection errors as on `main`, from modules and network
    this environment lacks.
  - **ruff:** clean, with this environment's rules and with `--isolated` defaults.
  - **Docs:** `npm run build` succeeds, and the new section's anchor is generated.
- **Not run:** nothing dbt-related changed, so no `dbt ls`.

## Verdict

**Approve with nits.** Merge when the four required checks are green on the latest commit.
