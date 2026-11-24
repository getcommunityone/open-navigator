---
pr: 876
branch: fix/875-load-dbt-profiles-dir
title: "fix(batch-jobs): run the Load tab's dbt steps with the project's profiles directory"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 03917a1404ef6a04080f4f1d8bbdfaa144a8bbab
verdict: approve-with-nits
---

# PR Review: fix(batch-jobs): run the Load tab's dbt steps with the project's profiles directory

## Summary

The Load tab started dbt from the repository root with no profiles directory, so dbt looked in `~/.dbt` and not in
`dbt_project/`, where `scripts/dbt.sh` points it. The PR sets `DBT_PROFILES_DIR` for the steps when the project has
a `profiles.yml`, keeps an explicit setting, and writes the directory used into each dbt step's log. Small and
unit-tested. Whether it explains the owner's failing Load runs is not confirmed.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `packages/hosting/src/hosting/deploy/run_deployment.py`
- `tests/test_load_tab_steps_796.py`
- `web_docs/docs/development/batch-load-tab.md`

## CI Status

See the PR checks on `03917a1404ef`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. It narrows which database a Load run can write to, towards the local one the owner already uses by hand.

## Strengths

- It mirrors `scripts/dbt.sh` exactly, so the tab and the terminal now agree.
- The log line makes the next failure diagnosable from the tab.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- Not run against a real dbt project. The owner's next Load is the test; its dbt step logs should start with
  the `dbt_project` path.

### 🔵 Nit (Minor)

- If `~/.dbt/profiles.yml` was what made earlier Load runs work on some machine, this changes which profile they
  use there. That is the intended direction, but worth knowing.

## Verdict

**approve-with-nits**
