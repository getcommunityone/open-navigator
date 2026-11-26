---
pr: 1008
branch: fix/1007-search-meeting-passages
title: "fix(api): meeting search finds meetings through their verbatim passages; topics table on the prod copy"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: aab19ba8c834ad79f791117e43a1584f06c083f7
verdict: approve
---

# PR Review: fix(api): meeting search finds meetings through their verbatim passages; topics table on the prod copy

## Summary

Automated review (#648) for PR #1008 on `fix/1007-search-meeting-passages`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/search.py`
- `api/routes/search_postgres.py`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `web_docs/docs/development/search-meeting-passages.md`

## CI Status

See the PR checks on `aab19ba8c834`.

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

## Agent review (Claude Code)

- The third leg runs only with a query or topic and is deduped on video_id against the analyzed and transcript legs. The snippet is a verbatim `ts_headline` of the passages. count_events uses the same `meeting_passage_where()`.
- Read-only runs against the prod and local DBs are recorded in the PR. Scans are clean; docs page added.

Verdict stands: approve.
