---
pr: 1196
branch: fix/1194-publish-recorded-meeting-year
title: "fix(data): publish recorded_meeting_year to production Neon"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: coordinator (read-only pass over a two-file diff)
verdict: approve
---

# PR Review: fix(data): publish recorded_meeting_year to production Neon

## Summary
Adds `recorded_meeting_year` to the Neon serving allow-list so full syncs copy it, and documents the one-off publish
already done on the owner's go-ahead. Verdict: approve.

## Scans
- Secrets: clean. Fabricated data: clean (copies an existing dbt mart). Personal data: none (counts per jurisdiction
  and year). Destructive data changes: none — adds a table to the copy list; the sync swaps it in via a staging table.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None. Size checked: ~1 MB; Neon prod 363 → 364 MB of the 480 MB budget.
### 🔵 Nits
- Neon copies are plain tables (no FK to `jurisdictions` on the target), the same as every other allow-listed table.

## Checks
- `python -c "import ast; ast.parse(...)"` on the sync module: ok
- Live API after the publish: GA timeline `coverage_available: True`, zero years drawn; dumbbell 43 rows.
