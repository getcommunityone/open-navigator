---
pr: 764
branch: fix/763-run-all-parallel
title: "feat(batch-jobs): Run all starts stages 1\u20135 in parallel"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: github-actions
head_sha: fadec772adf5867558c2551fdfebf41eda561710
verdict: approve
---

# PR Review: feat(batch-jobs): Run all starts stages 1–5 in parallel

## Summary

Automated review (#648) for PR #764 on `fix/763-run-all-parallel`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/batch_jobs.py`
- `tests/test_batch_job_stage_controls_761.py`
- `web_app/src/pages/BatchJobStatusPage.tsx`
- `web_docs/docs/development/batch-analysis-light-full-design.md`

## CI Status

See the PR checks on `fadec772adf5`.

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
