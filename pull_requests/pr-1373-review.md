---
pr: 1373
branch: feat/1371-compact-topic-compare-all
title: "feat(home): Compare all on the chip bar; drop the large topic strip"
author: cursor-agent
reviewed_at: 2026-11-27
reviewer: coordinator
verdict: approve
---

## Scans

- Secrets / fabricated data / personal data / destructive: none

## Findings

None blocking. Dead `HomeTopicStrip.tsx` left intentionally; tracked in #1372.

## Notes

Matches owner choice: Compare all replaces All topics; large strip unmounted from home.

## Local checks

- `tsc --noEmit` passed; CI pending at review time.

