---
pr: 298
branch: feat/294-databricks-free-dev-target
title: "feat(databricks): a Free Edition target deployed by CI, copied from the NLP lab's setup"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: feat(databricks): a Free Edition target deployed by CI, copied from the NLP lab's setup

## Summary

Adds a Free Edition bundle target, a setup script, the sign-in action and a deploy workflow copied from the Health
Transformation Lab. Nothing runs until the GitHub environment `free` has the principal's secret; the job deploys
paused. Closes #294. Approve with one nit.

## Scans

Secrets: clean. Fabricated data: none. No secret in any file; the setup script prints the secret command and never stores it. Personal data: none. Destructive changes: none.

## Findings

None blocking, none to fix.

Nit: `bundle validate -t free` couldn't run here without a workspace; the first workflow run is the real check.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #294 (epic #293) with four parts; contract change noted on the issue |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |
| Docs | Yes | New page under `web_docs/docs/deployment/`, kebab-case, front matter |

## Verdict

Approve once the required checks are green.
