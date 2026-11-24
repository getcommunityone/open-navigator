---
pr: 921
branch: feat/915-story-opens-with-question
title: "feat(web_app): open the Data Center Story on its question, record the vote before and after, and make phones kinetic"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 40f94d270b216f7fcf80d5e6517cc9befd3d2d6f
verdict: approve
---

# PR Review: feat(web_app): open the Data Center Story on its question, record the vote before and after, and make phones kinetic

## Summary

Automated review (#648) for PR #921 on `feat/915-story-opens-with-question`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/stance.py`
- `api/stance_packs/data_centers.json`
- `tests/test_stance_api.py`
- `web_app/src/api/stance.ts`
- `web_app/src/components/stance/ChoiceBars.tsx`
- `web_app/src/components/stance/Cover.tsx`
- `web_app/src/components/stance/EndPanel.tsx`
- `web_app/src/components/stance/FloatingNext.tsx`
- `web_app/src/components/stance/KineticText.tsx`
- `web_app/src/components/stance/ProgressPips.tsx`
- `web_app/src/components/stance/RoundPanel.tsx`
- `web_app/src/components/stance/ScopeBar.tsx`
- `web_app/src/components/stance/ScreenNav.tsx`
- `web_app/src/components/stance/SoundToggle.tsx`
- `web_app/src/components/stance/StoryScreenView.tsx`
- `web_app/src/components/stance/StoryVoteScreens.tsx`
- `web_app/src/components/stance/useActs.ts`
- `web_app/src/pages/Challenge.tsx`
- `web_app/src/pages/DataStories.tsx`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/dataStory.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/floatingNext.test.ts`
- `web_app/src/utils/floatingNext.ts`
- `web_app/src/utils/storyQuestion.test.ts`
- `web_app/src/utils/storyQuestion.ts`
- `web_docs/docs/development/where-you-stand-game-design.md`
- `web_docs/docs/guides/data-center-challenge.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `40f94d270b21`.

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
