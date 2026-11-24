---
pr: 839
branch: fix/838-data-explorer-missing-bundle
title: "fix(web_app): say so when the Data explorer's census data files are missing"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 50cb334d8154c5f163a2ab19885216f1f12dcfdd
verdict: approve
---

# PR Review: fix(web_app): say so when the Data explorer's census data files are missing

## Summary

Automated review (#648) for PR #839 on `fix/838-data-explorer-missing-bundle`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/pages/CensusDrilldownMapPage.tsx`
- `web_app/src/pages/DataExplorerMatrixPage.tsx`
- `web_app/src/utils/fetchStaticJson.test.ts`
- `web_app/src/utils/fetchStaticJson.ts`
- `web_docs/docs/guides/data-explorer-matrix-map.md`

## CI Status

See the PR checks on `50cb334d8154`.

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
