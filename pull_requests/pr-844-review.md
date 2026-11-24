---
pr: 844
branch: fix/843-load-builds-staging-view
title: "fix(batch-jobs): build the staging view before the Load tab promotes events"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: c6690a81d4386b593e37330c888ee0118b68b375
verdict: approve
---

# PR Review: fix(batch-jobs): build the staging view before the Load tab promotes events

## Summary

Automated review (#648) for PR #844 on `fix/843-load-builds-staging-view`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/deployments.py`
- `packages/hosting/src/hosting/deploy/run_deployment.py`
- `tests/test_deployments_groups_796.py`
- `tests/test_load_tab_counts_823.py`
- `tests/test_load_tab_steps_796.py`
- `web_app/src/components/DeploymentPanel.tsx`
- `web_app/src/utils/stepCounts.test.ts`
- `web_app/src/utils/stepCounts.ts`
- `web_docs/docs/development/batch-load-tab.md`

## CI Status

See the PR checks on `c6690a81d438`.

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
