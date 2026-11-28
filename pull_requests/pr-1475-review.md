---
pr: 1475
branch: feat/1445-bodies-api
title: "feat(api): jurisdiction bodies and body detail endpoints"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 8c89caab829ed4a0ddee849a18bd09c4a3c09f5d
verdict: approve
---

# PR Review: feat(api): jurisdiction bodies and body detail endpoints

## Summary

Automated review (#648) for PR #1475 on `feat/1445-bodies-api`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/main.py`
- `api/routes/governing_bodies.py`
- `dbt_project/contracts/body_membership.odcs.yaml`
- `dbt_project/contracts/body_recent_speaker.odcs.yaml`
- `dbt_project/contracts/governing_body.odcs.yaml`
- `dbt_project/contracts/meeting_body.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `tests/test_api_governing_bodies.py`

## CI Status

See the PR checks on `8c89caab829e`.

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
