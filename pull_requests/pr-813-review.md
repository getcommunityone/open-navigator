---
pr: 813
branch: feat/807-public-comment-stance
title: "feat(llm): extract public-comment stance in the full and light analysis prompts"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 7b6dd404dd71499929fa471891ccc3448d454548
verdict: approve
---

# PR Review: feat(llm): extract public-comment stance in the full and light analysis prompts

## Summary

Automated review (#648) for PR #813 on `feat/807-public-comment-stance`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/macros/public_stance_bucket.sql`
- `dbt_project/models/bronze/bronze_public_participation_from_ai.sql`
- `dbt_project/models/marts/_schema_public_comment.yml`
- `dbt_project/models/marts/decision_public_stance.sql`
- `dbt_project/models/marts/public_comment.sql`
- `packages/llm/src/llm/gemini/part1_schema.py`
- `packages/llm/tests/test_part1_public_participation.py`
- `prompts/policy_analysis_lite.md`
- `prompts/policy_analysis_part_1.md`
- `web_docs/docs/development/meeting-sentiment-design.md`

## CI Status

See the PR checks on `7b6dd404dd71`.

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
