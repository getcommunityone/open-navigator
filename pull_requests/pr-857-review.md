---
pr: 857
branch: fix/856-lazy-matrix-page
title: "fix(web_app): load the Matrix map page only when its tab is opened"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: e401b45b0df6a68d85ad6baade9cde08c0122367
verdict: approve
---

# PR Review: fix(web_app): load the Matrix map page only when its tab is opened

## Summary

Automated review (#648) for PR #857 on `fix/856-lazy-matrix-page`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/App.tsx`
- `web_app/src/components/LazyRouteBoundary.tsx`
- `web_app/src/utils/lazyRouteMessage.test.ts`
- `web_app/src/utils/lazyRouteMessage.ts`
- `web_docs/docs/guides/data-explorer-matrix-map.md`

## CI Status

See the PR checks on `e401b45b0df6`.

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
