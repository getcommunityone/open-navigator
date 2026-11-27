---
pr: 1329
branch: feat/1290-fit-display-to-data
title: "feat(stories): votes read by which way they went, speaker sources reconciled, topic control in the title, screens fit a phone"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 92d5b69ed82ef973f7a5abb4d79fe0dcce99626a
verdict: approve
---

# PR Review: feat(stories): votes read by which way they went, speaker sources reconciled, topic control in the title, screens fit a phone

## Summary

Automated review (#648) for PR #1329 on `feat/1290-fit-display-to-data`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topic_caption_facts.py`
- `dbt_project/contracts/data_center_decision.odcs.yaml`
- `dbt_project/models/marts/_schema_data_center_decision.yml`
- `dbt_project/models/marts/data_center_decision.sql`
- `pull_requests/pr-1329-review.md`
- `tests/test_api_topic_caption_facts.py`
- `web_app/e2e/story-fit.check.mjs`
- `web_app/src/api/topics.ts`
- `web_app/src/components/stance/PositionsBlock.tsx`
- `web_app/src/components/stance/StoryScreenFrame.tsx`
- `web_app/src/components/stance/TopicPositionsBreakdown.tsx`
- `web_app/src/components/stance/useScreenFit.ts`
- `web_app/src/components/stance/useStoryScreens.ts`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/dataStory.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/stanceEvidence.ts`
- `web_app/src/utils/stanceHeadline.test.ts`
- `web_app/src/utils/storyCaption.ts`
- `web_app/src/utils/storyCaptionPosition.test.ts`
- `web_app/src/utils/storyHeadlineTopic.test.ts`
- `web_app/src/utils/topicPositions.ts`
- `web_docs/docs/development/story-captions.md`
- `web_docs/docs/development/story-vote-direction-and-phone-fit.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `92d5b69ed82e`.

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
