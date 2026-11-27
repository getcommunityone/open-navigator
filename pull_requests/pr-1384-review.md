---
pr: 1384
branch: fix/1380-phone-overview-map-size
title: "fix(web): phone Overview map fills the screen, compact header and stat row"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 34c34bcaf88150f28310a162fb937c5c25dbdc47
verdict: approve
---

# PR Review: fix(web): phone Overview map fills the screen, compact header and stat row

## Summary

Automated review (#648) for PR #1384 on `fix/1380-phone-overview-map-size`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/e2e/phone-overview-map.check.mjs`
- `web_app/e2e/story-header.check.mjs`
- `web_app/src/components/stance/ScopeNote.tsx`
- `web_app/src/components/stance/StoryScreenFrame.tsx`
- `web_app/src/components/stance/StoryScreenView.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/resolveStoryScope.ts`
- `web_app/src/utils/storySummary.test.ts`
- `web_app/src/utils/storySummary.ts`

## CI Status

See the PR checks on `34c34bcaf881`.

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
