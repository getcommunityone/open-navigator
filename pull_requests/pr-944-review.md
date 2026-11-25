---
pr: 944
branch: feat/933-dc-uncontested-decisions
title: "feat(data-centers): show the decisions meetings took on data center items, debated or passed without debate"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: github-actions
head_sha: 9d1d035e1ebfbc24632e2551487c4a98da0c4501
verdict: approve
---

# PR Review: feat(data-centers): show the decisions meetings took on data center items, debated or passed without debate

## Summary

Automated review (#648) for PR #944 on `feat/933-dc-uncontested-decisions`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `dbt_project/contracts/data_center_decision.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_data_center_decision.yml`
- `dbt_project/models/marts/data_center_decision.sql`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `tests/test_api_data_center_decisions.py`
- `web_app/src/api/dataCenters.ts`
- `web_app/src/api/stance.ts`
- `web_app/src/utils/dataStory.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/stanceGame.test.ts`
- `web_app/src/utils/stanceGame.ts`
- `web_docs/docs/development/data-center-who-spoke-up.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `9d1d035e1ebf`.

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
