---
pr: 1244
branch: feat/1224-topic-story-screens
title: "feat(stories): topic stories go screen by screen like the Data Center Story, with swipe"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 013cc20d810184f67e4fadfaecd7e0bdfafca138
verdict: approve
---

# PR Review: feat(stories): topic stories go screen by screen like the Data Center Story, with swipe

## Summary

Automated review (#648) for PR #1244 on `feat/1224-topic-story-screens`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/e2e/story-nav.check.mjs`
- `web_app/src/components/stance/StoryScreenFrame.tsx`
- `web_app/src/components/stance/StoryScreenView.tsx`
- `web_app/src/components/stance/TopicPositionsBreakdown.tsx`
- `web_app/src/components/stance/useStoryScreens.ts`
- `web_app/src/hooks/useSwipeNav.test.ts`
- `web_app/src/hooks/useSwipeNav.ts`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/styles/topic-story.css`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/topicStoryScreens.test.ts`
- `web_app/src/utils/topicStoryScreens.ts`
- `web_docs/docs/development/topic-story-screens.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `013cc20d8101`.

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
