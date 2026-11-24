---
pr: 881
branch: fix/878-redact-keys-in-logs
title: "fix(scrapers): keep API keys out of log lines"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 09f99d961e024961d229419706ceb8fa0b1f6be1
verdict: request-changes
---

# PR Review: fix(scrapers): keep API keys out of log lines

## Summary

YouTube API errors quote the request URL, which carries the API key, and the scraper logged them as they were. The
PR adds a redaction helper in core-lib, installs it on every loguru message of the YouTube scraper and loaders, and
redacts the offending error line directly. Unit-tested, and exercised once through the loaders' real logging setup.
It does not make the already-leaked key safe; the owner must rotate it.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

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
- Secrets: the tests use a key-shaped fake built at run time, not a real key, and the leaked key is not repeated in the code, tests, docs, issue or PR. Fabricated data / personal / destructive: clean.

## Strengths

- (blocked on scan findings below)

## Findings

### 🔴 Blocking (Critical)

- Possible secret or credential pattern matched: `(?i)(api[_-]?key|secret|password|token)\s*[=:]\s…`

### 🟡 Should fix (Important)

- Output that bypasses loguru is not filtered, and the batch tab shows log tails as written. A filter where the
  batch runner writes child output to the log file, or where the API serves the tail, would close that gap.
- Other entry points (the analysis pipeline, the loaders outside YouTube) do not install the redaction yet.

### 🔵 Nit (Minor)

- The environment-value pass re-reads the environment on every log message; cheap, but it could be cached.
- `token=` in ordinary query strings (a pagination token, for example) is also blanked. That errs on the safe side.

## Verdict

**request-changes**
