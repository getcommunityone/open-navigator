---
pr: 377
branch: dependabot/pip/pip-607752f497
title: "chore(deps): bump the pip group across 2 directories with 3 updates"
author: dependabot[bot]
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve
---

# PR Review: pip group update (#377)

## Summary
Bumps `python-jose` 3.4.0 → 3.5.0 (JWT handling for auth), `aiohttp` 3.14.4 and `opentelemetry-api` 1.45.2. The last two already landed on main through #376, so they merged as no-ops. The merge with main kept main's matching OpenTelemetry family (1.45.2 / 0.66b2) and this branch's `mlflow>=3.18.0` in `requirements-cpu.txt`. `uv pip compile` resolves all three requirement files.

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
**approve** once CI is green.
