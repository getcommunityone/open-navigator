---
pr: 873
branch: feat/871-light-analysis-claude-haiku
title: "feat(llm): run the light analysis and its reports on Claude Haiku 5.5"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 72e0cfb944ee4d69621cc89ae8d812eb7d3d60e5
verdict: request-changes
---

# PR Review: feat(llm): run the light analysis and its reports on Claude Haiku 5.5

## Summary

Adds Claude Haiku 5.5 as a provider for the analysis pipeline and makes it the default for the two light stages, at
the owner's decision. Calls stream through the official SDK with low-effort thinking, prompt caching, a guard that
skips a prompt over the 100,000-token price tier, and usage logging. DeepSeek and Gemini stay selectable; the full
stages are unchanged. Tested with a stubbed client; the request parameters were checked against the installed
SDK's signatures. No real Anthropic call was made.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `.env.example`
- `packages/llm/src/llm/claude/text_client.py`
- `packages/llm/src/llm/gemini/genai_text_client.py`
- `packages/llm/src/llm/gemini/meeting_transcript_policy.py`
- `packages/llm/src/llm/gemini/tier_model_guard.py`
- `packages/llm/src/llm/typesafe/light_blurb.py`
- `packages/llm/tests/test_claude_light_analysis.py`
- `packages/llm/tests/test_jev_analyze_gate.py`
- `packages/scrapers/scripts/youtube_run_priority_states_last_n.sh`
- `tests/test_loader_gate_796.py`
- `web_docs/docs/development/transcript-analysis-cost.md`

## CI Status

See the PR checks on `72e0cfb944ee`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: **findings**
- Fabricated data / personal / destructive: clean. The docs state that cost and quality on Haiku are unmeasured. The key is read by the SDK or from `.env` and is not logged. A refusal, an empty answer or a truncated answer raises and is never saved as an analysis.

## Strengths

- (blocked on scan findings below)

## Findings

### 🔴 Blocking (Critical)

- Possible secret or credential pattern matched: `(?i)(api[_-]?key|secret|password|token)\s*[=:]\s…`

### 🟡 Should fix (Important)

- No live call. The first run decides whether the request is accepted as sent, whether the prompt prefix is long
  enough to cache, and whether a 65,536 `max_tokens` is acceptable. Run about 20 meetings and read the usage report
  before a large run.
- Quality on these prompts is untested. Run `python -m llm.gemini.public_comment_checks` on that first sample.
- The default lives in a shell script (`youtube_run_priority_states_last_n.sh`) and a constant; a test pins the
  constant but nothing pins the script's default to it.

### 🔵 Nit (Minor)

- Cache-write tokens are priced as plain input in the usage report, slightly underpricing a cached run's first call.
- Skipped over-long meetings appear as failed policy events; there is no single list of them for the owner yet.

## Verdict

**request-changes**
