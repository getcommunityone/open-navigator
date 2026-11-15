---
pr: 330
branch: chore/266-gemini-prices
title: "chore(llm): price Gemini calls from Google's own page, batch included"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: chore(llm): price Gemini calls from Google's own page, batch included

## Summary

The usage report's Gemini prices now come from Google's own Gemini API pricing page, read today, for all four Gemini
models in both API modes. Before, the interactive rates came from a third-party republisher and batch had none.
DeepSeek's page no longer lists `deepseek-chat`, and prices its current models by time of day, so that row keeps no
price, with the reason written down and #328 filed. The model deprecation the page announces is filed as #329.
Closes #266. Approve.

## Scope of Change

- Files changed: 3: `prices.yaml`, `packages/llm/tests/test_usage.py`, `web_docs/docs/development/llm-usage-tracking.md`
- Areas touched: packages (llm), docs
- Commits: 01f9f4fd chore(llm): price Gemini calls from Google's own page, batch included

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: clean. I checked every new number against the downloaded pricing page: the paid-tier text rate,
  per 1M tokens, in the Standard and Batch tabs. Each carries its source URL and read date, as the file's rule
  requires. No price is assumed for DeepSeek.
- Personal data: none.
- Destructive changes: none.

## Findings

None blocking, none to fix, no nits. The test pins one batch cost (`0.05 + 0.20` for 1M in and 1M out on
`gemini-2.5-flash-lite`). That's intended, so a later edit to the price table shows up in review.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #266 has all four parts; the DeepSeek change is recorded as a dated line; `Closes #266` |
| Conventional Commits | Yes | `chore(llm): ...` with the co-author trailer |
| No fabricated data | Yes | Every price is sourced and dated; DeepSeek is left blank rather than guessed |
| Tests | Yes | The new test failed before (republisher source, no batch rates) and passes after; `packages/llm/tests`: 125 passed |
| Docs | Yes | The existing page under `web_docs/docs/` is updated |

## Verdict

Approve once the required checks are green.
