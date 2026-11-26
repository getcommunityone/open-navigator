---
pr: 1020
branch: feat/1019-dc-payroll-jobs
title: "feat(data-centers): actual data center payroll jobs (BLS QCEW 518210) on the jobs screen, with job-site citations"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: cf8ab96fbb35111072fe187933689437100b0ef5
verdict: approve
---

# PR Review: feat(data-centers): actual data center payroll jobs (BLS QCEW 518210) on the jobs screen, with job-site citations

## Summary

Automated review (#648) for PR #1020 on `feat/1019-dc-payroll-jobs`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `dbt_project/contracts/data_center_employment.odcs.yaml`
- `dbt_project/contracts/data_center_job_source.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/bronze/bronze_bls_qcew_industry.sql`
- `dbt_project/models/marts/_schema_data_center_jobs.yml`
- `dbt_project/models/marts/data_center_employment.sql`
- `dbt_project/models/marts/data_center_job_source.sql`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/models/staging/stg_bls__qcew_industry.sql`
- `dbt_project/seeds/data_center_job_sources.csv`
- `dbt_project/seeds/schema.yml`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `packages/ingestion/src/ingestion/bls/qcew.py`
- `tests/test_api_data_center_job_claims.py`
- `web_app/src/components/stance/PayrollJobsPanel.tsx`
- `web_app/src/components/stance/StoryScreenView.tsx`
- `web_app/src/lib/api.types.ts`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/dataStory.ts`
- `web_docs/docs/development/data-center-jobs.md`
- `web_docs/docs/development/data-center-payroll-jobs.md`

## CI Status

See the PR checks on `cf8ab96fbb35`.

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
