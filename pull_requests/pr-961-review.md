---
pr: 961
branch: feat/955-dc-hearing-leads
title: "feat(data-centers): show upcoming data center hearings only once the government's own page confirms them"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: github-actions
head_sha: b814046f2aa355e4206c5f0ed264e1788063d1dd
verdict: approve
---

# PR Review: feat(data-centers): show upcoming data center hearings only once the government's own page confirms them

## Summary

Automated review (#648) for PR #961 on `feat/955-dc-hearing-leads`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `dbt_project/contracts/data_center_hearing.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_data_center_hearing.yml`
- `dbt_project/models/marts/data_center_hearing.sql`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/seeds/data_center_hearing_lead.csv`
- `dbt_project/seeds/schema.yml`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `packages/ingestion/src/ingestion/data_centers/fetch_hearing_sources.py`
- `packages/ingestion/tests/test_fetch_hearing_sources.py`
- `tests/test_api_data_center_hearings.py`
- `web_app/src/api/dataCenters.ts`
- `web_app/src/pages/DataCenters.tsx`
- `web_docs/docs/development/data-center-hearings.md`

## CI Status

See the PR checks on `b814046f2aa3`.

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
