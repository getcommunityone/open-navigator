---
pr: 881
branch: fix/878-redact-keys-in-logs
title: "fix(scrapers): keep API keys out of log lines"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 09f99d961e024961d229419706ceb8fa0b1f6be1
verdict: request-changes
---

# PR Review: fix(scrapers): keep API keys out of log lines

## Summary

Automated review (#648) for PR #881 on `fix/878-redact-keys-in-logs`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `packages/core-lib/src/core_lib/logging.py`
- `packages/core-lib/src/core_lib/redact.py`
- `packages/core-lib/tests/test_redact.py`
- `packages/scrapers/src/scrapers/youtube/scrape_youtube_channels.py`
- `packages/scrapers/src/scrapers/youtube/youtube_loader_logging.py`
- `web_docs/docs/development/log-redaction.md`

## CI Status

See the PR checks on `09f99d961e02`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: **findings**
- Fabricated data / personal / destructive: see findings

## Strengths

- (blocked on scan findings below)

## Findings

### 🔴 Blocking (Critical)

- Possible secret or credential pattern matched: `(?i)(api[_-]?key|secret|password|token)\s*[=:]\s…`

### 🟡 Should fix (Important)

None from automated heuristics.

### 🔵 Nit (Minor)

None from automated heuristics.

## Verdict

**request-changes**
