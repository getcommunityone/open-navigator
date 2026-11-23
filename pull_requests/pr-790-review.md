---
pr: 790
branch: fix/789-start-all-stale-procs
title: "fix(dev): start-all.sh stops this repo's stuck dev processes that hold no port"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: github-actions
head_sha: c19d6af0b41d240d81636763a11a31819fb64f97
verdict: approve
---

# PR Review: fix(dev): start-all.sh stops this repo's stuck dev processes that hold no port

## Summary

Automated review (#648) for PR #790 on `fix/789-start-all-stale-procs`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `start-all.sh`
- `tests/test_start_all_787.py`
- `web_docs/docs/development/start-all.md`

## CI Status

See the PR checks on `c19d6af0b41d`.

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
