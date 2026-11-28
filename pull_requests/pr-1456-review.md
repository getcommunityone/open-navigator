---
pr: 1456
branch: feat/1394-hud-cdbg
title: "feat(hud): CDBG activities, allocation marts and benchmark metrics (#1394)"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 4e244681e8f0b77bf35bf89f3d3de146c107b648
verdict: approve
---

# PR Review: feat(hud): CDBG activities, allocation marts and benchmark metrics (#1394)

## Summary

Automated review (#648) for PR #1456 on `feat/1394-hud-cdbg`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/benchmark.py`
- `dbt_project/contracts/cdbg_activity_summary.odcs.yaml`
- `dbt_project/contracts/cdbg_allocation.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/intermediate/int_hud_cdbg_grantee__jurisdiction_match.sql`
- `dbt_project/models/marts/_schema_cdbg.yml`
- `dbt_project/models/marts/cdbg_activity.sql`
- `dbt_project/models/marts/cdbg_activity_summary.sql`
- `dbt_project/models/marts/cdbg_allocation.sql`
- `dbt_project/models/staging/_staging.yml`
- `dbt_project/models/staging/stg_hud_cdbg__activity.sql`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `packages/ingestion/src/ingestion/hud/load_cdbg.py`
- `packages/ingestion/src/ingestion/hud/zip_county.py`
- `tests/test_api_benchmark.py`
- `web_docs/docs/data-sources/citations.md`
- `web_docs/docs/development/hud-cdbg-decision.md`
- `web_docs/docs/legal/data-provider-terms.md`

## CI Status

See the PR checks on `4e244681e8f0`.

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
