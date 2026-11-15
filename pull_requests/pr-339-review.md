---
pr: 339
branch: feat/336-gemini-thinking-level
title: "feat(llm): set a thinking level for the Gemini 3.x and 4 models"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (a small, single-area diff; each point traced in the code, the tests run, and the behaviour checked live)
verdict: approve
---

# PR Review: feat(llm): set a thinking level for the Gemini 3.x and 4 models

## Summary

The client can now turn down thinking on the Gemini 3.x and 4 models, which take a level instead of a token budget.
The levels each model accepts come from Google's thinking docs. The pipeline sends each model's lowest level by
default, and the 2.5 models keep the budget.

Live, `gemini-3.8-flash` (the backlog's fallback) went from 978 thinking tokens to none, with the same items and
votes on the made-up meeting. A Batch API job with the level succeeded. Verdict: **approve**.

## Scope of Change

- Files changed: 7 (`genai_text_client.py`, `batch_backlog.py`, `meeting_transcript_policy.py`, `compare_models.py`,
  two test files, `transcript-analysis-cost.md`)
- Areas touched: packages (llm), web_docs
- Commits: 0d4182a feat(llm): set a thinking level for the Gemini 3.x and 4 models
- Range reviewed: `origin/main..0d4182a` (merge base 2bd6d43)

## CI Status

| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | running at the time of writing |
| PR conventions | branch `feat/336-gemini-thinking-level` and `Closes #336` meet the rule |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data in a served path:** clean. No `api/` or `web_app/` changes. The level table cites Google's page,
  and the measurement in the doc and PR comes from real calls.
- **Personal data:** clean.
- **Destructive or bulky data changes:** clean.

## Strengths

- **Each model family gets the setting it takes.** A caller can pass both a budget and a level: 2.5 Flash gets the
  budget, 3.x and 4 get the level. Neither is sent where the API would reject it.
- **"lowest" resolves per model.** It follows Google's table ("minimal" on 3.5 Flash-Lite, "low" on 3.8 Flash, which
  doesn't accept "minimal"), so one CLI default works across models.
- **A rejected level degrades safely.** It reuses the existing retry (`_rejected_generation_option` matches
  "THINKING"), so an unexpected 400 drops the setting rather than failing the run.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

- **The level table is a snapshot.**
  - Where: `genai_text_client.py` (`_THINKING_LEVELS`).
  - What: a model Google adds later takes no level until it is listed. That is safe: such a model runs at its own
    default, and a level that turns out to be wrong is retried without.
  - Fix: when a new model enters the defaults, add its row from the thinking docs.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | #336 has the four parts; branch `feat/336-…`; `Closes #336` |
| Conventional Commits | ✅ | One commit, with the co-author trailer |
| No fabricated data | ✅ | Levels cite Google; measurements are from live calls |
| New Python in `packages/` | ✅ | `packages/llm` only |
| dbt / naming / keys / calendar years | n/a | |
| Docs | ✅ | `transcript-analysis-cost.md` updated |
| Tests | ✅ | Every behaviour change tested |
| Shared libraries | ✅ | `packages/llm` tests and the `tests/` files that import `llm` run |

## Test Coverage

- `pytest packages/llm`: 165 passed. With `packages/datamodels/tests` and the `tests/` files that import `llm`: 270
  passed.
- New tests:
  - `test_thinking_levels` (11 models);
  - `test_resolve_thinking_level` (7 cases);
  - `test_unknown_thinking_level_is_refused`;
  - `test_level_goes_to_level_models_and_budget_to_25_flash`;
  - `test_a_rejected_level_is_dropped_and_the_call_retried`;
  - `test_cli_thinking_level`;
  - `test_request_line_sends_a_thinking_level_to_level_models`.
- Live, with the real Part 1 prompt on the made-up meeting:
  - `gemini-3.8-flash` at its default: 978 thinking tokens, 66 s.
  - `gemini-3.8-flash` at "low": 0 thinking tokens, 62 s.
  - Both runs: 4/4 items and 4/4 votes.
  - `gemini-3.5-flash-lite` at "minimal": 0 thinking tokens, 21 s, 4/4 and 4/4.
- Batch: a one-request job to `gemini-3.8-flash` with `thinking_config.thinking_level: LOW` ended
  `JOB_STATE_SUCCEEDED` with a correct answer and no thinking tokens reported.

## Verdict

**approve.** Merge once the required checks are green.
