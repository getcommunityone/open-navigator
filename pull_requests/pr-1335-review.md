---
pr: 1335
branch: feat/1314-meeting-outcomes
title: "feat(stories): what happened next \u2014 link meetings to state bills and show the chain from meeting to outcome"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: d741bd95d42358d8bbb88b7ffd8f279de34c81dd
verdict: request-changes
---

# PR Review: feat(stories): what happened next — link meetings to state bills and show the chain from meeting to outcome

## Summary

Automated review (#648) for PR #1335 on `feat/1314-meeting-outcomes`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/main.py`
- `api/routes/topic_outcomes.py`
- `dbt_project/contracts/meeting_bill_link.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_meeting_bill_link.yml`
- `dbt_project/models/marts/meeting_bill_link.sql`
- `tests/test_api_topic_outcomes.py`
- `web_app/src/api/topicOutcomes.ts`
- `web_app/src/components/home/HomeOutcomesScroller.tsx`
- `web_app/src/components/stance/OutcomesChain.css`
- `web_app/src/components/stance/OutcomesChain.tsx`
- `web_app/src/hooks/useTopicOutcomes.ts`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/dataStory.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/topicOutcomes.test.ts`
- `web_app/src/utils/topicOutcomes.ts`
- `web_app/src/utils/topicStoryScreens.test.ts`
- `web_app/src/utils/topicStoryScreens.ts`
- `web_docs/docs/development/meeting-bill-links.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `d741bd95d423`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: **findings**
- Fabricated data / personal / destructive: see findings

## Strengths

- (blocked on scan findings below)

## Findings

### 🔴 Blocking (Critical)

- Possible secret or credential pattern matched: `(?i)postgres(ql)?://[^:\s]+:[^@\s]+@…`

### 🟡 Should fix (Important)

None from automated heuristics.

### 🔵 Nit (Minor)

None from automated heuristics.

## Verdict

**request-changes**
