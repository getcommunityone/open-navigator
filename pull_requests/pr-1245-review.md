---
pr: 1245
branch: feat/1231-speaker-names-self-intros
title: "feat(stories): speaker names on meeting quotes from public-comment self-introductions"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: d95f38caa0d9d16ad42e61e1993e4debe404f7d1
verdict: approve
---

# PR Review: feat(stories): speaker names on meeting quotes from public-comment self-introductions

## Summary

Automated review (#648) for PR #1245 on `feat/1231-speaker-names-self-intros`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `api/routes/topics.py`
- `dbt_project/contracts/meeting_passage_speaker.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_meeting_speaker_intro.yml`
- `dbt_project/models/marts/meeting_passage_speaker.sql`
- `dbt_project/models/marts/meeting_speaker_intro.sql`
- `dbt_project/models/staging/_schema_stg_meeting_speaker_intro.yml`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/models/staging/stg_bronze_meeting_speaker_intro.sql`
- `packages/ingestion/src/ingestion/youtube/speaker_intros.py`
- `packages/ingestion/tests/test_speaker_intros.py`
- `pull_requests/pr-1245-review.md`
- `tests/test_api_passage_speakers.py`
- `web_app/src/api/topics.ts`
- `web_app/src/components/home/HomeTopicStoryCard.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_docs/docs/development/data-contracts.md`
- `web_docs/docs/development/speaker-names-from-self-introductions.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `d95f38caa0d9`.

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
