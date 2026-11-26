---
pr: 1166
branch: feat/1126-topic-lean
title: "feat(llm): Jev reads how the public and officials leaned on each topic, into topic_meeting_lean"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: f3951f4700e28cd4d87018a30cfc372f3fe91702
verdict: approve
---

# PR Review: feat(llm): Jev reads how the public and officials leaned on each topic, into topic_meeting_lean

## Summary

Automated review (#648) for PR #1166 on `feat/1126-topic-lean`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/contracts/topic_meeting_lean.odcs.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_topic_meeting_lean.yml`
- `dbt_project/models/marts/topic_meeting_lean.sql`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/models/staging/stg_jev__transcript_topic_lean.sql`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `packages/llm/src/llm/typesafe/screen_transcripts.py`
- `packages/llm/src/llm/typesafe/topic_lean.py`
- `packages/llm/tests/test_topic_lean.py`
- `web_docs/docs/development/topic-meeting-lean.md`

## CI Status

See the PR checks on `f3951f4700e2`.

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
