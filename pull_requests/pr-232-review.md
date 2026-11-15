---
pr: 232
branch: feat/150-money-payoff-subhead
title: "feat(web_app): make the money hook's payoff concrete on the homepage"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: coordinator (read the full diff against the rubric)
verdict: approve
---

# PR Review: a concrete payoff for the money hook (#150)

## Summary

Feedback issue #150 asks the "Show me my money" hook to say what the user gets. The homepage subhead changes from
"Four governments, one wallet. 90 seconds, mildly humbling, grandkids included." to "See what you pay in local taxes,
where it goes, and what it means for your grandkids. About 90 seconds." It is one line of copy, with no numbers. The
verdict is approve.

## Scope of Change

- Files changed: 1 (`web_app/src/pages/HomeV9.tsx`, +1 / -1)
- Areas touched: web_app (copy)

## CI Status

| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | success |

## Scans (secrets, fabricated data, personal data, destructive data changes)

All clean: one line of copy, with no figures.

## Findings

None.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Pass | `Closes #150`; branch `feat/150-money-payoff-subhead` |
| Conventional Commits | Pass | `feat(web_app)` |
| No fabricated data | Pass | No figures |

## Verdict

Approve.
