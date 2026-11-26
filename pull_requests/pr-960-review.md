---
pr: 960
branch: fix/959-hide-showing-national
title: "fix(web): hide Showing National under the United States blank"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: coordinator
verdict: approve
---

# PR Review: fix(web): hide Showing National under the United States blank

## Summary

Stops repeating **Showing: National** under the stories place blank that already reads **the United States** (#959). Hub omits the scope strip when there is no state; `ScopeBar` keeps the back crumb and only shows Showing + broaden controls for state/city. Docs match. No blocking findings.

## Scope of Change

- Files changed: 3
- Areas touched: web_app / web_docs
- Commits: `418090e0` fix(web): hide Showing National under the United States blank
- Range reviewed: `origin/main..HEAD`

## CI Status

See PR checks on the head commit.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean
- Fabricated data: clean
- Personal data: clean
- Destructive data: clean

## Strengths

- Matches the scope-label rule: national is still named once (the United States blank), not twice.
- City/state broaden controls preserved.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

None.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | yes | `fix/959-…`, Closes #959 |
| Conventional Commits | yes | |
| Scope label matches filter | yes | National named in blank only; Showing when narrowed |
| Docs | yes | |

## Test Coverage

Presentation-only; CI Frontend/Docs builds gate it.

## Verdict

**approve** — merge when required CI is green.
