---
pr: 292
branch: docs/290-coverage-figures
title: "docs(pitch): coverage figures from /api/stats in the README and the status slide"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: docs(pitch): coverage figures from /api/stats in the README and the status slide

## Summary

Adds four national figures from /api/stats to the README and slide 10, each labelled with the endpoint and the
snapshot date, and leaves out the figures the endpoint gets wrong (#291). Deck rebuilt; `--check` passes. Closes #290.
Approve.

## Scans

Secrets: clean. Fabricated data: none; every figure traces to the live endpoint, with its date. Personal data: none. Destructive changes: none.

## Findings

None blocking, none to fix, no nits.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #290 with four parts; `Closes #290` |
| Conventional Commits | Yes | |
| No fabricated data | Yes | Source and date on each figure |
| Docs | Yes | Existing page under `web_docs/docs/` |

## Verdict

Approve once the required checks are green.
