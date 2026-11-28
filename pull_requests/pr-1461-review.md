---
pr: 1461
branch: feat/1437-topic-place-ranking
title: "feat(rankings): topic_place_ranking mart and /api/rankings (#1437)"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 1233a47a97e28c0569ce4d4c36f9110b6b45f768
verdict: approve
---

# PR Review: feat(rankings): topic_place_ranking mart and /api/rankings (#1437)

## Summary

Automated review (#648) for PR #1461 on `feat/1437-topic-place-ranking`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/main.py`
- `api/routes/rankings.py`
- `dbt_project/dbt_project.yml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_topic_place_ranking.yml`
- `dbt_project/models/marts/topic_place_ranking.sql`
- `tests/test_api_rankings.py`
- `tests/test_topic_place_ranking_dbt.py`
- `web_docs/docs/development/topic-place-rankings.md`

## CI Status

See the PR checks on `1233a47a97e2`.

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
