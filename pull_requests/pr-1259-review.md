---
pr: 1259
branch: fix/1258-publish-meeting-video-kind
title: "fix(data): keep meeting_video_kind in the production Neon sync"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: coordinator (read-only pass over a two-file diff)
verdict: approve
---

# PR Review: fix(data): keep meeting_video_kind in the production Neon sync

## Summary
Adds `meeting_video_kind` to the Neon serving allow-list so full syncs keep the real-meeting filter that map quotes use
(#1240), and documents the one-off publish already done on the owner's go-ahead. Verdict: approve.

## Scans
- Secrets, fabricated data, personal data, destructive changes: clean. The table classifies videos, not people.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None. Size checked: ~0.8 MB; Neon prod 367 → 368 MB of the 480 MB budget.
### 🔵 Nits
None.

## Checks
- `ast.parse` on the sync module: ok
- Published rows: 6,264 (`--only meeting_video_kind`)
