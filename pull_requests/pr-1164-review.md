---
pr: 1164
branch: fix/1134-hero-speaker-basis
title: "fix(stories): one title for hero, story header and Overview; hero basis leads with the meeting reading"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 0603ebe038f9d4ff25ae67a2d57b7e6104447554
verdict: approve
---

# PR Review: fix(stories): one title for hero, story header and Overview; hero basis leads with the meeting reading

## Summary

Automated review (#648) for PR #1164 on `fix/1134-hero-speaker-basis`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `api/routes/topic_caption_facts.py`
- `tests/test_api_data_center_positions.py`
- `tests/test_api_topic_caption_facts.py`
- `web_app/src/api/dataCenters.ts`
- `web_app/src/api/topics.ts`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/stance/StoryScreenView.tsx`
- `web_app/src/components/stance/StoryVoteScreens.tsx`
- `web_app/src/components/stance/useStoryConclusion.ts`
- `web_app/src/lib/api.types.ts`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/clauses.ts`
- `web_app/src/utils/dataStory.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/heroPoints.test.ts`
- `web_app/src/utils/heroPoints.ts`
- `web_app/src/utils/storyCaption.test.ts`
- `web_app/src/utils/storyCaption.ts`
- `web_app/src/utils/storyConclusion.test.ts`
- `web_app/src/utils/storyTitle.test.ts`
- `web_docs/docs/development/data-center-meeting-lean.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `0603ebe038f9`.

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
