---
pr: 1215
branch: feat/1200-topic-positions-headline
title: "feat(stories): each topic's public position in its own words, and the place's conclusion in the headline"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 417dde02cb6f73b16b6e8c1fc76d96b0493323e0
verdict: approve
---

# PR Review: feat(stories): each topic's public position in its own words, and the place's conclusion in the headline

## Summary

Automated review (#648) for PR #1215 on `feat/1200-topic-positions-headline`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topic_caption_facts.py`
- `api/routes/topics.py`
- `tests/test_api_topic_caption_facts.py`
- `tests/test_api_topic_state_map.py`
- `web_app/src/api/topics.ts`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/home/storyColors.ts`
- `web_app/src/components/stance/UnitMatrixChart.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/storyCaption.ts`
- `web_app/src/utils/storyCaptionPosition.test.ts`
- `web_app/src/utils/topicPositions.test.ts`
- `web_app/src/utils/topicPositions.ts`
- `web_app/src/utils/topicStance.test.ts`
- `web_app/src/utils/topicStance.ts`
- `web_app/src/utils/unitMatrix.test.ts`
- `web_app/src/utils/unitMatrix.ts`
- `web_docs/docs/development/story-captions.md`
- `web_docs/docs/development/topic-meeting-lean.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `417dde02cb6f`.

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
