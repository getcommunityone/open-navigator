---
pr: 912
branch: fix/911-restore-lfs-static
title: "fix(hosting): restore real files in place of Git LFS pointers when the Space starts"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: fde13b781d8eed0f1a917266439125af93f2737d
verdict: approve
---

# PR Review: fix(hosting): restore real files in place of Git LFS pointers when the Space starts

## Summary

Automated review (#648) for PR #912 on `fix/911-restore-lfs-static`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `.huggingface/restore_lfs_static.sh`
- `.huggingface/start.sh`
- `Dockerfile.huggingface`
- `tests/test_restore_lfs_static.py`
- `web_docs/docs/deployment/huggingface-spaces.md`

## CI Status

See the PR checks on `fde13b781d8e`.

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
