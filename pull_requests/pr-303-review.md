---
pr: 303
branch: feat/302-databricks-token-signin
title: "feat(databricks): connect the Free Edition workspace from a phone with a token"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: feat(databricks): connect the Free Edition workspace from a phone with a token

## Summary

Lets the deploy sign in with a personal access token until the service principal exists, checks the connection and
creates the catalog once. The service principal still takes precedence. Closes #302. Approve.

## Scans

Secrets: clean. Fabricated data: none. The token is masked in logs and lives only in the GitHub environment. Personal data: none. Destructive changes: none.

## Findings

None blocking, none to fix, no nits.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #302 with four parts, under epic #293 |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |
| Docs | Yes | Existing page under `web_docs/docs/` |

## Verdict

Approve once the required checks are green.
