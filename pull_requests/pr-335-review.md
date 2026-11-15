---
pr: 335
branch: fix/333-gemini-25-flash-shutdown
title: "fix(llm): move the transcript pipeline off gemini-2.5-flash before its shutdown"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (a small, single-area diff; each point traced in the code and the tests run)
verdict: approve
---

# PR Review: fix(llm): move the transcript pipeline off gemini-2.5-flash before its shutdown

## Summary

Google deprecated `gemini-2.5-flash`: from December 1, 2026 its requests route to `gemini-3.5-flash-lite` at that
model's rates. This PR names the model the backlog's requests would reach anyway, with 3.8 Flash as the fallback. It
stops sending `temperature` to the models Google says ignore it and will later reject it, and it replaces the
third-party prices with Google's own, batch rates included.

Each claim cites Google's pages, read the same day. The tests cover the new behaviour, and a live call confirmed both
default models answer through the updated client. Verdict: **approve**.

## Scope of Change

- Files changed: 13 (+214 / -76)
- Areas touched: packages (llm), web_docs
- Commits: f13f56f fix(llm): move the transcript pipeline off gemini-2.5-flash before its shutdown
- Range reviewed: `origin/main..f13f56f` (merge base fc222ba)

## CI Status

| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | running at the time of writing |
| PR conventions | branch `fix/333-gemini-25-flash-shutdown` and `Closes #333` meet the rule |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data in a served path:** clean. Nothing under `api/` or `web_app/` changed.
- **Prices:** every price now cites Google's pricing page, with a read date. A price past its `valid_until` yields no
  cost rather than a guess, and Gemma's missing paid price stays empty.
- **Personal data:** clean.
- **Destructive or bulky data changes:** clean. No deletions and no data files.

## Strengths

- **The defaults follow the shutdown.** They move to the model Google routes 2.5 Flash requests to, at the same price,
  so there is no surprise on December 1 and the usage log records the model the calls actually reach.
- **`supports_sampling_params` matches Google's own rule.** It covers 3.5 Flash-Lite, 3.6 and later, and 4.x, and
  leaves every other model, including DeepSeek and Gemma, unchanged.
- **`valid_until` keeps the report from understating cost.** A known price change (3.6 and 3.8 Flash double on
  2027-01-01) can't silently produce a low figure.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

- **The fallback model thinks by default.**
  - Where: `analyze_backlog.py`.
  - What: `gemini-3.8-flash` used 124 thinking tokens on a two-line prompt, and the client can't set a 3.x thinking
    level yet.
  - Status: tracked in #336. It only costs extra when the lead model walls.
- **Aliases get `temperature` until their name says otherwise.**
  - Where: `genai_text_client.py`, `supports_sampling_params`.
  - What: a name without a version, such as `gemini-flash-latest`, still gets `temperature`. Today Google ignores it,
    so nothing fails.
  - Status: no fix needed now. If a future alias points at a model that rejects it, the 400 surfaces with the model
    name.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | #333 has the four parts; branch `fix/333-…`; `Closes #333`; follow-up #336 filed |
| Conventional Commits | ✅ | One commit, with the co-author trailer |
| No fabricated data | ✅ | Prices sourced and dated; `valid_until` |
| New Python in `packages/` | ✅ | Changes only in `packages/llm` |
| dbt / naming / keys / calendar years | n/a | No data-model changes |
| Docs | ✅ | Existing pages under `web_docs/docs/development/` updated |
| Telemetry and logging | ✅ | Unchanged (loguru) |
| Tests | ✅ | New tests for each behaviour change |
| Shared libraries | ✅ | `packages/llm` tests and the `tests/` files that import `llm` run |

## Test Coverage

- `pytest packages/llm`: 141 passed. With `packages/datamodels/tests` and the `tests/` files that import `llm`: 246
  passed.
- New tests:
  - `test_supports_sampling_params` (12 model names);
  - `test_temperature_is_left_out_for_models_that_ignore_it`;
  - `test_request_line_leaves_out_temperature_for_models_that_ignore_it`;
  - `test_default_flash_model_is_off_the_deprecated_25_flash`;
  - `test_a_price_past_its_valid_until_gives_no_cost`;
  - `test_shipped_prices_cite_google_and_have_batch_rates`;
  - the updated `test_default_models_drop_retired_and_deprecated_models`.
- `ruff check`: clean on the changed files.
- Live: both default models answered through `call_gemini_text`, and `python -m llm.usage.report` priced them from the
  new rates.

## Verdict

**approve.** Merge once the required checks are green. Worth merging before December 1, 2026, when `gemini-2.5-flash`
starts routing.
