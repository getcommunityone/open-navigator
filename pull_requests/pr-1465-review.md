---
pr: 1465
branch: feat/1443-body-membership
title: "feat(dbt): body_membership with roles from officials, Legistar office records, rosters and OpenStates"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 638dc98c19def6d36009713c73c4a07d15d15547
verdict: approve
---

# PR Review: feat(dbt): body_membership with roles from officials, Legistar office records, rosters and OpenStates

## Summary

Automated review (#648) for PR #1465 on `feat/1443-body-membership`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/dbt_project.yml`
- `dbt_project/macros/body_membership.sql`
- `dbt_project/models/intermediate/int_body_member__candidate.sql`
- `dbt_project/models/marts/_schema_body_membership.yml`
- `dbt_project/models/marts/body_membership.sql`
- `dbt_project/models/marts/governing_body.sql`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/models/staging/stg_legistar__office_record.sql`
- `dbt_project/models/staging/stg_openstates__chamber_member.sql`
- `dbt_project/seeds/body_role_rule.csv`
- `dbt_project/seeds/schema.yml`
- `packages/ingestion/src/ingestion/governance/roles.py`
- `packages/ingestion/tests/test_governing_body_roles.py`
- `packages/scrapers/src/scrapers/platforms/legistar_people.py`
- `packages/scrapers/tests/test_legistar_people.py`
- `web_docs/docs/development/governing-bodies.md`

## CI Status

See the PR checks on `638dc98c19de`.

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
