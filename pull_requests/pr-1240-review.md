---
pr: 1240
branch: fix/1230-map-quotes-stance-meetings
title: "fix(stories): map cards quote real meetings where the public took a side"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 74857c9e074bb4377a61f24b2bcd573ea9e51d84
verdict: approve
---

# PR Review: fix(stories): map cards quote real meetings where the public took a side

## Summary

Automated review (#648) for PR #1240 on `fix/1230-map-quotes-stance-meetings`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `api/routes/topics.py`
- `dbt_project/contracts/meeting_video_kind.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_meeting_video_kind.yml`
- `dbt_project/models/marts/meeting_video_kind.sql`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/models/staging/stg_jev__video_meeting_kind.sql`
- `tests/test_api_story_map_quotes.py`
- `web_app/src/api/dataCenters.ts`
- `web_app/src/api/topics.ts`
- `web_app/src/components/home/HomeDataStories.tsx`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/components/home/StoryStatesMap.tsx`
- `web_app/src/components/stance/QuoteCard.css`
- `web_app/src/components/stance/QuoteCard.tsx`
- `web_app/src/components/stance/StoryScreenView.tsx`
- `web_app/src/lib/api.types.ts`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/topicPositions.test.ts`
- `web_app/src/utils/topicPositions.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `74857c9e074b`.

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
