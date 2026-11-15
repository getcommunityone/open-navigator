---
pr: 379
branch: dependabot/pip/pip-1e502c7b5b
title: "chore(deps): bump the pip group across 2 directories with 1 update"
author: dependabot[bot]
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve
---

# PR Review: pip group update (#379)

## Summary
Bumps `python-jose` 3.4.0 → 3.5.0 (JWT handling for login tokens) in `requirements.txt`, `requirements-cpu.txt` and the web app. Replaces #377, whose other updates already landed through #376.

## Scans
Secrets, fabricated data, personal data, destructive changes: none (requirement files only).

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `python-jose` backs login tokens; Backend Tests cover the auth routes. The recurring OpenTelemetry breakage is tracked in #378.

## Verdict
**approve.** CI: Frontend Build, Documentation Build, Backend Tests, API Types, PR conventions all success.
