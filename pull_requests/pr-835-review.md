---
pr: 835
branch: fix/834-vpn-banner-when-up
title: "fix(batch-jobs): clear VPN-down banner when the Surfshark tunnel is back"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 090e282b723aa3e9a29893e59fec12d06e50a4fc
verdict: approve
---

# PR Review: fix(batch-jobs): clear VPN-down banner when the Surfshark tunnel is back

## Summary

Automated review (#648) for PR #835 on `fix/834-vpn-banner-when-up`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/batch_jobs.py`
- `pull_requests/pr-835-review.md`
- `tests/test_batch_job_launch_inactivity.py`

## CI Status

See the PR checks on `090e282b723a`.

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
