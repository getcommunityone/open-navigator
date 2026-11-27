---
pr: 1199
branch: fix/1192-story-nav-simplify
title: "fix(stories): one exit, one progress indicator, no floating Next on the cover; dumbbell on the Overview"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 41a834ac7cf353edbb9292d64ffbbe96c59714d4
verdict: approve
---

# PR Review: fix(stories): one exit, one progress indicator, no floating Next on the cover; dumbbell on the Overview

## Summary

Automated review (#648) for PR #1199 on `fix/1192-story-nav-simplify`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/e2e/story-nav.check.mjs`
- `web_app/src/components/stance/ChartPanel.tsx`
- `web_app/src/components/stance/DumbbellChart.tsx`
- `web_app/src/components/stance/ProgressPips.tsx`
- `web_app/src/components/stance/StoryProgress.tsx`
- `web_app/src/components/stance/StoryScreenView.tsx`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/storyCaption.test.ts`
- `web_app/src/utils/storyCaption.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `41a834ac7cf3`.

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
