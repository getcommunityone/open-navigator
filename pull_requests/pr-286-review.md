---
pr: 286
branch: fix/281-api-docs-nginx
title: "fix(hosting): pass /api/docs through to the app's own Swagger route"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: fix(hosting): pass /api/docs through to the app's own Swagger route

## Summary

One nginx line; verified against the app that /api/docs is the served route and /docs is a 404. Closes #281. Approve.

## Scans

Secrets: clean. Fabricated data: none added. Personal data: none. Destructive changes: none.

## Findings

### 🔴 Blocking
None.
### 🟡 Should fix
None.
### 🔵 Nits
None.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #281 with four parts; branch and `Closes #281` |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |

## Verdict

Approve once the required checks are green.
