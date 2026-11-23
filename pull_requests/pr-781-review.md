---
pr: 781
branch: fix/778-shared-channel-upsert-ownership
title: "fix(youtube): keep a shared-channel video's place when another town re-crawls it"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: github-actions
head_sha: 858ccae4aa0438622341c7029fd76e5c027f9193
verdict: approve
---

# PR Review: fix(youtube): keep a shared-channel video's place when another town re-crawls it

## Summary

Automated review (#648) for PR #781 on `fix/778-shared-channel-upsert-ownership`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py`
- `packages/scrapers/tests/test_youtube_jurisdiction_name_not_id.py`
- `packages/scrapers/tests/test_youtube_upsert_ownership.py`
- `web_docs/docs/data-sources/youtube-discovery.md`

## CI Status

See the PR checks on `858ccae4aa04`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: see findings

## Strengths

- Automated scans found no secret/credential patterns in added lines.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None from automated heuristics.

### 🔵 Nit (Minor)

None from automated heuristics.

## Verdict

**approve**
