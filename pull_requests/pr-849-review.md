---
pr: 849
branch: feat/848-chat-claude-haiku
title: "feat(api): meeting chat answers with Claude Haiku instead of Gemini Flash-Lite"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 17c91e03620eee7f6f0c8f1fcff0cf088b10918c
verdict: approve-with-nits
---

# PR Review: feat(api): meeting chat answers with Claude Haiku instead of Gemini Flash-Lite

## Summary

Moves the meeting chat's one model call from Gemini Flash-Lite to Claude Haiku 5.5 through the official `anthropic`
SDK, keeps the Gemini path behind `CHAT_PROVIDER=gemini`, adds a sourced price for the cost estimate, and removes a
guessed fallback rate. Request and response shapes, rate limits and the spend cap are unchanged. Unit-tested with the
SDK client stubbed; no real call to the Anthropic API was made because the session has no key.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `.env.example`
- `api/routes/chat_meetings.py`
- `packages/llm/pyproject.toml`
- `packages/llm/src/llm/claude/__init__.py`
- `packages/llm/src/llm/claude/text_client.py`
- `packages/llm/src/llm/usage/prices.yaml`
- `packages/llm/tests/test_claude_text_client.py`
- `requirements-cpu.txt`
- `requirements.txt`
- `setup.py`
- `tests/test_chat_meetings.py`
- `web_docs/docs/development/meeting-chat-model.md`

## CI Status

See the PR checks on `17c91e03620e`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. The price was read from Anthropic's pricing page on the stated date; an unpriced model now gives a null estimate instead of a guessed one. No key is read, stored or logged by the new code.

## Strengths

- The request sends nothing current Claude models reject (no sampling parameters, no thinking budget, no prefill),
  and a test asserts that.
- A refusal raises instead of being read as an empty answer.
- The provider is a setting, so going back to Gemini needs no code change.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- No live call was made. The owner must set `ANTHROPIC_API_KEY`, install the newer `anthropic` package and ask one
  question to confirm. Until the key is set the chat returns 502, as it does today for the Gemini credit error.
- `anthropic` moves from `>=0.8.0` to `>=2.13`, a major-version jump. The only other caller,
  `packages/agents/agents/policy_reasoning_analyzer.py`, uses `Anthropic(api_key=...).messages.create`, which is
  unchanged, but it was not exercised here.

### 🔵 Nit (Minor)

- When a model has no price the call adds nothing to the daily spend total, so the cap would not bite for an
  unpriced `CHAT_MODEL`. The default model is priced.
- The chat code keeps the file's existing `Optional`/`Tuple` typing style, which ruff flags elsewhere in the file too.

## Verdict

**approve-with-nits**
