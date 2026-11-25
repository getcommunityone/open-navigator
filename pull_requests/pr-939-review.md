---
pr: 939
branch: fix/935-mdm-person-nonblocking-rebuild
title: "fix(dbt): rebuild mdm_person without locking readers or losing its trigram index"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: github-actions
head_sha: 18963eab3fb2e74a223e34dbf472a80eba1d4001
verdict: approve
---

# PR Review: fix(dbt): rebuild mdm_person without locking readers or losing its trigram index

## Summary

Automated review (#648) for PR #939 on `fix/935-mdm-person-nonblocking-rebuild`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/macros/ensure_search_indexes.sql`
- `dbt_project/macros/swap_guard.sql`
- `dbt_project/models/marts/mdm_person.sql`
- `web_docs/docs/development/non-blocking-table-rebuilds.md`

## CI Status

See the PR checks on `18963eab3fb2`.

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
