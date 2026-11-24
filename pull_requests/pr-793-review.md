---
pr: 793
branch: feat/792-failure-reasons
title: "feat(batch-jobs): click a stage's failed count to see why videos failed, grouped by reason"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 3b1d1016fa8fa0b47dae616c4749d7a211ebc7f1
verdict: approve
---

# PR Review: feat(batch-jobs): click a stage's failed count to see why videos failed, grouped by reason

## Summary

Automated review (#648) for PR #793 on `feat/792-failure-reasons`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/batch_jobs/failure_reasons.py`
- `api/routes/batch_jobs.py`
- `tests/test_failure_reasons_792.py`
- `web_app/src/App.tsx`
- `web_app/src/api/batchJobs.ts`
- `web_app/src/pages/BatchFailureReasonsPage.tsx`
- `web_app/src/pages/BatchJobStatusPage.tsx`
- `web_docs/docs/development/batch-failure-reasons.md`

## CI Status

See the PR checks on `3b1d1016fa8f`.

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
