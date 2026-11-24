---
pr: 886
branch: fix/885-embedding-fallback-guard
title: "fix(llm): refuse to write embeddings from a different encoder than the table holds"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 5164257c41173678ad22e64f44d1f39a10c59539
verdict: approve-with-nits
---

# PR Review: fix(llm): refuse to write embeddings from a different encoder than the table holds

## Summary

The embedding step fell back to TF-IDF when the transformer could not be loaded and wrote those vectors beside the
stored transformer vectors; question assignment then failed on the dimension. The PR checks the encoder and
dimension against what the table holds before writing, and stops with nothing written. One part of #885.
Unit-tested; not run against a database.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `packages/llm/src/llm/policy_questions/embed_instances.py`
- `packages/llm/tests/test_pq_embedding_guard.py`

## CI Status

See the PR checks on `5164257c4117`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. The change prevents a write; it deletes nothing. The owner's table still holds the wrong vectors until it is re-embedded.

## Strengths

- The failure is now loud and happens before the write, with a message that says what to install.
- The test loads the guard without importing the encoder stack, so it runs anywhere.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- A table already holding both kinds (the owner's state) refuses a plain re-run even with the transformer
  installed; the repair is `--full-refresh --allow-model-change`. The error message says so, but the owner should be
  told directly.
- The database address these commands resolve can still be production (#885); not fixed here.

### 🔵 Nit (Minor)

- The check runs after encoding, so a doomed run still spends the encoding time.

## Verdict

**approve-with-nits**
