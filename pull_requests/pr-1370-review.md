---
pr: 1370
branch: fix/1369-overview-column-scrollbar
title: "fix(stories): hide the Overview column scrollbar on desktop"
author: cursor-agent
reviewed_at: 2026-11-27
reviewer: coordinator
verdict: approve
---

## Scans

- Secrets / fabricated data / personal data / destructive: none

## Findings

None.

## Notes

CSS-only: pinned columns keep `overflow-y: auto`, hide the bar like snap. Matches owner ask to remove the Overview scrollbar.

## Local checks

- Diff reviewed; CI pending at review time.

