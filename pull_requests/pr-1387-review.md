---
pr: 1387
branch: feat/1386-mixed-comments
title: "feat(data-centers): speaker turns, stance shapes, attribution provenance and heat for mixed comments"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: a73048b9752679e7fbcc911dc2190ac16a29ecf5
verdict: approve-with-nits
---

# PR Review: feat(data-centers): speaker turns, stance shapes, attribution provenance and heat for mixed comments

## Summary

Automated review (#648) for PR #1387 on `feat/1386-mixed-comments`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_center_comments.py`
- `api/routes/data_center_drill.py`
- `api/routes/data_centers.py`
- `api/routes/decision_people.py`
- `api/routes/topics.py`
- `dbt_project/contracts/data_center_comment.odcs.yaml`
- `dbt_project/contracts/meeting_comment.odcs.yaml`
- `dbt_project/contracts/meeting_passage_speaker.odcs.yaml`
- `dbt_project/contracts/meeting_speaker_position.odcs.yaml`
- `dbt_project/contracts/meeting_speaker_turn.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/dbt_project.yml`
- `dbt_project/macros/attribution_tier.sql`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/macros/stance_shape_sql.sql`
- `dbt_project/models/intermediate/int_meeting_comment__flags.sql`
- `dbt_project/models/intermediate/int_meeting_comment__stance_shape.sql`
- `dbt_project/models/intermediate/int_meeting_comment__turns.sql`
- `dbt_project/models/intermediate/int_meeting_speaker__heat.sql`
- `dbt_project/models/intermediate/int_meeting_speaker__stance_shape.sql`
- `dbt_project/models/marts/_schema_meeting_comment.yml`
- `dbt_project/models/marts/_schema_meeting_speaker_intro.yml`
- `dbt_project/models/marts/data_center_comment.sql`
- `dbt_project/models/marts/meeting_comment.sql`
- `dbt_project/models/marts/meeting_passage_speaker.sql`
- `dbt_project/models/marts/meeting_speaker_position.sql`
- `dbt_project/models/marts/meeting_speaker_turn.sql`
- `dbt_project/seeds/comment_heat_terms.csv`
- `dbt_project/seeds/comment_stance_shape_terms.csv`
- `dbt_project/seeds/schema.yml`
- `dbt_project/seeds/speaker_attribution_rules.csv`
- `packages/ingestion/src/ingestion/meetings/comment_segments.py`
- `packages/ingestion/tests/test_comment_stance_shape_terms.py`
- `packages/ingestion/tests/test_meeting_comment_segments.py`
- `tests/test_api_data_center_comment_metrics.py`
- `tests/test_api_data_center_drill.py`
- `tests/test_api_decision_people.py`
- `web_app/src/components/stance/CommentMetricsBlock.test.ts`
- `web_app/src/components/stance/CommentMetricsBlock.tsx`
- `web_app/src/components/stance/HeatFlames.test.tsx`
- …and 9 more

## CI Status

See the PR checks on `a73048b97526`.

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

**approve-with-nits**
