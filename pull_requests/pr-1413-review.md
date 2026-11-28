---
pr: 1413
branch: feat/1393-usaspending-awards
title: "feat(finance): USAspending federal awards + /api/benchmark (#1393)"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 3bb8e9646583b84423dba11550c7707d678e6a2e
verdict: approve
---

# PR Review: feat(finance): USAspending federal awards + /api/benchmark (#1393)

## Summary

Automated review (#648) for PR #1413 on `feat/1393-usaspending-awards`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/main.py`
- `api/routes/benchmark.py`
- `dbt_project/contracts/federal_award.odcs.yaml`
- `dbt_project/contracts/jurisdiction_federal_funding.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/intermediate/int_usaspending_recipient__jurisdiction_match.sql`
- `dbt_project/models/marts/_schema_federal_award.yml`
- `dbt_project/models/marts/federal_award.sql`
- `dbt_project/models/marts/jurisdiction_federal_funding.sql`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/models/staging/stg_usaspending__award.sql`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `packages/ingestion/src/ingestion/pgutil.py`
- `packages/ingestion/src/ingestion/usaspending/__init__.py`
- `packages/ingestion/src/ingestion/usaspending/client.py`
- `packages/ingestion/src/ingestion/usaspending/load_awards.py`
- `tests/test_api_benchmark.py`
- `web_docs/docs/data-sources/citations.md`
- `web_docs/docs/development/usaspending-federal-awards-decision.md`
- `web_docs/docs/legal/data-provider-terms.md`

## CI Status

See the PR checks on `3bb8e9646583`.

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
