---
pr: 844
branch: fix/843-load-builds-staging-view
title: "fix(batch-jobs): build the staging view before the Load tab promotes events"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: c6690a81d4386b593e37330c888ee0118b68b375
verdict: approve-with-nits
---

# PR Review: fix(batch-jobs): build the staging view before the Load tab promotes events

## Summary

The Load tab failed at "Promote events" because that step reads the dbt view `staging.stg_youtube__event`, which no
Load step built. The PR adds a first step, `dbt-staging`, that builds that one view, gives it the same counts and
drill-down as the other dbt step, and makes the run header add both dbt steps together. Tested at the unit level.
The step itself was not run: the session cannot reach the warehouse or run dbt.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

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
- Fabricated data / personal / destructive: clean. The step only creates a view in the local warehouse.

## Strengths

- A test ties the step's selector to the relation the promotion SQL names, so the two cannot drift apart.
- The header sum is a pure function with its own test, and returns null rather than zero when nothing was measured.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- Not run end to end. If `int_jurisdictions`, the view's upstream model, is also missing locally, the new step
  fails (visibly, with dbt's message). The owner should run one Load and confirm the first step passes.

### 🔵 Nit (Minor)

- A dbt run of one view still fires the `publish_public_serving` on-run-end hook. It is idempotent, but it adds a few
  seconds and runs twice per Load.
- The step label and description are duplicated in the orchestrator and the API, as the existing steps are.

## Verdict

**approve-with-nits**
