---
pr: 1306
branch: feat/1293-said-people-positions
title: "feat(stories): people and position on \"What was said\", decisions on the topic vs in passing"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 3640f1c39c7f0e15bf0a36bc6e5bbf7300c18ddb
verdict: approve
---

# PR Review: feat(stories): people and position on "What was said", decisions on the topic vs in passing

## Summary

Automated review (#648) for PR #1306 on `feat/1293-said-people-positions`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `api/routes/topic_relevance.py`
- `api/routes/topics.py`
- `tests/test_api_data_center_decisions.py`
- `tests/test_api_topic_said.py`
- `tests/test_api_topics.py`
- `web_app/src/api/dataCenters.ts`
- `web_app/src/api/topics.ts`
- `web_app/src/components/stance/MeetingVideoModal.tsx`
- `web_app/src/components/stance/TopicRecordCards.tsx`
- `web_app/src/components/stance/UnitMatrixChart.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/styles/topic-story.css`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/saidCards.test.ts`
- `web_app/src/utils/saidCards.ts`
- `web_app/src/utils/stanceGame.ts`
- `web_app/src/utils/topicPolicy.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `3640f1c39c7f`.

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
