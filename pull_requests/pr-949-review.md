---
pr: 949
branch: fix/948-deploy-map-data
title: "fix(deploy): carry the generated census map data into the isolated HF deploy clone"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: github-actions
head_sha: 7e337ccb133289c61a3bcd37773367bcb027061d
verdict: approve
---

# PR Review: fix(deploy): carry the generated census map data into the isolated HF deploy clone

## Summary

Automated review (#648) for PR #949 on `fix/948-deploy-map-data`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `packages/hosting/scripts/huggingface/deploy-huggingface.sh`
- `web_docs/docs/deployment/huggingface-spaces.md`

## CI Status

See the PR checks on `7e337ccb1332`.

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
