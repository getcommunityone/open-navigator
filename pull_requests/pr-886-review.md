---
pr: 886
branch: fix/885-embedding-fallback-guard
title: "fix(llm): refuse to write embeddings from a different encoder than the table holds"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 5164257c41173678ad22e64f44d1f39a10c59539
verdict: approve
---

# PR Review: fix(llm): refuse to write embeddings from a different encoder than the table holds

## Summary

Automated review (#648) for PR #886 on `fix/885-embedding-fallback-guard`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `packages/llm/src/llm/policy_questions/embed_instances.py`
- `packages/llm/tests/test_pq_embedding_guard.py`

## CI Status

See the PR checks on `5164257c4117`.

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
