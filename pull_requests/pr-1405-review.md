---
pr: 1405
branch: feat/1391-speaker-stance-jev
title: "feat(stance): Jev side and heat per public speaker for curated and major topics"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 8ccbd85edb810c26455199c45d220c126bd8d176
verdict: approve
---

# PR Review: feat(stance): Jev side and heat per public speaker for curated and major topics

## Summary

Automated review (#648) for PR #1405 on `feat/1391-speaker-stance-jev`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topic_caption_facts.py`
- `dbt_project/contracts/meeting_speaker_position.odcs.yaml`
- `dbt_project/contracts/meeting_speaker_topic_side.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/dbt_project.yml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/intermediate/int_meeting_speaker__heat.sql`
- `dbt_project/models/marts/_schema_meeting_comment.yml`
- `dbt_project/models/marts/_schema_meeting_speaker_topic_side.yml`
- `dbt_project/models/marts/meeting_speaker_position.sql`
- `dbt_project/models/marts/meeting_speaker_topic_side.sql`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/models/staging/stg_jev__speaker_topic_stance.sql`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `packages/llm/src/llm/typesafe/gold/speaker_stance_gold.json`
- `packages/llm/src/llm/typesafe/gold/speaker_stance_gold_results.json`
- `packages/llm/src/llm/typesafe/speaker_stance.py`
- `packages/llm/src/llm/typesafe/speaker_stance_gold.py`
- `packages/llm/src/llm/typesafe/speaker_stance_priority.py`
- `packages/llm/tests/test_speaker_stance.py`
- `tests/test_api_topic_caption_facts.py`
- `web_app/src/api/topics.ts`
- `web_app/src/components/stance/PositionsSummary.tsx`
- `web_app/src/utils/stanceEvidence.ts`
- `web_app/src/utils/stanceEvidenceClassifier.test.ts`
- `web_app/src/utils/topicPositions.test.ts`
- `web_app/src/utils/topicPositions.ts`
- `web_docs/docs/development/speaker-stance-classifier.md`

## CI Status

See the PR checks on `8ccbd85edb81`.

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
