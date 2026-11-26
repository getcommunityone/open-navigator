---
pr: 760
branch: ci/648-pr-review-auto
title: "ci(pr): auto-write and require pull_requests/pr-N-review.md"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: github-actions
head_sha: 54690c2c2fb7cf7ed153ec0cd357618f045f230e
verdict: approve
---

# PR Review: ci(pr): auto-write and require pull_requests/pr-N-review.md

## Summary

Automated review (#648) for PR #760 on `ci/648-pr-review-auto`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `.github/scripts/auto_pr_review.py`
- `.github/scripts/pr_conventions.py`
- `.github/workflows/pr-conventions.yml`
- `pull_requests/README.md`
- `tests/test_auto_pr_review.py`
- `tests/test_pr_conventions.py`

## CI Status

See the PR checks on `54690c2c2fb7`.

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
