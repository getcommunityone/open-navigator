---
pr: 768
branch: fix/766-light-progress-stamps
title: "fix(batch-jobs): Analysis light % was counting deep Part 1 as light"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: github-actions
head_sha: 207944678445b3f8a95e0b0412e5a9950ab85a50
verdict: approve
---

# PR Review: fix(batch-jobs): Analysis light % was counting deep Part 1 as light

## Summary

Automated review (#648) for PR #768 on `fix/766-light-progress-stamps`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/batch_jobs/batch_job_db.py`
- `packages/llm/src/llm/gemini/reclassify_policy_tier_stamps.py`
- `packages/llm/src/llm/gemini/tests/test_reclassify_policy_tier_stamps.py`
- `web_app/src/pages/BatchJobStatusPage.tsx`
- `web_docs/docs/development/batch-analysis-light-full-design.md`

## CI Status

See the PR checks on `207944678445`.

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
