---
pr: 1471
branch: feat/1444-officials-heard
title: "feat(dbt): officials heard most recently per body from roster-matched chair calls"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 6c4728b2218e1bd3ea746f163316d9e52b25a892
verdict: approve
---

# PR Review: feat(dbt): officials heard most recently per body from roster-matched chair calls

## Summary

Automated review (#648) for PR #1471 on `feat/1444-officials-heard`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/models/marts/_schema_body_recent_speaker.yml`
- `dbt_project/models/marts/body_recent_speaker.sql`
- `dbt_project/models/staging/_staging.yml`
- `packages/ingestion/src/ingestion/youtube/official_mentions.py`
- `packages/ingestion/tests/test_official_mentions.py`
- `web_docs/docs/development/governing-bodies.md`

## CI Status

See the PR checks on `6c4728b2218e`.

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
