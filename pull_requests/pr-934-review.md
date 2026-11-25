---
pr: 934
branch: feat/932-dc-uncontested-same-item
title: "feat(dbt): bring uncontested items into the warehouse and count same-item and consent-item data center comments"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: data-dbt-specialist subagent (read-only) and coordinator
head_sha: 108c86a8
verdict: approve-with-nits
---

# PR Review: feat(dbt): bring uncontested items into the warehouse and count same-item and consent-item data center comments

## Summary

The PR adds `bronze_uncontested_items_from_ai` and `event_uncontested_item`, so the consent and routine items the analyses
record are in the warehouse. 40,795 items are kept from preferred analyses, 11 of them data center decisions. It widens
`int_data_center__public_comment` with two evidence-based bases: `data_center_item` and `same_item`. On the local warehouse,
`data_center_public_comment` goes from 19 to 29 rows, and the 10 new rows are all Casa Grande's "Phoenix Mart PAD"
speakers.

The first review pass found three blocking problems and four important ones:
- the positions endpoint would have returned 500 on the new values;
- the load step didn't select the new bronze model;
- the data contracts were stale;
- the mart included superseded analyses;
- `same_item` could spread from the AI summary;
- `decision_headline` was null on non-data-center uncontested items;
- the mart wasn't classified for Neon.

All are fixed in `8c411eb5` and verified below. One nit is documented rather than fixed. Verdict: **approve-with-nits**.

## Scope of Change

- Files changed: 18 (+451 / -48 excluding the generated `dbt_project/contracts/` files (+137 / -5) and this review)
- Areas touched: dbt_project, api, web_app (type only), packages (hosting), web_docs, tests
- Commits:
  - 92019ebd feat(dbt): bring uncontested items into the warehouse and count same-item and consent-item data center comments
  - 8fcce8fa test(dbt): unit-test the data center comment rule for same-item and consent-item matches
  - 698441e4 docs(pr-934): auto-write rubric review [skip review] (CI bot)
  - 8c411eb5 fix(data-centers): serve the new match bases and wire the uncontested-item models through load, contracts and Neon
- Range reviewed: `6bf23065..108c86a8`

## CI Status

| Check | Status |
|---|---|
| PR conventions (linked issue) | pass |
| Frontend Build | see PR checks on `108c86a8` (pending at time of writing) |
| Documentation Build | see PR checks (pending); `npm run build` passed locally |
| Backend Tests | see PR checks (pending); the affected suites passed locally |
| API Types | see PR checks (pending); `tsc --noEmit` passed locally |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean (grep for key, token and credentialed-URL patterns on added lines; pre-commit secret hooks passed).
- Fabricated data in a served path: clean. The API change only widens an enum and a description. Test rows stay in `tests/`.
- Personal data: clean. The new table holds meeting agenda items (public records).
- Destructive or bulky changes: clean. Nothing is deleted, no raw files are added, and all warehouse changes go through dbt.

## Strengths

- The rule stays in one dbt view, and the API still only reads marts. Every new basis needs evidence from the record itself
  (a headline, or a speaker's verbatim quote), and the doc records what was measured and ruled out.
- There's a test for each layer that fails before the change: a dbt unit test for the rule (fails on `main`'s rule) and a
  pytest for the endpoint (fails on `main`'s route).

## Findings

### 🔴 Blocking (Critical)

All fixed in `8c411eb5`:

1. `api/routes/data_centers.py:1335`: `PositionQuote.match_basis` was `Literal["data_center_decision", "own_words"]`, so
   any `same_item` or `data_center_item` quote failed validation and returned 500 for the whole scope. **Fixed**: widened
   the Literal and updated `web_app/src/api/dataCenters.ts`. `test_every_match_basis_the_rule_emits_is_served` fails on
   `main`'s route and passes here.
2. `packages/hosting/src/hosting/deploy/run_deployment.py`: the load step's dbt selector didn't include
   `bronze_uncontested_items_from_ai`, so `event_uncontested_item` would rebuild from a stale or missing table.
   `tests/test_load_tab_steps_796.py` caught it. **Fixed**: added the selector, and the test passes (13/13).
3. `dbt_project/contracts/`: the ODCS/ODPS contracts were stale or missing. **Fixed**: ran
   `python -m models.odcs --write`, and `--check` reports them current.

### 🟡 Should fix (Important)

All fixed in `8c411eb5`:

4. `int_data_center__public_comment.sql`: `decision_headline` was null for `same_item` and `own_words` comments on an
   uncontested item whose headline doesn't name a data center. **Fixed**: headlines now come from every
   `event_uncontested_item` row; the unit test covers the case (c9, c10).
5. `int_data_center__public_comment.sql`: `same_item` spread from `stance_evidence || summary`, so one AI paraphrase
   could pull in a whole item. **Fixed**: it spreads from `stance_evidence` only. The unit test covers it (c11 counts,
   c12 doesn't).
6. `event_uncontested_item.sql`: it joined only `event_meeting`, which is append-only, so items from 9 superseded analyses
   (90 items) were kept. **Fixed**: inner join to `int_preferred_event_analysis`, as `event_decision` does; 40,885 → 40,795
   rows.
7. `hosting/neon/sync_public_to_neon.py`: the new mart was unclassified. **Fixed**: it's `NON_SERVING` until #933 gives it
   a reader, and the doc says so.
8. `data-center-who-spoke-up.md`, "Build it": the selectors lacked the two new models. **Fixed.**

### 🔵 Nits / suggestions (Minor)

9. `_schema_event_uncontested_item.yml`: the fixed-name `create index if not exists` was skipped on alternate builds
   (name collision during dbt's rename swap). **Fixed** with an unnamed index; it was present after two consecutive builds.
10. `bronze_uncontested_items_from_ai.sql`: when an analysis repeats an `item_id`, only the first item is kept (13 items
    locally, 11 in analysis 26073). **Not fixed**, documented in the design page and as a dated note on #932. Keying
    repeats by position would change `item_id`, which `public_comment` uses to join.
11. Stale wording in the `data_center_public_comment.sql` header and the over-count note in the doc. **Fixed.**

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `feat/932-…`; `Closes #932`; the issue has all four parts; follow-up #933 opened |
| Conventional Commits | ✅ | Every commit typed and scoped, with co-author trailer |
| No fabricated data | ✅ | Scan clean |
| New Python in `packages/` | ✅ | No `scripts/` changes |
| dbt for transformations | ✅ | JSONB extraction in a bronze dbt model; the rule in an intermediate view |
| Naming | ✅ | `state_code` and `state` present; no `dim_`/`fact_` |
| Keys | ✅ | `event_uncontested_item`: PK + enforced FK to `event_meeting`; tests pass |
| Calendar years | n/a | |
| Scope label matches filter | n/a | No UI change |
| Match evidence on filtered tiles | ✅ | Every counted row keeps the verbatim quote and the item headline that explains it |
| Docs | ✅ | `web_docs/docs/development/data-center-who-spoke-up.md` updated |
| Telemetry and logging | n/a | No new route or script |
| Tests | ✅ | dbt unit test and pytest, each failing before the change |
| Shared libraries | ✅ | `packages/hosting` and `packages/datamodels` tests run: 84 + others pass |

## Test Coverage

Run locally against the local warehouse (localhost:5433):
- `dbt run` of the changed models: 15/15. `dbt test` on `event_uncontested_item`, the rule view and both marts: 30/30,
  including the unit test.
- The unit test `dc_comment_rule_same_item_and_consent_items` fails on `main`'s rule.
- `pytest` on `packages/datamodels/tests`, `packages/hosting/tests`, `tests/test_api_data_center_positions.py` and
  `tests/test_load_tab_steps_796.py`: 105 passed.
- `python -m models.odcs --check`: current.
- `cd web_app && npx tsc --noEmit`: clean.
- `cd web_docs && npm run build`: success.
- `ruff check` on the changed Python: the same 5 findings as on `main`, none new.

Not tested: the Neon copy (deliberately excluded), and the live endpoint (the local API process runs older code).

## Verdict

**approve-with-nits**: the only open item (#10) is documented and has no effect on current data center rows. Merge once
the required CI checks are green on the head.
