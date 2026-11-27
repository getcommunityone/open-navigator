---
pr: 1365
branch: feat/1345-topic-organization
title: "feat(topics): topic_organization mart and API tie nonprofits to curated topics"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 223d212e388c5a40c462c5062a87a93360f1d999
verdict: approve
---

# PR Review: feat(topics): topic_organization mart and API tie nonprofits to curated topics

## Summary

Automated review (#648) for PR #1365 on `feat/1345-topic-organization`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/main.py`
- `api/routes/topic_organizations.py`
- `dbt_project/dbt_project.yml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/intermediate/int_topic_organization__named_in_meeting.sql`
- `dbt_project/models/intermediate/int_topic_organization__rule_match.sql`
- `dbt_project/models/marts/_schema_topic_organization.yml`
- `dbt_project/models/marts/topic_organization.sql`
- `dbt_project/seeds/schema.yml`
- `dbt_project/seeds/topic_organization_rule.csv`
- `tests/test_api_topic_organizations.py`
- `web_docs/docs/development/topic-organizations.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `223d212e388c`.

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
