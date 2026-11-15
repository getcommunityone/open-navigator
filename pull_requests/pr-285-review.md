---
pr: 285
branch: fix/284-money-flow-not-served
title: "fix(api): money-flow lenses whose table isn't served show as unavailable, logged once"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: fix(api): money-flow lenses whose table isn't served show as unavailable, logged once

## Summary

A missing relation is logged once and the lens stays empty; other errors still warn. Tests fail without the change and pass with it; the decision is written down in web_docs/docs/development/neon-serving-scope.md. Closes #284. Approve.

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
| Issue first | Yes | #284 with four parts; branch and `Closes #284` |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |

## Verdict

Approve once the required checks are green.
