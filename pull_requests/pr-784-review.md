---
pr: 784
branch: fix/783-restore-declared-fks
title: "fix(dbt): restore declared foreign keys after rebuild; add ballot_measures primary key"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: github-actions
head_sha: 0280f628d2af2b09e0ad999ce5196c3c3009871e
verdict: approve
---

# PR Review: fix(dbt): restore declared foreign keys after rebuild; add ballot_measures primary key

## Summary

Automated review (#648) for PR #784 on `fix/783-restore-declared-fks`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/dbt_project.yml`
- `dbt_project/macros/ensure_declared_foreign_keys.sql`
- `dbt_project/macros/ensure_gold_primary_keys.sql`
- `tests/test_ensure_declared_foreign_keys_783.py`
- `web_docs/docs/development/dbt-foreign-keys-cascade-drop.md`

## CI Status

See the PR checks on `0280f628d2af`.

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
