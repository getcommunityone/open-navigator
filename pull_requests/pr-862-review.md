---
pr: 862
branch: feat/858-matrix-table-bars-sparklines
title: "feat(web_app): Matrix map tables and stacked bar match the reference"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: ae1c31dd698f712ede9c955e53a6c235589c2142
verdict: approve
---

# PR Review: feat(web_app): Matrix map tables and stacked bar match the reference

## Summary

Automated review (#648) for PR #862 on `feat/858-matrix-table-bars-sparklines`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

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
