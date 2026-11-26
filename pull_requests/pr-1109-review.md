---
pr: 1109
branch: feat/1102-story-progress-next
title: "feat(stories): story progress and a clear Next story at the end (top bar, numbered dots, next-story card, phone bottom bar)"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 461567b73ac87b54ba8b4cfd4613f09fc064f409
verdict: approve
---

# PR Review: feat(stories): story progress and a clear Next story at the end (top bar, numbered dots, next-story card, phone bottom bar)

## Summary

Automated review (#648) for PR #1109 on `feat/1102-story-progress-next`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/components/stance/ProgressRail.tsx`
- `web_app/src/components/stance/StoryProgress.tsx`
- `web_app/src/components/stance/useActs.ts`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/storyNav.test.ts`
- `web_app/src/utils/storyNav.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `461567b73ac8`.

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
