---
pr: 835
branch: fix/834-vpn-banner-when-up
title: "fix(batch-jobs): clear VPN-down banner when the Surfshark tunnel is back"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: ea402f866c313110d36a3395a3a53bf7c92175d9
verdict: approve
---

# PR Review: fix(batch-jobs): clear VPN-down banner when the Surfshark tunnel is back

## Summary

Automated review (#648) for PR #835 on `fix/834-vpn-banner-when-up`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/batch_jobs.py`
- `tests/test_batch_job_launch_inactivity.py`

## CI Status

See the PR checks on `ea402f866c31`.

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
