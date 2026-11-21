---
pr: 620
branch: chore/271-served-contracts
title: "chore(dbt): enforce contracts on eight served marts"
author: jcbowyer
reviewed_at: 2026-11-21
reviewer: coordinator
verdict: approve
---

# PR Review: chore(dbt): enforce contracts on eight served marts

## Summary

This PR enables `contract: {enforced: true}` and typed column definitions for eight served marts (`event_*` and jurisdiction models), switches marts default `on_schema_change` to `append_new_columns`, and regenerates ODCS YAML plus `data-contracts.md` documentation. The change aligns warehouse schema with the ODCS pipeline (#271) and leaves `meeting_document` / `civic_jurisdiction` for #619. Required CI checks are green; mandatory scans found no secrets, fabricated served data, or destructive cache changes. **Approve** for merge.

## Scope of Change
- Files changed: 35 (+2366 / -606)
- Areas touched: dbt_project, web_docs
- Commits: 1912b27a chore(dbt): enforce contracts on eight served marts
- Range reviewed: merge-base..1912b27a

## CI Status
| Check | Status |
|---|---|
| Frontend Build | pass |
| Documentation Build | pass |
| Backend Tests | pass |
| API Types | pass |
| PR conventions | pass |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean
- Fabricated data (api/web_app served paths): clean (no api/web_app changes)
- Personal data: clean
- Destructive/bulky data: clean

## Strengths
- Centralizes contract enforcement on high-traffic served marts with PKs declared in schema YAML.
- ODCS regeneration keeps generated contracts in sync with dbt metadata.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
Spot-check `dbt build` on laptop warehouse remains in the PR test plan unchecked.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Closes #271; branch matches |
| dbt for transformations | Yes | Schema-only SQL config tweaks |
| Keys in public | Yes | PKs in schema YAML |

## Test Coverage
PR cites `dbt parse`, ODCS `--check`, and `test_odcs.py` (32 passed).

## Verdict
**Approve** — schema contract enforcement with green CI and clean scans.