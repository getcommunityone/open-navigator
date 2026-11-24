---
pr: 795
branch: fix/794-pk-macro-comment
title: "fix(dbt): move a Jinja comment out of the primary key list so dbt compiles"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 4fc207fc22317fe882dd162d1525f56ce4160efb
verdict: approve
---

# PR Review: fix(dbt): move a Jinja comment out of the primary key list so dbt compiles

## Summary

Automated review (#648) for PR #795 on `fix/794-pk-macro-comment`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/macros/ensure_gold_primary_keys.sql`
- `tests/test_dbt_macros_parse_794.py`

## CI Status

See the PR checks on `4fc207fc2231`.

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
