---
pr: 1211
branch: fix/1205-header-scope-label
title: "fix(web): header place control names the page's actual scope (National · Use your town)"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: coordinator
verdict: approve
---

# PR Review: fix(web): header place control names the page's actual scope (National · Use your town)

## Summary
This PR makes the header's place control follow the CLAUDE.md scope-label rule. On pages whose data follows `?state=&city=`, the control now names the page's real scope:
- the URL place, or
- **National** with a one-click **Use <saved town>**, or
- **National · Find your town**.

Before, it named the saved town over national data. The one-click apply reuses `usePlacePick` from #1197, so the label, the URL and the page's data move together.

Playwright on `/stories/guns` confirms the before/after on desktop and iPhone. The menu breakpoint moves to 1024px so the wider label fits; this was measured. The withdrawn Browse Topics request was correctly left out.

## Scope of Change
- Files changed: 4 (+185 / -31): `SiteHeader.tsx`, `headerPlace.ts`, `headerPlace.test.ts`, `guides/site-navigation.md`
- Areas touched: web_app, web_docs, pull_requests
- Commits: 4490647c fix(web): header place control names the page's actual scope (#1205); d3e8f913 bot auto-review; this review
- Range reviewed: `2e4974c5..HEAD`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | read on the head commit before merge |
| Documentation Build | read on the head commit before merge (passed locally) |
| Backend Tests | read on the head commit before merge (no Python changed) |
| API Types | read on the head commit before merge |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data: clean. Every label comes from the URL or the reader's own saved location. The fallback is "National · Find your town", never a stand-in town.
- Personal data: clean. It reuses the existing saved location (`localStorage`). Nothing new is stored or logged.
- Destructive data changes: none.

## Strengths
- The label rule is one pure function, `headerPlaceState`, with a test for each of its states. It also covers home, pages that aren't scope-aware, and lookalike routes such as `/stories-old`.
- "Use <town>" writes the scope through the same path as a picker pick. No second code path can drift.
- Home keeps its own level picker untouched.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
1. **`SCOPED_ROUTE_PREFIXES` is a hand-kept list** (`utils/headerPlace.ts`). A new page that starts reading `?state=` must be added to it, or it gets the "your town" label. The docs name the list and where it lives. Deriving it from the routes would need route metadata that doesn't exist yet. Left as is.
2. **City scope on a story** (`/stories/guns?state=AL&city=Tuscaloosa`). The page's headline reads "Alabama took up guns in 386 meetings". That is the story page's own city handling, which another agent owns. The header correctly shows the scope in the URL.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | #1205 has Problem / Done when / Contract / Read first and links #1191; branch `fix/1205-header-scope-label`; `Closes #1205`; dated lines for the withdrawn Topics request and the breakpoint |
| Conventional Commits | ✅ | co-author trailer present |
| No fabricated data | ✅ | scan above |
| New Python in `packages/` | n/a | |
| dbt / naming / keys / years | n/a | |
| Scope label matches filter | ✅ | the purpose of the PR: label = URL scope, or National; one click applies the saved town via the URL |
| Match evidence on filtered tiles | n/a | |
| Docs | ✅ | `guides/site-navigation.md` updated |
| Telemetry and logging | n/a | |
| Tests | ✅ | 5 new tests in `headerPlace.test.ts` |
| Shared libraries | n/a | |

## Test Coverage
- `npx tsc --noEmit` clean; `npx vitest run` passes 66 files / 613 tests; `npm run build` and the docs build pass.
- Playwright run with a saved Tuscaloosa, AL location:
  - `/stories/guns` before: national data, label "📍 National · Use Tuscaloosa, AL ▾".
  - `/stories/guns` after one click: URL `?state=AL&city=Tuscaloosa`, label "📍 Tuscaloosa, AL ▾", page scoped to Alabama. Checked on desktop and in the iPhone 13 menu.
  - ▾ opens the picker. Home still names the town. With no saved town the label is "National · Find your town".
  - No horizontal scroll and no API 404s.
- Header fit at 1023, 1024, 1280 and 1440px: no overflow at or above the 1024px breakpoint.

## Verdict
**approve.** Merge once required CI is green.
