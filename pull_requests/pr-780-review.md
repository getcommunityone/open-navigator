---
pr: 780
branch: fix/777-shared-channel-video-routing
title: "fix(youtube): file shared-channel videos under the government their title names"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: github-actions
head_sha: 729368dc035e5727bc3d7ba1226cc8f4482a87ab
verdict: approve
---

# PR Review: fix(youtube): file shared-channel videos under the government their title names

## Summary

Automated review (#648) for PR #780 on `fix/777-shared-channel-video-routing`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `packages/scrapers/src/scrapers/discovery/channel_government_mismatch.py`
- `packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py`
- `packages/scrapers/src/scrapers/youtube/reassign_shared_channel_videos.py`
- `packages/scrapers/tests/test_shared_channel_video_routing.py`
- `web_docs/docs/data-sources/youtube-discovery.md`

## CI Status

See the PR checks on `729368dc035e`.

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
