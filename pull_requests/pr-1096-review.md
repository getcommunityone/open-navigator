---
pr: 1096
branch: feat/1089-business-marts
title: "feat(dbt): business and business_mention marts from meetings and decisions"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 7aedb7179fd2160f9e48f8fc8df3be4249f7c401
verdict: approve
---

# PR Review: feat(dbt): business and business_mention marts from meetings and decisions

## Summary

Automated review (#648) for PR #1096 on `feat/1089-business-marts`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/contracts/business.odcs.yaml`
- `dbt_project/contracts/business_mention.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/intermediate/int_business_mention__source.sql`
- `dbt_project/models/marts/_schema_business.yml`
- `dbt_project/models/marts/business.sql`
- `dbt_project/models/marts/business_mention.sql`
- `dbt_project/tests/assert_business_has_a_mention.sql`
- `dbt_project/tests/assert_business_mention_quote_is_short_and_not_marked.sql`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `packages/hosting/tests/test_neon_sync_business_tables.py`

## CI Status

See the PR checks on `7aedb7179fd2`.

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
