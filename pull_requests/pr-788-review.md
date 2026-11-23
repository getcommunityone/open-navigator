---
pr: 788
branch: fix/787-start-all-unattended
title: "fix(dev): start-all.sh clears its ports, starts unattended, and fails loudly if a service is down"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: github-actions
head_sha: cde5389536d69cf75d09be8a87efed5c54ee46db
verdict: approve
---

# PR Review: fix(dev): start-all.sh clears its ports, starts unattended, and fails loudly if a service is down

## Summary

Automated review (#648) for PR #788 on `fix/787-start-all-unattended`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `start-all.sh`
- `tests/test_start_all_787.py`
- `web_app/vite.config.ts`
- `web_docs/docs/development/start-all.md`

## CI Status

See the PR checks on `cde5389536d6`.

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
