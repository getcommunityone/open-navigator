---
pr: 277
branch: fix/276-contract-refs-release-schemas
title: "fix(contracts): foreign keys resolve and schemas are the releases Ontos reads"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: coordinator (self-review; this session is itself a subagent and can't start a reviewer subagent, so the rubric's coordinator path)
verdict: approve-with-nits
---

# PR Review: fix(contracts): foreign keys resolve and schemas are the releases Ontos reads

## Summary

This PR fixes the two defects #276 describes in the contracts from #272 and #275.

- **Schemas:** the vendored ODCS v3.1.0 and ODPS v1.0.0 JSON Schemas are now Bitol's release-tag copies, which Ontos
  bundles byte for byte, instead of `main`-branch copies. `NOTICE` records each file's tag URL and SHA-256, and a test
  holds the files to it.
- **Foreign keys:** every foreign key is now an ODCS fully qualified reference to a column's `id` in the parent's
  contract file, and every schema object and property has an `id`. A key whose parent has no contract holding the
  column is left out and listed: in `build_contracts().left_out_keys`, in `--write`'s log, in the docs page, and on
  #271.
- **Counts:** of 38 keys, 25 are kept and 13 left out, matching an independent inventory of the old contracts.
- **ODPS:** no contract `id` or `version` changes, so the product file is byte-identical.

The tests were written first, and the new ones were shown to fail on a broken reference, on shorthand and on `main`'s
schema copy. All checks pass. Verdict: approve with nits, none of which blocks.

## Scope of Change

- Files changed: 52 in the fix commit (+1,719 / -753). Excluding the 45 regenerated contracts and the two vendored
  schemas, 5 files (+463 / -48): `models/odcs.py`, `tests/test_odcs.py`, `tests/test_odps.py`, `_schema/NOTICE`,
  and `data-contracts.md`.
- Areas touched: `packages` (datamodels), `dbt_project/contracts` (generated and vendored files only), `web_docs`.
- Commits:
  - 3ba9b2a fix(contracts): foreign keys resolve and schemas are the releases Ontos reads
  - 9be84e4 chore(merge): bring main (#273) into fix/276-contract-refs-release-schemas
- Range reviewed: `4aea386..3ba9b2a`. 9be84e4 only merges `main`'s #273, which touches none of these files; `--check`
  and the package's tests pass after it.

## CI Status

Read on `9be84e4`:

| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | ✅ success |
| Documentation Build (Docusaurus) | ✅ success |
| Backend Tests (Python) | ✅ success. The step logged "45 ODCS v3.1.0 contracts and their ODPS v1.0.0 data products are current and valid" (against the release-tag schemas), then `38 passed` (Python 3.11.18) |
| API Types (OpenAPI -> TypeScript) | ✅ success |
| PR conventions (linked issue) | ✅ success |
| Docker Build Test (Full Stack) | skipped (no Docker-relevant change; not required) |

Before merging, the four required checks are confirmed again on the commit that adds this review.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean. The diff was grepped for keys, tokens, passwords, credentialed URLs, `.env` content, cookies and
  e-mail addresses, with no hits.
- **Fabricated data in a served path:** clean. Nothing under `api/` or `web_app/src/` changes. The contracts hold
  structure only: ids, names and references.
- **Personal data:** clean.
- **Destructive data changes:** none. No files are deleted, and no warehouse table changes. The 753 deleted lines are
  the old `- name:` list items, each now `- id:` plus `name:`, the old shorthand references, and the 13 left-out keys.

## Strengths

- **References resolve by construction.** `build_contracts` writes a key only when the target column is a property
  of a contract in the same build, after projections. So a key into an unserved relation, one served without a
  contract, or a column the public projection drops is never written. A composite key whose `from` column the
  child's projection drops is also left out (verified by a trace with a temporary dbt project).
- **An independent check of the committed files.** The resolve test has its own resolver: it parses the reference,
  opens the target file beside the referencing one and finds the property by `id`. So a regression in
  `_reference`/`_target` can't hide behind the same code. It also asserts that at least one cross-contract reference
  exists, so it can't pass on an empty set.
- **Provenance verified, not assumed.** Both tag copies were downloaded and hashed, and they match the SHA-256s #276
  gives. Ontos's bundled copies are byte-identical to them. The diff against the old `main` copies is the five ODCS
  changes #276 lists, plus one ODPS description.
- **Nothing is silently lost.** The 13 keys are listed in three places: the log, the docs table (with a test) and
  #271. The docs separate the 9 that #271 brings back from the 4 whose parents aren't served at all.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

1. **The docs test checks one direction only.** `test_left_out_foreign_keys_are_documented` (`tests/test_odcs.py`)
   fails when a left-out key isn't in the page, but not when the page lists a key that has come back. Once #271 gives
   `event_meeting` and `event_decision` contracts, their 9 rows would go stale without a failing test. This mirrors
   `test_left_out_relations_are_documented`, and the #271 comment asks for the cleanup. A two-way comparison of the
   table with `left_out_keys` would close it.
2. **The `Built` docstring omits the composite form.** It describes `left_out_keys` entries as
   `<model>.<column> -> <parent>.<column>`, but `_drop_unresolved` writes a composite key as
   `<model>.(a, b) -> <parent>.(x, y)` (its `side()` helper). No composite key is left out today; the test fixture
   shows the form.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | #276 has Problem, Done when, Contract and Read first, label `bug`; branch `fix/276-contract-refs-release-schemas`; `Closes #276` |
| Conventional Commits | ✅ | `fix(contracts)` and `chore(merge)`, each with the co-author trailer |
| No fabricated data | ✅ | Scan above |
| New Python in `packages/` | ✅ | `packages/datamodels/models/odcs.py` only; no new command |
| dbt for transformations | ✅ | No SQL or data transformation in Python |
| Naming, Keys, Calendar years | n/a | No tables or columns change; the contracts describe the existing dbt keys |
| Scope label, match evidence | n/a | No UI change |
| Docs | ✅ | The existing `data-contracts.md`, extended; the docs build passes and generates the new anchor |
| Telemetry and logging | ✅ | loguru, with a warning that lists the left-out keys |
| Tests | ✅ | Written first; 11 failed before the fix, each for the expected reason |
| Shared libraries | ✅ | datamodels' tests ran before (33) and after (38). The root suite gives 867 passed against `main`'s 862, with an identical list of 56 failures and 43 collection errors. `build_contracts`' callers are all in this package, and all are updated |

## Test Coverage

- **New tests:**
  - a same-contract reference has no file part;
  - keys left out: a parent with no contract, a column the parent's projection drops, and a composite key into an
    unserved relation, with dbt's `dbtTestSeverity` kept on the resolved key and every written reference resolving;
  - every reference in the committed contracts resolves, and every object has an `id` equal to its name;
  - every left-out key is documented;
  - the `NOTICE` states each vendored file's SHA-256 and its release-tag source.
- **Changed tests:** the existing assertions now expect fully qualified references and `id`s.
- **Shown not to be vacuous.** Each change below made the named test fail; the files were restored afterwards:
  - pointing `bills`' key at a missing column, and writing it back as shorthand (the resolve test);
  - putting `main`'s ODCS schema back (the NOTICE test).
- **Not covered by a committed test:**
  - a composite key whose `from` column the child's projection drops. Verified by a trace: it is left out and
    listed.
  - a key to a column that the parent's projection redacts. It still resolves, since a redacted column stays a
    property marked `redactedInPublic`. No real key targets a redacted column.
- **Run locally:**
  - **Package tests:** 38 passed on Python 3.13 and 3.11.
  - **`python -m models.odcs --check`:** passes, before and after merging `main`.
  - **ruff:** `ruff check`, `ruff check --isolated` and `ruff format --check` are clean.
  - **Root `pytest`** (`--continue-on-collection-errors`): see the compliance table.
  - **Docs:** `npm ci && npm run build` succeeds.
- **Not run:** `dbt ls`, because no dbt model changed.

## Verdict

**Approve with nits.** Merge when the four required checks are green on the latest commit. The nits can wait for #271.
