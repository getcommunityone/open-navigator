---
pr: 980
branch: feat/958-dc-facility-inventories
title: "feat(data-centers): import the open data center inventories"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: github-actions
head_sha: 1fef1e0d267a1d11663cf13579a5fc575a5021aa
verdict: approve
---

# PR Review: feat(data-centers): import the open data center inventories

## Summary

Automated review (#648) for PR #980 on `feat/958-dc-facility-inventories`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `dbt_project/contracts/data_center_site.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/dbt_project.yml`
- `dbt_project/macros/ensure_data_center_inventory_tables.sql`
- `dbt_project/models/intermediate/_schema_int_data_center_facility_registry.yml`
- `dbt_project/models/intermediate/int_data_center_facility_registry__site.sql`
- `dbt_project/models/intermediate/int_data_center_project__base.sql`
- `dbt_project/models/intermediate/int_data_center_project__figure.sql`
- `dbt_project/models/intermediate/int_data_center_site__jurisdiction.sql`
- `dbt_project/models/marts/_schema_data_center_inventory.yml`
- `dbt_project/models/marts/_schema_data_center_site.yml`
- `dbt_project/models/marts/_schema_decision_context.yml`
- `dbt_project/models/marts/data_center_agenda_item.sql`
- `dbt_project/models/marts/data_center_meeting_mention.sql`
- `dbt_project/models/marts/data_center_project_company.sql`
- `dbt_project/models/marts/data_center_public_record.sql`
- `dbt_project/models/marts/data_center_site.sql`
- `dbt_project/models/marts/data_center_site_source.sql`
- `dbt_project/models/marts/decision_company_mention.sql`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/models/staging/data_centers/_schema_stg_data_center_inventories.yml`
- `dbt_project/models/staging/data_centers/stg_data_center_facility_registry.sql`
- `dbt_project/models/staging/data_centers/stg_data_center_public_record.sql`
- `dbt_project/models/staging/data_centers/stg_data_center_state_count.sql`
- `packages/ingestion/src/ingestion/data_centers/facility_inventories.py`
- `packages/ingestion/tests/test_facility_inventories.py`
- `tests/test_api_data_center_sites.py`
- `web_app/src/lib/api.types.ts`
- `web_app/src/lib/dataCenterJobs.test.ts`
- `web_app/src/lib/dataCenterJobs.ts`
- `web_app/src/pages/DataCenters.tsx`
- `web_app/src/utils/dataStory.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/stanceGame.ts`
- `web_docs/docs/development/data-center-sites.md`
- `web_docs/docs/development/data-center-source-review.md`

## CI Status

See the PR checks on `1fef1e0d267a`.

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
