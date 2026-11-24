---
pr: 876
branch: fix/875-load-dbt-profiles-dir
title: "fix(batch-jobs): run the Load tab's dbt steps with the project's profiles directory"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 03917a1404ef6a04080f4f1d8bbdfaa144a8bbab
verdict: approve
---

# PR Review: fix(batch-jobs): run the Load tab's dbt steps with the project's profiles directory

## Summary

Automated review (#648) for PR #876 on `fix/875-load-dbt-profiles-dir`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `packages/hosting/src/hosting/deploy/run_deployment.py`
- `tests/test_load_tab_steps_796.py`
- `web_docs/docs/development/batch-load-tab.md`

## CI Status

See the PR checks on `03917a1404ef`.

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
