---
pr: 1069
branch: feat/1068-official-terms
title: "feat(officials): office terms history: who held which seat, when, and why they left"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 21d2dbeb8c11716718d514c856db47b2fef56dc6
verdict: approve
---

# PR Review: feat(officials): office terms history: who held which seat, when, and why they left

## Summary

Automated review (#648) for PR #1069 on `feat/1068-official-terms`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/contracts/person_government_term.odcs.yaml`
- `dbt_project/contracts/products/open-navigator-public-api.odps.yaml`
- `dbt_project/macros/publish_public_serving.sql`
- `dbt_project/models/marts/_schema_person_government_term.yml`
- `dbt_project/models/marts/person_government_term.sql`
- `dbt_project/seeds/official_term.csv`
- `dbt_project/seeds/schema.yml`
- `dbt_project/snapshots/officials_roster_snapshot.sql`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `web_docs/docs/development/official-contacts.md`

## CI Status

See the PR checks on `21d2dbeb8c11`.

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
