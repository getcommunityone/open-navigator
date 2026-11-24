---
pr: 855
branch: feat/847-matrix-map-sections
title: "feat(web_app): turn the Matrix map into a sectioned scrolling report"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 619c407108e88d6f0fa7b1b498844adced288203
verdict: approve
---

# PR Review: feat(web_app): turn the Matrix map into a sectioned scrolling report

## Summary

Automated review (#648) for PR #855 on `feat/847-matrix-map-sections`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

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
- Fabricated data / personal / destructive: see findings

## Strengths

- Automated scans found no secret/credential patterns in added lines.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None from automated heuristics.

### 🔵 Nit (Minor)

None from automated heuristics.

## Verdict

**approve**
