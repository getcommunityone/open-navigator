---
pr: 867
branch: perf/866-deepseek-thinking-off
title: "perf(llm): send DeepSeek calls with thinking off by default"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: ae433b40bd41109f30797ac05ac28e2baba22189
verdict: approve-with-nits
---

# PR Review: perf(llm): send DeepSeek calls with thinking off by default

## Summary

DeepSeek calls sent no thinking setting, so they ran with DeepSeek's default, thinking on at high effort, and the
thinking tokens were 82% of the output-rate tokens on the owner's last two days of runs. The PR sends thinking off
by default and adds `DEEPSEEK_THINKING` to turn it back on. Small and unit-tested with a stubbed client. No real
DeepSeek call was made: the account is empty and the session has no key.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `.env.example`
- `packages/llm/src/llm/gemini/genai_text_client.py`
- `packages/llm/tests/test_deepseek_thinking.py`
- `web_docs/docs/development/llm-usage-tracking.md`

## CI Status

See the PR checks on `ae433b40bd41`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. The token and dollar figures in the doc are copied from the owner's usage report; the expected saving is labelled as arithmetic, not a measurement. The test key is an obvious dummy.

## Strengths

- The cause is shown with the usage report's own numbers, and the parameter and its placement come from the
  provider's documentation read the same day.
- A bad setting fails before any request, so it cannot burn retries.
- The usage log is untouched, so the next run's report will show whether the change worked.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- Unverified against the live API. If DeepSeek rejects the request shape, every analysis call fails until the
  setting or code is corrected. Run one meeting first and read the usage report before a large run.
- Quality without thinking is untested on these prompts. The doc says so and names the check to run.

### 🔵 Nit (Minor)

- `temperature` is still sent; DeepSeek ignores it in thinking mode and honours it otherwise, so with thinking off
  the existing 0.1 now takes effect. That is the intended value, but it is a behaviour change worth knowing.
- The report stage makes between five and six calls per analysed meeting and is about three quarters of the
  DeepSeek cost. Not addressed here.

## Verdict

**approve-with-nits**
