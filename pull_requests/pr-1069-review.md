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

## Agent review

- Story #1068 under epic #1061; contract change (first_seen_on/last_seen_on, term_source in PK) noted on the issue with a date.
- Scans: no secrets; personal data limited to officials' public terms from government pages and OpenStates; 'died' only from the city's own memorial page; no fabricated dates (snapshot dates are labelled observation dates, never term dates).
- Keys: PK + FK to person_government, contract enforced, accepted_values on end_reason/term_source.
- Checks: local dbt seed/snapshot/build passed; ODCS current; dbt parse clean after rebuilding the seed schema merge.

No blocking findings.
