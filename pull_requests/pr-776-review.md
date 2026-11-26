---
pr: 776
branch: feat/774-light-deepseek
title: "feat(batch-jobs): run Analysis light and Reports light on DeepSeek, not Gemini"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: github-actions
head_sha: 16b74faea4aa08df54e22117bd7c7de09a72f3ad
verdict: approve
---

# PR Review: feat(batch-jobs): run Analysis light and Reports light on DeepSeek, not Gemini

## Summary

Automated review (#648) for PR #776 on `feat/774-light-deepseek`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `.env.example`
- `packages/llm/src/llm/gemini/meeting_transcript_policy.py`
- `packages/llm/tests/test_jev_analyze_gate.py`
- `packages/scrapers/scripts/youtube_run_priority_states_last_n.sh`
- `pull_requests/pr-776-review.md`
- `web_app/src/pages/BatchJobStatusPage.tsx`
- `web_docs/docs/development/batch-analysis-light-full-design.md`

## CI Status

See the PR checks on `16b74faea4aa`.

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
