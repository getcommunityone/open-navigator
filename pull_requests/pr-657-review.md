---
pr: 657
branch: fix/656-stage-last-activity-time
title: "fix(batch-jobs): show stage last-activity time while running"
author: jcbowyer
reviewed_at: 2026-11-21
reviewer: AI agent (Cursor), read-only; this is a written review, not a GitHub approval
verdict: approve
---

# PR Review: fix(batch-jobs): show stage last-activity time while running

## Summary
One-cell UI fix on the batch job status pipeline table. **Last activity** always shows the compact `last_at` stamp (`8m ago` / `—`); running stages keep the green pulse and green-tint the time instead of replacing it with `running…`. Matches the header, which already showed the real stamp. Approve.

## Scope of Change
- Files changed: 1 (`web_app/src/pages/BatchJobStatusPage.tsx`)
- Areas touched: frontend batch-jobs status page
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| Required checks | pending at review write; re-check before merge |

## Secrets, PHI and Claims Scan
- Secrets: clean
- Fabricated data in a served path: none
- Personal data: none
- Destructive data changes: none

## Strengths
- Small, targeted change; no API / `last_at` calculation changes
- Running state remains visible via the pulse + color

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix
None.

### 🔵 Nits
None.

## Verdict
Ready to merge once required CI is green.
