---
pr: 1077
branch: feat/1073-company-foundation-grants
title: "feat(money): companies linked to the nonprofits their foundations fund (990 grants), Funds and Funded by on organization pages"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 1e37acd7fcc8a6a4d93bce56eb2874bb139b418d
verdict: approve
---

# PR Review: feat(money): companies linked to the nonprofits their foundations fund (990 grants), Funds and Funded by on organization pages

## Summary

Automated review (#648) for PR #1077 on `feat/1073-company-foundation-grants`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/organizations.py`
- `dbt_project/contracts/company_grant.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_company_grant.yml`
- `dbt_project/models/marts/company_grant.sql`
- `dbt_project/seeds/company_foundation.csv`
- `dbt_project/seeds/schema.yml`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `pull_requests/pr-1077-review.md`
- `tests/test_api_organization_funding.py`
- `web_app/src/components/OrganizationFunding.tsx`
- `web_app/src/pages/OrganizationPage.tsx`
- `web_docs/docs/development/company-funding.md`

## CI Status

See the PR checks on `1e37acd7fcc8`.

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
