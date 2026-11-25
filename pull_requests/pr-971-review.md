---
pr: 971
branch: feat/970-overview-dot-map
title: "feat(web_app): story Overview shows a dot map of where data center meetings are"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: general-purpose subagent (read-only, two passes) and coordinator
head_sha: see branch head
verdict: approve-with-nits
---

# PR Review: feat(web_app): story Overview shows a dot map of where data center meetings are

## Summary

Closes #970. The Data Story's Overview screen draws the US as a dot map shaded by real meetings per state (new `counts.by_state`), and clicking a state narrows the story through `?state=`. The map geometry is shared with the Census dot map.

The first independent pass said **request-changes**. Every Blocking and Should-fix finding is fixed on the branch, and
the second pass says **approve-with-nits**. The CI bot's heuristic auto-review is superseded by this file.

## Findings and their fixes

### 🔴 Blocking (fixed)
1. **States outside the scope read "no meetings".** `by_state` was narrowed by the story's scope. **Fixed:** it is national (only the site and strength filters apply); the map highlights the scope, and every state keeps its own count. A test asserts that no state or city parameters reach the query.

### 🟡 Should fix (fixed)
- The WHERE clause was split from another query's text. Now it comes from a shared `_mention_where` helper.
- From a city scope, clicking the state jumped to National. Now it broadens to the state (`scopeCity`).
- The hover readout was a live region that flooded screen readers. It no longer is.

### 🔵 Nits
- **Fixed:**
  - legend keys use the index;
  - the caption names the highlighted state ("Texas highlighted, which contains Austin").
- **Open:** `by_state` runs one national count-distinct per call (the mart is small; cache if it grows).

## Tests
- pytest: 9 passed. vitest: 4 new tests for the colour scale; full suite green. `tsc` is clean.
- Browser: national 1,859 meetings across 50 states. Under a Charlotte scope, Texas reads 71 meetings, and clicking NC goes to `?state=NC`.

## Scans

- Secrets: clean.
- Fabricated data: clean.
- Personal data: none.
- Destructive changes: none.

## Verdict

**approve-with-nits**: merge when the required checks are green.
