---
pr: 1462
branch: feat/1396-opioid-settlement
title: "feat(opioid): settlement spending pilot (Michigan), meeting topic and benchmark metric (#1396)"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 3ce0ab63937727d33849e9ebbc4a07b136fc76cc
verdict: approve
---

# PR Review: feat(opioid): settlement spending pilot (Michigan), meeting topic and benchmark metric (#1396)

## Summary

Automated review (#648) for PR #1462 on `feat/1396-opioid-settlement`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/benchmark.py`
- `dbt_project/contracts/opioid_settlement_spending.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_opioid_settlement_spending.yml`
- `dbt_project/models/marts/opioid_settlement_spending.sql`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/models/staging/stg_opioid_settlement__spending.sql`
- `dbt_project/seeds/curated_topics.csv`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `packages/ingestion/src/ingestion/opioid_settlement/__init__.py`
- `packages/ingestion/src/ingestion/opioid_settlement/michigan.py`
- `tests/test_api_benchmark.py`
- `web_docs/docs/data-sources/citations.md`
- `web_docs/docs/development/opioid-settlement-decision.md`
- `web_docs/docs/legal/data-provider-terms.md`

## CI Status

See the PR checks on `3ce0ab639377`.

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
