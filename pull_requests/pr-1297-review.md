---
pr: 1297
branch: feat/1285-place-scope-zoom
title: "feat(stories): story scope steps up to a level with 5+ meetings, the home map zooms to the place, and the header has a one-click National"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: e8460e9a7f8361cc7bfa80a969fd18b01d15f9e5
verdict: approve
---

# PR Review: feat(stories): story scope steps up to a level with 5+ meetings, the home map zooms to the place, and the header has a one-click National

## Summary

Automated review (#648) for PR #1297 on `feat/1285-place-scope-zoom`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/e2e/place-scope.check.mjs`
- `web_app/src/components/SiteHeader.tsx`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/home/HomeTopicStrip.tsx`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/stance/ScopeBar.tsx`
- `web_app/src/hooks/useStoryScope.ts`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/pages/HomeV9.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/headerPlace.test.ts`
- `web_app/src/utils/headerPlace.ts`
- `web_app/src/utils/resolveStoryScope.test.ts`
- `web_app/src/utils/resolveStoryScope.ts`
- `web_app/src/utils/storyCaption.test.ts`
- `web_app/src/utils/storyCaption.ts`
- `web_docs/docs/development/story-captions.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `e8460e9a7f83`.

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
