---
pr: 1247
branch: feat/1233-dc-comment-segments
title: "feat(data-centers): segment public comments once per meeting and flag concerns, companies, AI and places (phase 1)"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: ea930c17593a1d29973866a56d2f13917667d728
verdict: request-changes
---

# PR Review: feat(data-centers): segment public comments once per meeting and flag concerns, companies, AI and places (phase 1)

## Summary

Automated review (#648) for PR #1247 on `feat/1233-dc-comment-segments`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/app.py`
- `api/main.py`
- `api/routes/data_center_comments.py`
- `dbt_project/dbt_project.yml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/intermediate/int_meeting_comment__flags.sql`
- `dbt_project/models/marts/_schema_meeting_comment.yml`
- `dbt_project/models/marts/data_center_comment.sql`
- `dbt_project/models/marts/data_center_comment_place.sql`
- `dbt_project/models/marts/meeting_comment.sql`
- `dbt_project/models/marts/segmented_meeting.sql`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/models/staging/meetings/_schema_stg_meeting_comment_segment.yml`
- `dbt_project/models/staging/meetings/stg_meeting_comment_segment.sql`
- `dbt_project/seeds/comment_concern_terms.csv`
- `dbt_project/seeds/comment_entity_terms.csv`
- `dbt_project/seeds/comment_place_patterns.csv`
- `dbt_project/seeds/comment_role_terms.csv`
- `dbt_project/seeds/schema.yml`
- `packages/ingestion/src/ingestion/meetings/comment_segments.py`
- `packages/ingestion/tests/test_meeting_comment_segments.py`
- `tests/test_api_data_center_comment_metrics.py`
- `tests/test_comment_keyword_seeds.py`
- `web_app/src/api/dataCenters.ts`
- `web_app/src/components/stance/CommentMetricsBlock.test.ts`
- `web_app/src/components/stance/CommentMetricsBlock.tsx`
- `web_app/src/components/stance/PositionsBlock.tsx`
- `web_app/src/lib/api.types.ts`
- `web_docs/docs/development/data-center-comment-level.md`

## CI Status

See the PR checks on `ea930c17593a`.

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
