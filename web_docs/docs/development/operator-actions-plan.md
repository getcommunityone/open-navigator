---
sidebar_position: 50
title: Operator actions — implementation plan
description: Plan for #712 admin operator-actions page + templates.
---

# Operator actions Implementation Plan

**Goal:** Admin `/admin/operator-actions` lists open pipeline blockers with
standard templates; Batch Jobs links when any are open; Discover writes
`action_required.json`.

**Spec:** [operator-actions](./operator-actions.md) · Issue [#712](https://github.com/getcommunityone/open-navigator/issues/712).

## Tasks

1. JSON writer + code mapping in `discover_action_log`
2. `api/batch_jobs/operator_actions.py` + routes
3. Admin page + Batch Jobs banner
4. Docs playbooks (this tree)
