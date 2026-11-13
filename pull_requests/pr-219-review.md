---
pr: 219
branch: fix/connecticut-fips-planning-regions
title: "fix(census): show Connecticut's legacy counties as not available since 2022"
author: BlueHopper6
reviewed_at: 2026-11-13
reviewer: maintainer session (coordinator) + helper agent
verdict: approve
---

# PR Review: fix(census): show Connecticut's legacy counties as not available since 2022

## Summary

Since the 2022 American Community Survey, Connecticut reports by nine planning regions (`09110`-`09190`) instead of
its eight legacy counties (`09001`-`09015`), but the county basemap still draws the legacy counties, so they showed
blank with no explanation (issue #71). The first version of this PR filled them with figures computed from the
planning regions using population weights. Planning regions don't nest inside counties, and medians and rates can't
be averaged, so those figures were invented, which CLAUDE.md's No Fabricated Data rule forbids. The maintainer commits
replace that with an honest gap: the export writes each legacy county with null metrics and a `data_note`, and the map
shows "Not available: Connecticut reports by planning region since 2022" in the popup and once in the legend. A last
commit shows the same note for data exported before the note existed, so the map explains the gap before the export
is re-run. The verdict is approve.

## Scope of Change

- Files changed: 4, no generated files
- Areas touched: ingestion (`packages/ingestion/.../export_census_map_static.py`), web_app (`CensusMapPage.tsx`,
  `censusMapTransforms.ts`), tests
- Commits:
  - the contributor's crosswalk commits (population-weighted synthesis, now removed)
  - 7d40a1d fix(census): show Connecticut legacy counties as not available instead of blended values (maintainer)
  - 2b90a21 fix(census): explain Connecticut's missing county figures before the export is re-run (maintainer)
  - merges of `main`
- Range reviewed: merge base with `main` to `2b90a21`, then the sync with `main` at `3369986`

## CI Status

| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success on `7d40a1d`; `tsc --noEmit` and `npm run build` pass locally on `2b90a21` |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success on `7d40a1d` |
| API Types (OpenAPI -> TypeScript) | success on `7d40a1d` |
| Docker Build Test | skipped (no Docker files changed) |

All four are checked green on the final head before merging.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data in a served path:** fixed. No county figure is derived from planning regions anywhere, in the
  export or the browser. A missing value stays missing and says why.
- **Personal data:** clean. Public Census geography only.
- **Destructive data changes:** clean. The export overwrites its own output files, as before.

## Strengths

- Fixes the real problem in #71 (blank counties with no explanation) without inventing numbers.
- The note text lives in one constant (`CT_PLANNING_REGION_UNAVAILABLE_TEXT`) used by the popup and the legend.
- The legacy-county fallback only explains a missing value. It never fills one, and pre-2022 vintages, where the
  legacy counties have real figures, are unchanged.
- The export keeps the real FIPS-to-name mapping (`CONNECTICUT_LEGACY_COUNTY_NAMES`) and drops the invented weights.

## Findings

### 🔴 Blocking (Critical)

None after `7d40a1d`. The population-weighted synthesis was blocking and is removed.

### 🟡 Should fix (Important, non-blocking)

1. **Re-run the census export** so the served `county_metrics.json` and `county_trends_09.json` carry the `data_note`.
   The frontend fallback covers the gap until then. This needs the Census API, which this session can't reach.

### 🔵 Nits / suggestions (Minor)

1. **Draw the planning regions.** A later change could add the nine planning-region shapes so Connecticut's 2022+
   figures appear on the map at their real geography. Follow-up issue.

## Repo-Rule Compliance

| Rule (CLAUDE.md) | Status |
|---|---|
| No Fabricated Data | ✅ after `7d40a1d` |
| Conventional Commits | ✅ |
| Never push to `main`, never force-push | ✅ (merges only) |
| Required checks green | re-checked on the final head |
| New Python in `packages/`, not `scripts/` | ✅ (`packages/ingestion`) |
| Issue first, `Closes #<issue>` (AGENTS.md) | ✅ `Closes #71`; opened Nov 3, before the four-part rule's start date |

## Test Coverage

`packages/ingestion/tests/test_connecticut_fips_crosswalk.py`: 7 tests pass. They check that legacy counties get null
metrics and the note, that other states are untouched and that existing values are kept. The web app has no unit test
runner, so the frontend change is covered by `tsc --noEmit` and the build.

## Verdict

**Approve.** Merge when the four required checks are green on the final head, then re-run the census export (Should
fix 1).
