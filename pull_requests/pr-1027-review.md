---
pr: 1027
branch: fix/1026-topics-city-subquery
title: "fix(api): topics list no longer fails for a city whose name is inside another place's (Tuscaloosa)"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 501f7a1e6ad079f8287e449449acfc2ab2525d17
verdict: approve
---

# PR Review: fix(api): topics list no longer fails for a city whose name is inside another place's (Tuscaloosa)

## Summary

Automated review (#648) for PR #1027 on `fix/1026-topics-city-subquery`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/topics.py`
- `tests/test_api_topics.py`

## CI Status

See the PR checks on `501f7a1e6ad0`.

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

- Scalar city subquery now orders by exact name then most meetings, LIMIT 1. Verified 200 for AL/Tuscaloosa (was 503), other scopes unchanged; 14 topics tests pass. Scans clean.

Verdict stands: approve.
