---
pr: 1433
branch: feat/1395-aspep-payroll
title: "feat(census): ASPEP public payroll marts and benchmark metrics (#1395)"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 987b682e1ce9ee6e4c3c13a9a8caaad6d327bfeb
verdict: approve
---

# PR Review: feat(census): ASPEP public payroll marts and benchmark metrics (#1395)

## Summary

Automated review (#648) for PR #1433 on `feat/1395-aspep-payroll`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/benchmark.py`
- `dbt_project/contracts/jurisdiction_public_payroll.odcs.yaml`
- `dbt_project/contracts/jurisdiction_public_payroll_latest.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/dbt_project.yml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/intermediate/int_aspep_unit__jurisdiction_match.sql`
- `dbt_project/models/marts/_schema_jurisdiction_public_payroll.yml`
- `dbt_project/models/marts/jurisdiction_public_payroll.sql`
- `dbt_project/models/marts/jurisdiction_public_payroll_latest.sql`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/models/staging/stg_aspep__employment.sql`
- `dbt_project/models/staging/stg_aspep__unit.sql`
- `dbt_project/seeds/aspep_function_code.csv`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `packages/ingestion/src/ingestion/census/load_aspep.py`
- `tests/test_api_benchmark.py`
- `web_docs/docs/data-sources/citations.md`
- `web_docs/docs/development/aspep-public-payroll-decision.md`
- `web_docs/docs/legal/data-provider-terms.md`

## CI Status

See the PR checks on `987b682e1ce9`.

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
