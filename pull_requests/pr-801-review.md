---
pr: 801
branch: feat/796-part2
title: "feat(llm): skip non-government meetings on load, keep light and full apart, stop deleting cache duplicates"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 8ce6cc68b8924bd617d952096778736ed6346305
verdict: approve
---

# PR Review: feat(llm): skip non-government meetings on load, keep light and full apart, stop deleting cache duplicates

## Summary

Automated review (#648) for PR #801 on `feat/796-part2`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `packages/llm/src/llm/enrichment/analysis_load_gate.py`
- `packages/llm/src/llm/enrichment/load_analysis_cache_to_bronze.py`
- `packages/llm/src/llm/gemini/meeting_transcript_policy.py`
- `packages/llm/src/llm/gemini/tier_model_guard.py`
- `packages/llm/src/llm/gemini/tier_names.py`
- `packages/llm/src/llm/gemini/transcript_cache_paths.py`
- `tests/test_cache_set_aside_796.py`
- `tests/test_loader_gate_796.py`
- `web_docs/docs/development/batch-load-tab.md`

## CI Status

See the PR checks on `8ce6cc68b892`.

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
