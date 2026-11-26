---
pr: 1098
branch: fix/1095-explorer-sheet-flicker
title: "fix(data-explorer): a pinned county's panel no longer covers the map or flickers; county name when no towns"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 125301e17aebbbe120fc488cf93e0495bf81e425
verdict: approve
---

# PR Review: fix(data-explorer): a pinned county's panel no longer covers the map or flickers; county name when no towns

## Summary

Automated review (#648) for PR #1098 on `fix/1095-explorer-sheet-flicker`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/components/CensusDrilldownStage.tsx`
- `web_app/src/pages/CensusDrilldownMapPage.tsx`
- `web_docs/docs/guides/data-explorer-matrix-map.md`

## CI Status

See the PR checks on `125301e17aeb`.

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
