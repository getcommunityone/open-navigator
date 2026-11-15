---
pr: 354
branch: feat/137-money-median-income
title: "feat(money): start the income slider at the real ACS local median household income"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: data-dbt-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: feat(money): start the income slider at the real ACS local median household income

## Summary
Closes #137. The money modal's income slider now starts at the place's real ACS median household income (B19013), labelled as the local median, instead of starting empty. The value is loaded by the existing property-tax ingestion, carried through `stg_acs_property_tax` and `jurisdiction_property_tax_rate`, and served by `GET /api/local-finance/property-tax-rate`. Each layer works before the data refresh: staging falls back to NULL if the raw table lacks the column, the API reads it with `to_jsonb` so an older Neon table returns null, and the UI keeps today's empty slider on null. No Critical or Important findings. The one Minor UI finding (stale seeded medians if the place changed while the bill stayed mounted) is fixed in 27f2dbb. Not compiled or run against data here, so approve-with-nits.

## Scope of Change
- Files changed: 12
- Areas touched: packages (ingestion), dbt_project, api, web_app, tests
- Commits:
  - eac187b feat(money): start the income slider at the real ACS local median household income
  - 27f2dbb fix(money): remount the bill per place so seeded medians never carry over
- Range reviewed: `main...27f2dbb`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | see PR checks on head |
| Documentation Build | see PR checks on head |
| Backend Tests | see PR checks on head |
| API Types | see PR checks on head |
| PR conventions | see PR checks on head |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean. The income comes only from ACS; when it's null the slider stays empty and the copy says the income is the user's own. Test values live only in tests.
- Personal data: clean (place-level medians only).
- Destructive data changes: clean. `ALTER TABLE … ADD COLUMN IF NOT EXISTS` on bronze only adds; the loader's existing per-vintage delete/upsert is unchanged.

## Strengths
- Each layer handles the window before the refresh, so merging before the reload changes nothing for users.
- The footnote cites the same ACS vintage as the property-tax rate.
- ODCS contract regenerated with the repo's generator rather than edited by hand.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- ~~`MoneyGameModal.tsx` (`YourBill` had no `key`): a place change while mounted would keep the old place's seeded medians.~~ **Fixed in 27f2dbb** (`key` = state|city|county). Note: "(change)" (`changePlace`, `:1845`) sets the place to null, which shows the place gate and unmounts the bill, so the case was unlikely in practice; the key covers home value as well.
- `tests/test_api_property_tax_rate_income.py:108` asserts an exact SQL substring, so a harmless rewording of the query would fail it. Kept deliberately: the tolerant read is the behaviour that protects the card before the Neon sync.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `feat/137-…`, `Closes #137`; four parts appended to #137 (dated); state income tax split to #353 |
| Conventional Commits | ✅ | Co-author trailers |
| No fabricated data | ✅ | Null → empty slider |
| New Python in `packages/` | ✅ | Loader change is in `packages/ingestion`; nothing in `scripts/` |
| dbt for transformations | ✅ | Pass-through in staging/mart; no SQL logic in Python |
| Naming | ✅ | `median_household_income`, matching `stg_data_commons__jurisdiction` |
| Keys | ✅ | PK/FK of the mart unchanged and enforced |
| Calendar years | ✅ | Unchanged (`acs_vintage_year` integer) |
| Scope label / Match evidence | n/a | |
| Docs | n/a | |
| Telemetry and logging | ✅ | Existing span and loguru messages updated |
| Tests | ✅ | Loader (2) and API (3) tests fail on `main`, pass here |
| Shared libraries | ✅ | `packages/datamodels` contract tests run (38 passed) |

## Test Coverage
- `packages/ingestion/tests/test_census_property_tax_fetch.py`: 2 passed (2 failed on `main`).
- `tests/test_api_property_tax_rate_income.py`: 3 passed (3 failed on `main`).
- `packages/datamodels/tests/test_odcs.py` + `test_odps.py`: 38 passed.
- `tsc --noEmit` and ESLint on the changed frontend files: clean.
- Rendered in headless Chrome against a mock API: with an income figure, "Household income · local median $52,000" and "1.7% of your household income"; with null, unchanged from today.
- Not run: `dbt compile/build` (no warehouse; dbt hub blocked here) and the Census loader (no network to api.census.gov).

## Verdict
**approve-with-nits.** Safe to merge before the data refresh. To make it show: run `python -m ingestion.census.property_tax`, then `dbt build --select stg_acs_property_tax+`, then the Neon sync of `jurisdiction_property_tax_rate`.
