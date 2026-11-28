---
pr: 1494
issue: 1476
branch: chore/1476-round2-gold-results
title: "chore(stance): commit round-2 gold results and gate outcomes"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: coordinator
verdict: approve
---

# PR Review: chore(stance): commit round-2 gold results and gate outcomes

Reviewed against `.claude/review-rubric.md`.

## Summary

Commits the 538 round-2 Jev gold predictions (`packages/llm/src/llm/typesafe/gold/speaker_stance_gold_round2_results.json`), records the round-2 and `--all-rounds` gate outcomes plus `2026-11-28` Jev usage in `web_docs/docs/development/speaker-stance-classifier.md`, and pins the numbers in `packages/llm/tests/test_speaker_stance.py`. Only `battery-storage` passed (already released and serving), so no additional paid classifier run was executed.

## Scope of Change

- Files changed: 3 (+8148 / -1, mostly the committed `speaker_stance_gold_round2_results.json` predictions file)
- Areas touched: `packages/llm`, `web_docs`
- Commits: `f1d6ffe5` (`chore(stance): commit round-2 gold results and gate outcomes (#1476)`)
- Range reviewed: `main..HEAD`

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: clean (every metric comes directly from `speaker_stance_gold report` / `report --all-rounds` and `llm.usage.report`).
- Personal data: clean (`speaker_stance_gold_round2_results.json` verified to contain only `{heat, input_chars, input_tokens, question_version, side, side_confidence, side_probabilities}` keyed by topic + MD5 speaker ID; zero speech text or names).
- Destructive data changes: clean.

## Strengths

- Keeps the remaining 12 held topics held (`#1477` / `#1402`) rather than running an unvalidated paid batch.
- Enforces the zero-speech schema and exact gate numbers in `test_committed_round2_gold_run_numbers()`.

## Findings

### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
None.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first, four parts, branch/PR naming | Yes | #1476, `chore/1476-round2-gold-results`, `Closes #1476` |
| Conventional Commits | Yes | `chore(stance): ...` |
| No fabricated data / zero speech in gold | Yes | Asserted in `test_committed_round2_gold_run_numbers()` |
| Docs with the change | Yes | `speaker-stance-classifier.md` |
| Tests | Yes | `packages/llm/tests/test_speaker_stance.py` |

## Test Coverage

- `.venv/bin/ruff check packages/llm/tests/test_speaker_stance.py`: passed.
- `PYTHONPATH=packages/llm/src .venv/bin/pytest packages/llm/tests/test_speaker_stance.py`: 21 passed.
- `cd web_docs && npm run build`: succeeded.

## Verdict

approve.
