---
pr: 1363
branch: feat/1361-all-major-meeting-topics
title: "feat(topics): show all major meeting topics on Browse all topics"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 56c9b1db91b4b863431d98afc62fd0be9ee8c851
verdict: approve
---

# PR Review: feat(topics): show all major meeting topics on Browse all topics

## Summary

Automated review (#648) for PR #1363 on `feat/1361-all-major-meeting-topics`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topic_yoy.py`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/contracts/topic_meeting_year.odcs.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_topic_meeting_year.yml`
- `dbt_project/models/marts/topic_meeting_year.sql`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `tests/test_api_topic_yoy.py`
- `web_app/src/api/topicsYoy.ts`
- `web_app/src/lib/api.types.ts`
- `web_app/src/pages/BrowseAllTopics.tsx`
- `web_app/src/utils/topicsYoy.test.ts`
- `web_app/src/utils/topicsYoy.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `56c9b1db91b4`.

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
