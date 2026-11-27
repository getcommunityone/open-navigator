---
pr: 1180
branch: fix/1179-find-your-town
title: "fix(web): drop the four hard-coded launch cities; home gets a Find your town prompt"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 570435feb01394cf705e40a7ffdd3fa123aef05f
verdict: approve
---

# PR Review: fix(web): drop the four hard-coded launch cities; home gets a Find your town prompt

## Summary

Automated review (#648) for PR #1180 on `fix/1179-find-your-town`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/components/AddressLookup.tsx`
- `web_app/src/lib/launchCounties.ts`
- `web_app/src/lib/launchCoverage.ts`
- `web_app/src/pages/HomeV9.tsx`
- `web_app/src/pages/UnifiedSearch.tsx`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `570435feb013`.

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
