---
pr: 352
branch: fix/350-flyout-active-scope
title: "fix(home): browse flyout links carry the active scope, not the saved location"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator
verdict: approve-with-nits
---

# PR Review: fix(home): browse flyout links carry the active scope, not the saved location

## Summary
Closes #350. On the homepage, every Browse pill link (the question, topic and cause items, "see all" for topics and causes, and Places) now builds its `state` / `city` params from one helper, `activeScopeParams()`. The helper uses the active scope (`stateCode`, plus `city` at city level) instead of the saved location. Before, a user with a saved city who picked National saw national lists but was sent to city-filtered pages, which broke "Scope Label Must Match the Active Filter". The change is small and type-checks, and the logic matches `runSearch` in the same file. Approve with one behaviour note for the maintainer: Places no longer carries `county`.

## Scope of Change
- Files changed: 1 (+22 / -30)
- Areas touched: web_app
- Commits:
  - see `git log main..fix/350-flyout-active-scope`: the fix, plus a comment correction
- Range reviewed: `main..fix/350-flyout-active-scope`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | ⏳ pending at time of review |
| Documentation Build | ⏳ pending |
| Backend Tests | ⏳ pending |
| API Types | ⏳ pending |
| PR conventions | ⏳ pending (#350 has the four parts) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean (no figures touched).
- Personal data: clean. Fewer saved-location values reach URLs than before.
- Destructive data changes: clean.

## Strengths
- One helper replaces five copies of the param-building code.
- Comments now describe the active-scope rule and point to #350.
- It matches the rule the same file already applies in `runSearch`.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `HomeV9.tsx`, Browse places `to`: the link used to add `county=` for a saved location with a county but no city. `JurisdictionsSearch.tsx:109,124` reads `county`, so county-only users now land on the state view instead of their county. That is consistent with the label (the homepage never shows a county scope: the `city` level is disabled without a city, `:481`). A county level on the homepage would be the proper way to get it back. Verified by reading `naturalLevel` (`:433`) and the level options (`:481-482`).
- When #349 merges, its trending-questions row can use `activeScopeParams()` instead of its own copy of the same two lines.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `fix/350-…`, `Closes #350`, issue has the four parts |
| Conventional Commits | ✅ | Co-author trailers |
| No fabricated data | ✅ | |
| Scope label matches filter | ✅ | The point of the change |
| Docs / Python / dbt / keys / years | n/a | |
| Tests | ⚠️ | No HomeV9 tests exist; manual check in the PR description |

## Test Coverage
- `npx tsc --noEmit`: clean. `npx eslint src/pages/HomeV9.tsx`: only the existing exhaustive-deps warning.
- No automated UI test.

## Verdict
**approve-with-nits.** Merge once CI is green. Decide whether county-only users need a county scope on the homepage.
