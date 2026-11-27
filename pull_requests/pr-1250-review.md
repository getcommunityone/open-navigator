---
pr: 1250
branch: fix/1229-map-taps-check
title: "fix(stories): story map cards open and close on a tap, never on hover (#1229)"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: b7039d2da65376a9479807ed7b97a406ea69da0e
verdict: approve
---

# PR Review: fix(stories): story map cards open and close on a tap, never on hover (#1229)

## Summary

Automated review (#648) for PR #1250 on `fix/1229-map-taps-check`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/e2e/map-taps.check.mjs`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/stance/StoryCountyMap.tsx`
- `web_app/src/components/stance/StoryDotMap.tsx`
- `web_app/src/hooks/useMapKeyboard.test.tsx`
- `web_app/src/hooks/useMapKeyboard.tsx`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `b7039d2da653`.

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
