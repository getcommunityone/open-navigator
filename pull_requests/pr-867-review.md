---
pr: 867
branch: perf/866-deepseek-thinking-off
title: "perf(llm): send DeepSeek calls with thinking off by default"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: ae433b40bd41109f30797ac05ac28e2baba22189
verdict: approve
---

# PR Review: perf(llm): send DeepSeek calls with thinking off by default

## Summary

Automated review (#648) for PR #867 on `perf/866-deepseek-thinking-off`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `.env.example`
- `packages/llm/src/llm/gemini/genai_text_client.py`
- `packages/llm/tests/test_deepseek_thinking.py`
- `web_docs/docs/development/llm-usage-tracking.md`

## CI Status

See the PR checks on `ae433b40bd41`.

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
