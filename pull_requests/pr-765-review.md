---
pr: 765
branch: fix/699-gemini-billing-warning
title: "fix(batch-jobs): surface Gemini 402 billing exhaustion on dashboard"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: github-actions
head_sha: fa9ec04c2703e81477bc1e7befc79f890d12e9d8
verdict: approve
---

# PR Review: fix(batch-jobs): surface Gemini 402 billing exhaustion on dashboard

## Summary

Automated review (#648) for PR #765 on `fix/699-gemini-billing-warning`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/batch_jobs.py`
- `packages/llm/src/llm/gemini/genai_text_client.py`
- `packages/llm/src/llm/gemini/tests/test_genai_text_client.py`
- `tests/test_batch_job_launch_inactivity.py`
- `web_app/src/api/batchJobs.ts`
- `web_app/src/pages/BatchJobStatusPage.tsx`

## CI Status

See the PR checks on `fa9ec04c2703`.

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
