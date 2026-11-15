---
pr: 289
branch: docs/287-use-cases-no-invented-figures
title: "docs(intro): describe the use cases in words, with no invented figures"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: docs(intro): describe the use cases in words, with no invented figures

## Summary

Removes every invented figure from the five use cases in `intro.md` and describes each in words, pointing to the app
page that has it. The routes named exist in `web_app/src/App.tsx`. Closes #287. Approve.

## Scans

Secrets: clean. Fabricated data: removed, none added. Personal data: none. Destructive changes: none.

## Findings

None blocking, none to fix, no nits.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #287 with four parts; `Closes #287` |
| Conventional Commits | Yes | |
| No fabricated data | Yes | The point of the change |
| Docs | Yes | Existing page under `web_docs/docs/` |

## Verdict

Approve once the required checks are green.
