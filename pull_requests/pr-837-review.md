---
pr: 837
branch: fix/836-load-dbt-selects-participation
title: "fix(batch-jobs): rebuild every analysis bronze model in the Load tab's dbt step"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: b70b600efbd6a0a9e2ec98f6d27eff747bf612bc
verdict: approve
---

# PR Review: fix(batch-jobs): rebuild every analysis bronze model in the Load tab's dbt step

## Summary

Automated review (#648) for PR #837 on `fix/836-load-dbt-selects-participation`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `packages/hosting/src/hosting/deploy/run_deployment.py`
- `tests/test_load_tab_steps_796.py`
- `web_docs/docs/development/batch-load-tab.md`

## CI Status

See the PR checks on `b70b600efbd6`.

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
