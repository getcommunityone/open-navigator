---
pr: 1283
branch: feat/1277-map-hover-video-card
title: "feat(stories): story maps drill on tap with no card on phones; desktop hover card autoplays the recording beside the map"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: df0d9a4002f8c6b5cf48cb2ef3e37fc6c1c4dd12
verdict: approve
---

# PR Review: feat(stories): story maps drill on tap with no card on phones; desktop hover card autoplays the recording beside the map

## Summary

Automated review (#648) for PR #1283 on `feat/1277-map-hover-video-card`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/e2e/map-taps.check.mjs`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/home/storyColors.test.ts`
- `web_app/src/components/home/storyColors.ts`
- `web_app/src/components/stance/QuoteCard.css`
- `web_app/src/components/stance/QuoteCard.test.tsx`
- `web_app/src/components/stance/QuoteCard.tsx`
- `web_app/src/components/stance/StoryClose.tsx`
- `web_app/src/components/stance/StoryCountyMap.tsx`
- `web_app/src/components/stance/StoryDotMap.tsx`
- `web_app/src/hooks/useMapKeyboard.test.tsx`
- `web_app/src/hooks/useMapKeyboard.tsx`
- `web_app/src/lib/youtubeEmbed.test.ts`
- `web_app/src/lib/youtubeEmbed.ts`
- `web_app/src/pages/HomeV9.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/topicPositions.test.ts`
- `web_app/src/utils/topicPositions.ts`
- `web_app/src/utils/topicStance.test.ts`
- `web_app/src/utils/touchOnly.test.ts`
- `web_app/src/utils/touchOnly.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `df0d9a4002f8`.

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
