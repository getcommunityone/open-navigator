---
pr: 1298
branch: fix/1289-story-display-fit
title: "fix(stories): displays fit the amount of data; stance headline agrees with recorded votes"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: e5bf12e1243419745182e4a96722b2def3bc062d
verdict: approve
---

# PR Review: fix(stories): displays fit the amount of data; stance headline agrees with recorded votes

## Summary

Automated review (#648) for PR #1298 on `fix/1289-story-display-fit`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topic_caption_facts.py`
- `pull_requests/assets/1289/after-concerns.png`
- `pull_requests/assets/1289/after-decisions.png`
- `pull_requests/assets/1289/after-national-top.png`
- `pull_requests/assets/1289/after-projects.png`
- `pull_requests/assets/1289/after-top.png`
- `pull_requests/assets/1289/after-voices.png`
- `pull_requests/assets/1289/before-concerns.png`
- `pull_requests/assets/1289/before-decisions.png`
- `pull_requests/assets/1289/before-projects.png`
- `pull_requests/assets/1289/before-top.png`
- `pull_requests/assets/1289/before-voices.png`
- `tests/test_api_topic_caption_facts.py`
- `web_app/src/api/topics.ts`
- `web_app/src/components/stance/ChartPanel.tsx`
- `web_app/src/components/stance/FitDisplay.tsx`
- `web_app/src/components/stance/PositionsBlock.tsx`
- `web_app/src/components/stance/StoryScreenView.tsx`
- `web_app/src/components/stance/TimelineChart.tsx`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/dataStory.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/displayFit.test.ts`
- `web_app/src/utils/displayFit.ts`
- `web_app/src/utils/stanceEvidence.ts`
- `web_app/src/utils/stanceGame.ts`
- `web_app/src/utils/stanceHeadline.test.ts`
- `web_app/src/utils/storyCaption.ts`
- `web_docs/docs/development/story-captions.md`
- `web_docs/docs/development/story-display-fit.md`

## CI Status

See the PR checks on `e5bf12e12434`.

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
