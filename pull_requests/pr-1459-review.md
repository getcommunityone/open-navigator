---
pr: 1459
branch: feat/1442-governing-body
title: "feat(dbt): governing_body and meeting_body from meeting titles, platform bodies and rosters"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 039bd1859ea7b3ade60e0a37d3d341f032ff82ac
verdict: approve
---

# PR Review: feat(dbt): governing_body and meeting_body from meeting titles, platform bodies and rosters

## Summary

Automated review (#648) for PR #1459 on `feat/1442-governing-body`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/dbt_project.yml`
- `dbt_project/macros/governing_body_title.sql`
- `dbt_project/models/intermediate/int_meeting_body__matched.sql`
- `dbt_project/models/marts/_schema_governing_body.yml`
- `dbt_project/models/marts/governing_body.sql`
- `dbt_project/models/marts/meeting_body.sql`
- `dbt_project/seeds/governing_body_pattern.csv`
- `dbt_project/seeds/governing_body_title_example.csv`
- `dbt_project/seeds/schema.yml`
- `dbt_project/tests/assert_governing_body_title_examples.sql`
- `packages/ingestion/src/ingestion/governance/__init__.py`
- `packages/ingestion/src/ingestion/governance/body_titles.py`
- `packages/ingestion/tests/test_governing_body_titles.py`
- `web_docs/docs/development/governing-bodies.md`

## CI Status

See the PR checks on `039bd1859ea7`.

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
