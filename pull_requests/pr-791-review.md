---
pr: 791
branch: fix/786-orphan-fk-audit
title: "feat(dbt): read-only audit of foreign-key candidates that have orphan rows"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: github-actions
head_sha: 249abf0d6cad6866cb897086325629974a52769a
verdict: approve
---

# PR Review: feat(dbt): read-only audit of foreign-key candidates that have orphan rows

## Summary

Automated review (#648) for PR #791 on `fix/786-orphan-fk-audit`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/macros/audit_orphan_foreign_keys.sql`
- `tests/test_audit_orphan_foreign_keys_786.py`
- `web_docs/docs/development/dbt-foreign-keys-cascade-drop.md`

## CI Status

See the PR checks on `249abf0d6cad`.

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
