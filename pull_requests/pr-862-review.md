---
pr: 862
branch: feat/858-matrix-table-bars-sparklines
title: "feat(web_app): Matrix map tables and stacked bar match the reference"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: ae1c31dd698f712ede9c955e53a6c235589c2142
verdict: approve-with-nits
---

# PR Review: feat(web_app): Matrix map tables and stacked bar match the reference

## Summary

Brings three Matrix map sections up to the reference screenshots the owner sent: the Table gets in-cell bars, a
Change column, sparklines, a Region column and a fixed header; the Share bar gets labels with leader lines and
percentages inside its segments; the Pivot gets the reference's styling, a Share column and a Total row. Unit tests,
type check and build pass, and the sections were checked in a browser against a fixture with deliberate gaps. Not
seen with real census data.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `web_app/src/components/matrix/CompareSection.tsx`
- `web_app/src/components/matrix/PivotSection.tsx`
- `web_app/src/components/matrix/ShareSection.tsx`
- `web_app/src/components/matrix/TableSection.tsx`
- `web_app/src/components/matrix/TilesSection.tsx`
- `web_app/src/components/matrix/data.ts`
- `web_app/src/components/matrix/parts.tsx`
- `web_app/src/components/matrix/types.ts`
- `web_app/src/pages/DataExplorerMatrixPage.tsx`
- `web_app/src/styles/folio.css`
- `web_app/src/utils/folioRamp.test.ts`
- `web_app/src/utils/matrixTable.test.ts`
- `web_app/src/utils/matrixTable.ts`
- `web_docs/docs/guides/data-explorer-matrix-map.md`

## CI Status

See the PR checks on `ae1c31dd698f`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. A missing value is a dash in the table, an empty CSV cell and a gap in the sparkline; no change is computed from a missing value; the Total row appears only for metrics that can be summed. The browser fixture was served by a request intercept and is not in the repo.

## Strengths

- The signed-change formatting and colouring are one shared helper for Compare and the Table, so they agree.
- Sparklines break at a missing vintage instead of drawing a line across it, and a test covers that.
- New bar, sparkline and leader colours are added to the per-theme contrast test.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- Pivot shares are a share of all rows including Puerto Rico, while the Share section excludes Puerto Rico. Two
  sections of one page can therefore show different shares for the same state. They should use one denominator.
- Not seen with real census data, nor Pivot grouped by region, nor Share in county mode.

### 🔵 Nit (Minor)

- The Table is at least 960 px wide, so on narrow screens Change and Trend start off-screen to the right.
- The CSV's Change is the plain numeric difference while the table shows "+5.3 pp"; fine for a data file, but worth
  a line in the guide (it has one).
- Share's bar shows whole percentages while its tooltip and data table show one decimal.

## Verdict

**approve-with-nits**
