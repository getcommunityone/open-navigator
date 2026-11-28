---
pr: 1404
branch: feat/1400-cross-page-box-particles
title: "feat(stories): unified vizjb12 box charts and cross-page particle flights (#1400)"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 4da50a4b5d8ba1b9801615907add5eac57e35f10
verdict: approve
---

# PR Review: feat(stories): unified vizjb12 box charts and cross-page particle flights (#1400)

## Summary

Automated review (#648) for PR #1404 on `feat/1400-cross-page-box-particles`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/e2e/map-taps.check.mjs`
- `web_app/src/App.tsx`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeOutcomesScroller.tsx`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/stance/BoxFlightProvider.tsx`
- `web_app/src/components/stance/BoxWaffleChart.tsx`
- `web_app/src/components/stance/ChartPanel.tsx`
- `web_app/src/components/stance/FitDisplay.tsx`
- `web_app/src/components/stance/MapDrill.tsx`
- `web_app/src/components/stance/NonprofitsPanel.tsx`
- `web_app/src/components/stance/OutcomesChain.tsx`
- `web_app/src/components/stance/PositionsBlock.tsx`
- `web_app/src/components/stance/StoryClose.tsx`
- `web_app/src/components/stance/StoryCountyMap.tsx`
- `web_app/src/components/stance/StoryDotMap.tsx`
- `web_app/src/components/stance/StoryNextButton.tsx`
- `web_app/src/components/stance/TopicPositionsBreakdown.tsx`
- `web_app/src/components/stance/UnitMatrixChart.tsx`
- `web_app/src/components/stance/boxFlightBridge.ts`
- `web_app/src/components/stance/storyCharts.css`
- `web_app/src/components/stance/useStoryBoxTransition.ts`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/boxFlight.test.ts`
- `web_app/src/utils/boxFlight.ts`
- `web_app/src/utils/waffleGrid.test.ts`
- `web_app/src/utils/waffleGrid.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `4da50a4b5d8b`.

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
