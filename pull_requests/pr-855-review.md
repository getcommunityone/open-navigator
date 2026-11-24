---
pr: 855
branch: feat/847-matrix-map-sections
title: "feat(web_app): turn the Matrix map into a sectioned scrolling report"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 619c407108e88d6f0fa7b1b498844adced288203
verdict: approve-with-nits
---

# PR Review: feat(web_app): turn the Matrix map into a sectioned scrolling report

## Summary

Turns the Matrix map from seven tabbed layouts into a scrolling report of twelve numbered sections in the reference's
layout (title and explanation left, chart right), and adds the features it lacked: five chart types, a data table
under every figure, interactive legends, a section band, animated titles, tile regrouping and seven themes. The page
file shrinks from 983 to 313 lines, with one component per section. Unit tests, type check and build pass, and every
section was rendered in a browser against a throwaway fixture. It has not been seen against the real census bundle.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `web_app/src/components/matrix/BarsSection.tsx`
- `web_app/src/components/matrix/ColumnsSection.tsx`
- `web_app/src/components/matrix/CompareSection.tsx`
- `web_app/src/components/matrix/DivergingBars.tsx`
- `web_app/src/components/matrix/DivergingSection.tsx`
- `web_app/src/components/matrix/DotsSection.tsx`
- `web_app/src/components/matrix/HeatmapSection.tsx`
- `web_app/src/components/matrix/Kpi.tsx`
- `web_app/src/components/matrix/LegendChips.tsx`
- `web_app/src/components/matrix/PivotSection.tsx`
- `web_app/src/components/matrix/ScatterSection.tsx`
- `web_app/src/components/matrix/SectionBand.tsx`
- `web_app/src/components/matrix/SectionShell.tsx`
- `web_app/src/components/matrix/ShareSection.tsx`
- `web_app/src/components/matrix/TableSection.tsx`
- `web_app/src/components/matrix/TilesSection.tsx`
- `web_app/src/components/matrix/Tooltip.tsx`
- `web_app/src/components/matrix/TrendSection.tsx`
- `web_app/src/components/matrix/data.test.ts`
- `web_app/src/components/matrix/data.ts`
- `web_app/src/components/matrix/hooks.ts`
- `web_app/src/components/matrix/parts.tsx`
- `web_app/src/components/matrix/types.ts`
- `web_app/src/hooks/useFlip.ts`
- `web_app/src/pages/DataExplorerMatrixPage.tsx`
- `web_app/src/styles/folio.css`
- `web_app/src/utils/folioRamp.test.ts`
- `web_app/src/utils/folioRamp.ts`
- `web_app/src/utils/folioThemes.ts`
- `web_app/src/utils/matrixMapMath.test.ts`
- `web_app/src/utils/matrixMapMath.ts`
- `web_app/src/utils/matrixTable.test.ts`
- `web_app/src/utils/matrixTable.ts`
- `web_docs/docs/guides/data-explorer-matrix-map.md`

## CI Status

See the PR checks on `619c407108e8`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. Headlines, figures and tables are computed from the loaded bundle; none of the reference's sample numbers or copy is reused; the trend has no invented milestones and the columns no forecast bar; a metric that cannot be summed shows an explicit state instead of a sum; missing values are a dash in charts and an empty cell in CSV. The browser fixture was served by a request intercept and is not in the repo.

## Strengths

- Contrast is a unit test over every theme's ramp, series, text and band colours, not a judgement call.
- The CSV writer, row filter, region stacking and series toggles are pure functions with tests; region stacking
  never treats a missing value as zero.
- Existing URL parameters keep working, and `layout` became a deep link instead of being dropped.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- Not seen against real census data, and Share and Dot map were not exercised in county mode. The owner should
  scroll the whole page once after pulling and report anything that looks wrong with real values.
- `sort` and `dir` are one pair shared by Pivot, Heatmap, Table, Compare and Diverging, so sorting one section can
  reorder another. Documented in the guide; per-section sort parameters would be cleaner.

### 🔵 Nit (Minor)

- No keyboard-only walkthrough was done; focus styles exist but were not tabbed through.
- Compare's axis starts at zero, so values far from zero cluster to the right.
- The Absolute / Share of total toggle is component state, not in the URL.
- Four of the seven themes were captured but not looked at by eye.

## Verdict

**approve-with-nits**
