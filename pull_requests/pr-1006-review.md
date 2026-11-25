---
pr: 1006
branch: fix/1005-decisions-map-path
title: "fix(web_app): decisions map calls /api/decision/map"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: github-actions
head_sha: 6a95d72f39b35c9468f90ee103dfc497270efb6f
verdict: approve
---

# PR Review: fix(web_app): decisions map calls /api/decision/map

## Summary

Automated review (#648) for PR #1006 on `fix/1005-decisions-map-path`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/pages/DecisionsMapPage.tsx`

## CI Status

See the PR checks on `6a95d72f39b3`.

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

## Agent review (Claude Code)

- One-line path fix; the router prefix is `/decision`. Browser check: 1,000 pins, no 4xx. No other `/decisions/map` callers.
- Scans clean.

Verdict stands: approve.
