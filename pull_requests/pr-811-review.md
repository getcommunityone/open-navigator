---
pr: 811
branch: feat/806-data-explorer-matrix-map
title: "feat(web_app): add the Matrix map tab to Data explorer"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: feat(web_app): add the Matrix map tab to Data explorer

## Summary
Adds a Matrix map tab to Data explorer with seven layouts over the published ACS bundle. The first review pass at
`8d9cc3ca` returned **request-changes**: no blocking defects, but six should-fix items, three of which affected users
(rows ordered by an unrelated metric in two layouts, a dot map that stayed on "Loading map…" when the shapes could not
be fetched and could not be drilled by keyboard, and a false "only one vintage" message). All six were fixed on the
branch and re-checked in a browser, which moves the verdict to approve-with-nits. No fabricated data was found. The page
has still not been run against the real ACS bundle.

## Scope of Change
- Files changed: 12 (excluding this review)
- Areas touched: web_app / web_docs
- Commits: `8d9cc3ca` feat(web_app): add the Matrix map tab to Data explorer, plus the review-fix commit that carries
  this file
- Range reviewed: `origin/main...origin/feat/806-data-explorer-matrix-map` at `8d9cc3ca`; fixes verified by the coordinator

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | Not run at review time: the bot's review commit became the head and does not trigger workflows. Read them on the commit that carries this file before merging. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean. The reviewer checked every literal: shade stops, the 975×610 map box and the
  dot-grid column counts are presentation constants. Test values exist only in the unit test.
- Personal data: clean.
- Destructive or bulky data changes: clean.

## Strengths
- Every hook runs before its early return; the waffle allocation sums to exactly 100; the OLS slope and r² are correct;
  county filtering by 5-digit GEOID prefix and FIPS padding are consistent; the point-in-polygon test is correct.
- All view state is in the URL and each layout has an explicit empty state.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
All fixed on the branch.
1. `DataExplorerMatrixPage.tsx` sort key: Diverging and Compare were ordered by `sort` or the first pivot column, not
   the metric on screen. Fixed with `activeSortKey()` (pivot uses the header sort; every other layout uses its metric).
   Verified in a browser: `?layout=diverging&metric=b&sort=a` orders by `b`.
2. `DotMatrixMap.tsx`: the shape fetches never checked `r.ok`, so a blocked CDN left "Loading map…" forever; dots were
   mouse-only. Fixed: an explicit "map shapes could not be loaded" state (verified by aborting the requests), and a
   state list above the map so the drill-down works by keyboard and touch. Reading a single dot's value still needs a
   pointer; the guide says to use Tiles or Pivot for that.
3. Compare: "only one vintage is published" was shown while the earlier year was loading or missing. Fixed: separate
   loading and "file could not be loaded" states (verified with a 404).
4. Legend: "Lowest … Highest" was wrong for lower-is-better metrics. Fixed: "Lower rank … Higher rank" with a note.
5. No tests. Fixed: the maths moved to `utils/matrixMapMath.ts` with 10 unit tests (shade flip, median, waffle
   allocation, OLS, sort key).
6. Guide claimed the Highlight slider applies to the Dot map. Fixed in the guide.

### 🔵 Nits / suggestions (Minor)
Fixed: median for an even count; the last pivot column can no longer be unchecked; an unknown `?metric=` falls back to
the first metric; the group toggle is hidden for Scatter; `aria-sort` on pivot headers; county shades are labelled
"scaled within this state"; the type shim is marked temporary.

Left as is:
- The us-atlas shapes come from a CDN, as the existing map page does. Vendoring them is a separate change.
- `geo-untyped.d.ts` types `d3-geo` and `topojson-client` as `any` for every importer. No regression today (neither
  `@types` package is installed, and the existing importers use `@ts-nocheck`); delete it when the types are added.
- The Highlight threshold works on the rank scale, so for lower-is-better metrics it keeps low values.
- The meeting-metrics design page records best-judgement decisions; the owner confirmed them in the session.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #806 with the four parts; branch `feat/806-data-explorer-matrix-map`; `Closes #806` |
| Conventional Commits | Yes | |
| No fabricated data | Yes | Scan above; explicit empty states |
| Scope label matches filter | Yes | The label names the drilled state's counties and the vintage or year range; scope is in the URL |
| Match evidence on filtered tiles | n/a | No content filter |
| Docs | Yes | `guides/data-explorer-matrix-map.md`, `development/meeting-metrics-matrix-map-design.md` |
| Telemetry and logging | No | No frontend spans added for the new tab; the neighbouring Data explorer pages have none either |
| Tests | Yes | 10 unit tests for the maths and the sort key; no component test |

## Test Coverage
`vitest run src/utils/matrixMapMath.test.ts`: 10 passed. `npx tsc --noEmit`, `eslint --max-warnings 0` on the changed
files and `npm run build` pass. In Chromium against the dev server, with test-only data served by request
interception and the real us-atlas shapes: all ten views render with no page or console errors, and the four failure
cases above behave as described. Not run: the real ACS bundle, the docs build (left to CI).

## Verdict
approve-with-nits. Nothing must change first.
