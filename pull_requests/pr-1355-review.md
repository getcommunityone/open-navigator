---
pr: 1355
branch: feat/1349-topic-county-map
title: "feat(stories): topic stories draw the county and town map at state scope"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 2b6a42c0ec9c3ce6dfdffe7a8e62282ecaba157d
verdict: approve
---

# PR Review: feat(stories): topic stories draw the county and town map at state scope

## Summary

Automated review (#648) for PR #1355 on `feat/1349-topic-county-map`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topics.py`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_topic_place_meeting.yml`
- `dbt_project/models/marts/topic_place_meeting.sql`
- `tests/test_api_topic_places.py`
- `web_app/e2e/topic-county-map.shots.mjs`
- `web_app/src/api/topics.ts`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/stance/StoryCountyMap.tsx`
- `web_app/src/components/stance/TopicCountyMap.test.tsx`
- `web_app/src/components/stance/TopicCountyMap.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/overviewLead.test.ts`
- `web_app/src/utils/overviewLead.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `2b6a42c0ec9c`.

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
