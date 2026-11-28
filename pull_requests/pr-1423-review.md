---
pr: 1423
branch: fix/1409-chart-legends
title: "fix(web): every map and chart gets a takeaway title and colour legend (ChartFrame)"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 78045c09f2a46890e0fad94b44e9ad7c26e845d9
verdict: approve
---

# PR Review: fix(web): every map and chart gets a takeaway title and colour legend (ChartFrame)

## Summary

Automated review (#648) for PR #1423 on `fix/1409-chart-legends`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `pull_requests/pr-1423-review.md`
- `web_app/e2e/chart-legends.check.mjs`
- `web_app/src/components/chart/ChartFrame.test.tsx`
- `web_app/src/components/chart/ChartFrame.tsx`
- `web_app/src/components/chart/toneColors.ts`
- `web_app/src/components/chart/useInsightYears.ts`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/stance/BoxWaffleChart.tsx`
- `web_app/src/components/stance/ChartPanel.tsx`
- `web_app/src/components/stance/DumbbellChart.tsx`
- `web_app/src/components/stance/DumbbellRows.tsx`
- `web_app/src/components/stance/DumbbellRowsLinks.test.tsx`
- `web_app/src/components/stance/FitDisplay.tsx`
- `web_app/src/components/stance/LegislationMap.tsx`
- `web_app/src/components/stance/LocalActionsTracker.tsx`
- `web_app/src/components/stance/SitesTimelinePanel.tsx`
- `web_app/src/components/stance/StoryCountyMap.tsx`
- `web_app/src/components/stance/StoryDotMap.tsx`
- `web_app/src/components/stance/TimelineChart.tsx`
- `web_app/src/components/stance/TopicCountyMap.tsx`
- `web_app/src/components/stance/UnitMatrixChart.tsx`
- `web_app/src/pages/BrowseAllTopics.tsx`
- `web_app/src/pages/CensusDrilldownMapPage.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/chartInsight.test.ts`
- `web_app/src/utils/chartInsight.ts`
- `web_docs/docs/development/chart-title-and-legend-rule.md`

## CI Status

See the PR checks on `78045c09f2a4`.

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
