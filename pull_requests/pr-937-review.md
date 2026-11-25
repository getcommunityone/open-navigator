---
pr: 937
branch: fix/936-stale-deploy-reload
title: "fix(web_app): reload once when a deploy removed a lazy page's chunk, and stop telling visitors to run npm install"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: github-actions
head_sha: 3e6263d3056a1b66adf9665f5d9b144c23f77743
verdict: approve
---

# PR Review: fix(web_app): reload once when a deploy removed a lazy page's chunk, and stop telling visitors to run npm install

## Summary

Automated review (#648) for PR #937 on `fix/936-stale-deploy-reload`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/components/LazyRouteBoundary.tsx`
- `web_app/src/main.tsx`
- `web_app/src/utils/lazyRouteMessage.test.ts`
- `web_app/src/utils/lazyRouteMessage.ts`
- `web_app/src/utils/staleDeploy.test.ts`
- `web_app/src/utils/staleDeploy.ts`
- `web_docs/docs/guides/data-explorer-matrix-map.md`

## CI Status

See the PR checks on `3e6263d3056a`.

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
