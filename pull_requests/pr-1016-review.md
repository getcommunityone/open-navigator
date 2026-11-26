---
pr: 1016
branch: feat/1015-str-companies
title: "feat(data): short-term rental platforms as organizations, linked to meetings and decisions; organization page"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 709c5a165a73d6fb2ca5066d190575ad8b610428
verdict: approve
---

# PR Review: feat(data): short-term rental platforms as organizations, linked to meetings and decisions; organization page

## Summary

Automated review (#648) for PR #1016 on `feat/1015-str-companies`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/main.py`
- `api/routes/organizations.py`
- `api/routes/search_postgres.py`
- `api/routes/short_term_rentals.py`
- `dbt_project/contracts/mdm_organization_short_term_rental.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/contracts/short_term_rental_company_mention.odcs.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/intermediate/int_organizations__unioned.sql`
- `dbt_project/models/marts/_schema_short_term_rental.yml`
- `dbt_project/models/marts/mdm_organization.sql`
- `dbt_project/models/marts/mdm_organization_short_term_rental.sql`
- `dbt_project/models/marts/short_term_rental_company_mention.sql`
- `dbt_project/models/staging/stg_short_term_rental_companies__org.sql`
- `dbt_project/seeds/schema.yml`
- `dbt_project/seeds/short_term_rental_companies.csv`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `pull_requests/pr-1016-review.md`
- `web_app/src/App.tsx`
- `web_app/src/pages/OrganizationPage.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_docs/docs/development/short-term-rental-companies.md`

## CI Status

See the PR checks on `709c5a165a73`.

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
