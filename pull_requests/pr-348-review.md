---
pr: 348
branch: fix/291-national-stats-counts
title: "fix(stats): populate jurisdiction and school-district counts on national and state rows"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: data-dbt-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: fix(stats): populate jurisdiction and school-district counts on national and state rows

## Summary
Part of #291 (`Refs`, not `Closes`). The national and state rows of `jurisdiction_state_aggregate` now count jurisdictions and school districts from `int_jurisdictions` instead of hardcoding 0. Nonprofit leaders are counted with one `COUNT(DISTINCT)` per level. The reviewer found two important gaps, and both are fixed in ab651eb. First, the count included census-designated places and other non-government geographies while the description said "local government units". The description now says exactly what is counted, and #351 tracks a true government count. Second, there was no regression test; `assert_national_stats_jurisdiction_counts.sql` now covers it. The SQL could not be compiled or run here, because the warehouse is unreachable and dbt packages can't be downloaded. So the verdict is approve-with-nits, conditional on a local `dbt build`.

## Scope of Change
- Files changed: 3 (+94 / -8)
- Areas touched: dbt_project
- Commits:
  - 3f71906 fix(stats): populate jurisdiction and school-district counts on national and state rows
  - ab651eb fix(stats): describe jurisdictions_count as Census geographies and test the national counts
- Range reviewed: `b448a7c..ab651eb`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | ✅ success (ab651eb) |
| Documentation Build | ✅ success (ab651eb) |
| Backend Tests | ⏳ running on ab651eb (✅ on 3f71906) |
| API Types | ⏳ running on ab651eb (✅ on 3f71906) |
| PR conventions | ✅ success (ab651eb) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean. Every figure is a count over warehouse tables, and the description of `jurisdictions_count` now matches what it counts.
- Personal data: clean (aggregate counts only).
- Destructive data changes: clean (dbt model change only).

## Strengths
- It uses `Refs` rather than `Closes` and names both open items in #291: nonprofit leaders still exceed persons, because the ID is name + EIN and so counts positions, not people; and Neon still needs a refresh.
- The bridge table is scanned once for the state rows instead of once per state.
- The column order and `INTEGER` types of the UNION ALL branches still line up.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- ~~`jurisdiction_state_aggregate.sql` (`jurisdiction_counts`) and the schema description: "local government units" while `int_jurisdictions` also holds census-designated places and non-governmental county subdivisions.~~ **Fixed in ab651eb (relabelled).** The government-only count is tracked in #351. Verified: the municipalities CTE in `int_jurisdictions.sql` strips a `cdp` suffix without filtering those rows out. Note for #351: the repo labels LSAD `37` as CDP, while the Census Gazetteer uses `57`, so check the code against the data.
- ~~No regression test.~~ **Fixed in ab651eb:** `dbt_project/tests/assert_national_stats_jurisdiction_counts.sql` checks the national counts against a direct count, and that no state with jurisdictions reports 0.
### 🔵 Nits / suggestions (Minor)
- ~~The national leader count (no `state_code` filter) and the state rows (filtered; an org that moved states can appear twice) don't reconcile.~~ **Documented in a comment in ab651eb.**
- `COUNT(DISTINCT jurisdiction_id)` would silently drop NULL IDs, and `jurisdiction_id` is untested. **Fixed in ab651eb:** now `COUNT(*)`, which is exact because `geoid` is tested unique and not null (`_intermediate.yml`).
- `jurisdiction_state_aggregate` declares no primary key. This predates the PR and is covered by #271 (served relations without a contract).

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `fix/291-…`, `Refs #291`; #291 has the four parts; follow-up #351 opened |
| Conventional Commits | ✅ | Co-author trailers present |
| No fabricated data | ✅ | Description now states what the number counts |
| New Python in `packages/` | n/a | |
| dbt for transformations | ✅ | Marts layer, all SQL in dbt |
| Naming | ✅ | No new names |
| Keys | ⚠️ | No PK on this mart (pre-existing, #271) |
| Calendar years | n/a | |
| Scope label / Match evidence | n/a | |
| Docs | n/a | |
| Telemetry and logging | n/a | |
| Tests | ✅ | Singular test added |
| Shared libraries | n/a | |

## Test Coverage
- New singular test: `assert_national_stats_jurisdiction_counts.sql`.
- **Not run.** `localhost:5433` is unreachable from the review session, and `dbt deps` / `dbt compile` failed because hub.getdbt.com is blocked here, so neither the model nor the test was compiled.
- Consumers were checked: `api/routes/stats_neon.py` passes the values through with `.get(…, 0)`; nothing in `web_app/src` reads them.

## Verdict
**approve-with-nits.** Run `dbt build --select jurisdiction_state_aggregate assert_national_stats_jurisdiction_counts` locally before merging. #291 stays open for the leaders field (rename or redefine — the maintainer's call) and for the Neon refresh.
