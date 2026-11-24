---
pr: 846
branch: feat/845-matrix-map-folio-look
title: "feat(web_app): give the Matrix map the look and motion of the Folio reference"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 89a96d5d539fde16b69624d950623e4a19a669ef
verdict: approve
---

# PR Review: feat(web_app): give the Matrix map the look and motion of the Folio reference

## Summary

Automated review (#648) for PR #846 on `feat/845-matrix-map-folio-look`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/package-lock.json`
- `web_app/package.json`
- `web_app/src/components/DotMatrixMap.tsx`
- `web_app/src/hooks/useCountUp.ts`
- `web_app/src/hooks/useFlip.ts`
- `web_app/src/hooks/usePrefersReducedMotion.ts`
- `web_app/src/pages/DataExplorerMatrixPage.tsx`
- `web_app/src/styles/folio.css`
- `web_app/src/utils/folioMotion.test.ts`
- `web_app/src/utils/folioMotion.ts`
- `web_app/src/utils/folioRamp.test.ts`
- `web_app/src/utils/folioRamp.ts`
- `web_docs/docs/guides/data-explorer-matrix-map.md`

## CI Status

See the PR checks on `89a96d5d539f`.

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
