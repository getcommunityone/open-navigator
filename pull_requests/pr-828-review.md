---
pr: 828
branch: feat/827-load-promote-step
title: "feat(batch-jobs): promote videos to events as the first step of a Load run"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: d1314a018522b9f30c97e052fc9381e47096e702
verdict: request-changes
---

# PR Review: feat(batch-jobs): promote videos to events as the first step of a Load run

## Summary

Automated review (#648) for PR #828 on `feat/827-load-promote-step`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/deployments.py`
- `packages/hosting/src/hosting/deploy/run_deployment.py`
- `packages/ingestion/src/ingestion/youtube/promote_to_c1_event.py`
- `tests/test_deployments_groups_796.py`
- `tests/test_load_tab_counts_823.py`
- `tests/test_load_tab_steps_796.py`
- `web_app/src/components/DeploymentPanel.tsx`
- `web_app/src/components/StepResultPanel.tsx`
- `web_docs/docs/development/batch-load-tab.md`

## CI Status

See the PR checks on `d1314a018522`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: **findings**
- Fabricated data / personal / destructive: see findings

## Strengths

- (blocked on scan findings below)

## Findings

### 🔴 Blocking (Critical)

- Possible secret or credential pattern matched: `(?i)postgres(ql)?://[^:\s]+:[^@\s]+@…`

### 🟡 Should fix (Important)

None from automated heuristics.

### 🔵 Nit (Minor)

None from automated heuristics.

## Verdict

**request-changes**
