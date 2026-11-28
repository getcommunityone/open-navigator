---
pr: 1421
branch: feat/boxesall
title: "feat(stories): boxes on every story screen, Coming up date strip, no empty quote cards"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 47c2d9f7241f206dcd3286b3d046d0404aba19b4
verdict: approve
---

# PR Review: feat(stories): boxes on every story screen, Coming up date strip, no empty quote cards

## Summary

Automated review (#648) for PR #1421 on `feat/boxesall`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/e2e/box-coverage.check.mjs`
- `web_app/src/components/stance/KpiDrill.tsx`
- `web_app/src/components/stance/NonprofitsPanel.tsx`
- `web_app/src/components/stance/ScreenBoxes.test.tsx`
- `web_app/src/components/stance/ScreenBoxes.tsx`
- `web_app/src/components/stance/SidesBlock.tsx`
- `web_app/src/components/stance/StoryScreenFrame.tsx`
- `web_app/src/components/stance/StoryScreenView.tsx`
- `web_app/src/components/stance/StoryVoteScreens.tsx`
- `web_app/src/components/stance/TopicRecordCards.tsx`
- `web_app/src/components/stance/UpcomingBoxes.tsx`
- `web_app/src/components/stance/UpcomingPanel.tsx`
- `web_app/src/components/stance/storyCharts.css`
- `web_app/src/lib/highlight.tsx`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/screenBoxes.ts`

## CI Status

See the PR checks on `47c2d9f7241f`.

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
