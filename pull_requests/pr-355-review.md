---
pr: 355
branch: feat/351-governments-count
title: "feat(stats): count local governments, not Census geographies, as governments_count"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve-with-nits
---

# PR Review: feat(stats): count local governments, not Census geographies, as governments_count

## Summary
Closes #351. Adds `governments_count` to `jurisdiction_state_aggregate`, national and state rows. It counts counties, school districts, and the places and county subdivisions with Census FUNCSTAT A/B/C, and serves the figure from `GET /api/stats` as `governments`. The filter uses FUNCSTAT rather than LSAD, which sidesteps the repo's LSAD 37 vs Census 57 inconsistency noted on #351. The codes were checked against the Census functional-status code list. The change is stacked on #348 (same model), so it can't merge or get CI until #348 merges and GitHub retargets it to `main`. dbt hasn't been run here, so the verdict is approve-with-nits.

## Scope of Change
- Files changed: 5 (+~50 / -4)
- Areas touched: dbt_project, api, tests
- Commits: the feature commit (see `git log fix/291-national-stats-counts..feat/351-governments-count`)
- Range reviewed: `fix/291-national-stats-counts..feat/351-governments-count`

## CI Status
| Check | Status |
|---|---|
| All required checks | ⏸ not triggered: the CI workflow runs on PRs into `main`/`develop`, and this PR's base is `fix/291-national-stats-counts`. It runs once #348 merges and this PR is retargeted. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean. The API returns `None`, not 0, when the column is absent or the row is a fallback. The column description states exactly what is and isn't counted.
- Personal data: clean (aggregate counts).
- Destructive data changes: clean.

## Strengths
- Uses the Census field designed for this (FUNCSTAT), already loaded for both relevant tables (`ingestion.census.gazetteer`). Verified: `int_jurisdictions` passes `funcstat` through for municipalities (`m.funcstat`) and townships (`t.funcstat`), and its final select exposes `u.funcstat` and `u.jurisdiction_type`.
- The regression test checks the new figure against a direct count and that it never exceeds `jurisdictions_count`.
- The contract decision and its limits are written on #351.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- Counties and school districts are counted without a government check, because their bronze tables have no FUNCSTAT. That over-counts slightly (Alaska census areas, Connecticut planning regions, dependent school districts). It's documented in the column description; a future fix would load the TIGER county and school-district FUNCSTAT.
- Virginia's independent cities appear both as county equivalents and as places, so they count twice. Small and documented only here; worth an `action-item` if the figure is quoted precisely.
- `ingestion.census.municipalities` (a second loader) keeps only FUNCSTAT `A` rows. If it's the one that filled the municipalities table, the filter is a no-op for places — still correct.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `feat/351-…`, `Closes #351`; #351 has four parts; dated Contract decision comment |
| Conventional Commits | ✅ | Co-author trailer |
| No fabricated data | ✅ | `None` when unavailable |
| dbt for transformations | ✅ | Filter in the mart SQL |
| Naming | ✅ | `governments_count` / `governments`, matching the existing `*_count` → key pattern |
| Keys | ⚠️ | Mart still has no PK (pre-existing, #271) |
| Tests | ✅ | API tests + extended singular dbt test |

## Test Coverage
- `tests/test_api_stats_governments.py`: 3 passed; 3 failed on the base branch.
- `ruff check` on the new test: clean.
- Not run: `dbt build` (no warehouse in this session).

## Verdict
**approve-with-nits.** Merge after #348. Run `dbt build --select jurisdiction_state_aggregate assert_national_stats_jurisdiction_counts` once with both changes in place.
