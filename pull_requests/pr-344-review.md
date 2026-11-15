---
pr: 344
branch: fix/328-deepseek-flash-peak-prices
title: "fix(llm): price DeepSeek by peak and off-peak hours, and name its current model"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: fix(llm): price DeepSeek by peak and off-peak hours, and name its current model

## Summary

DeepSeek calls showed no cost. The code named `deepseek-chat`, a model DeepSeek no longer lists or accepts, and
`prices.yaml` couldn't hold a rate that depends on the time of day. The PR prices DeepSeek's current models from its
own page, with peak hours and an off-peak rate. `model_price` picks the rate from the call's UTC time, and the
`--model` help names `deepseek-flash`. The contract was decided on the issue before the first commit. Closes #328.
Approve.

## Scope of Change

- Files changed: 6: `prices.py`, `prices.yaml`, `meeting_transcript_policy.py` (one help string), `test_usage.py`, and
  two docs pages
- Areas touched: packages/llm (usage pricing), docs

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: none. Every rate is copied from DeepSeek's pricing page as read on 2026-11-14, with `source` and
  `read_date`. Off-peak is half of peak, matching the page's own statement and its table. The holiday gap is stated,
  not estimated.
- Personal data: none.
- Destructive or bulky changes: none. Past `deepseek-chat` calls showed no cost before and still show none.

## Findings

None blocking, none to fix. Notes:

- **No time of day, no cost.** A call with no time, or only a date, gets no price, because the rate can't be chosen.
  Logged rows always carry `called_at` as a UTC timestamp (`calls.py`), so this only affects hand-made rows. It
  follows the file's rule: a cost is never assumed.
- **Holidays aren't modelled.** DeepSeek makes Chinese public holidays off-peak, and their dates aren't recorded, so a
  call during peak hours on one is priced at the peak rate. The estimate errs high, never low. The YAML comment and the
  docs both say so.
- **Other modes unchanged.** A mode with no `off_peak`, and every model with no `peak` (all the Gemini entries), is
  priced exactly as before. The existing price tests pass unchanged.
- `packages/llm/tests/test_call_cost_options.py` still uses `deepseek-chat` as an example of a non-Gemini name in its
  sampling-parameter tests. That name has nothing to do with pricing and stays.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #328 has all four parts; the contract decided in the plan is a dated comment; `Closes #328` |
| Conventional Commits | Yes | `fix(llm): ...` with the co-author trailer |
| Test first | Yes | 6 new tests failed before the change and pass after |
| No fabricated data | Yes | Sourced, dated rates; the holiday gap is stated, not guessed |
| Tests | Yes | Whole suite: 1384 passed, 40 skipped, 2 xfailed |

## Verdict

Approve once the required checks are green.
