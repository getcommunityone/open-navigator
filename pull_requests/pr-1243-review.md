---
pr: 1243
branch: fix/1234-story-start-titles-swipe
title: "fix(stories): Start skips the cover, short conclusion titles, swipe and phone Back"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 4aabe0d0d793835af13b60fd34cced31e2f4ea4d
verdict: approve
---

# PR Review: fix(stories): Start skips the cover, short conclusion titles, swipe and phone Back

## Summary

Automated review (#648) for PR #1243 on `fix/1234-story-start-titles-swipe`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/e2e/story-flow.check.mjs`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeStoryTitle.tsx`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/stance/StoryProgress.tsx`
- `web_app/src/hooks/useSwipeNav.test.ts`
- `web_app/src/hooks/useSwipeNav.ts`
- `web_app/src/pages/DataStories.tsx`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/captionPlace.test.ts`
- `web_app/src/utils/captionPlace.ts`
- `web_app/src/utils/dataStory.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/heroPoints.test.ts`
- `web_app/src/utils/heroPoints.ts`
- `web_app/src/utils/storyCaption.test.ts`
- `web_app/src/utils/storyCaption.ts`
- `web_app/src/utils/storyCaptionPosition.test.ts`
- `web_app/src/utils/storyConclusion.test.ts`
- `web_app/src/utils/storyNav.ts`
- `web_app/src/utils/topicPositions.ts`
- `web_docs/docs/development/story-captions.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `4aabe0d0d793`.

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
