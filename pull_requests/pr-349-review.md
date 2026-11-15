---
pr: 349
branch: feat/151-homepage-trending-questions
title: "feat(home): lead the homepage with trending questions, money banner second"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: feat(home): lead the homepage with trending questions, money banner second

## Summary
Closes #151. On the live homepage (`HomeV9.tsx`), a "Trending questions · {state | Nationwide}" row of up to 5 real policy questions now sits under the search box, and the money banner moves below the hero. The reviewer found that the row's links used the saved location (`locState` / `locCity`) while its label and data used the active scope. That meant a "Nationwide" question could open `/policy-questions` filtered to the saved city, which breaks the scope-label rule. Fixed in 9b897dd: the links now carry `stateCode`, plus `city` only at city level, the same pattern as `runSearch`. The same older flaw in the Browse flyouts is filed as #350. Approve with nits: nobody has looked at it in a browser yet.

## Scope of Change
- Files changed: 1 (+42 / -4)
- Areas touched: web_app
- Commits:
  - 04ee62d feat(home): lead the homepage with trending questions, money banner second
  - 9b897dd fix(home): trending-question links carry the active scope, not the saved location
- Range reviewed: `b448a7c..9b897dd`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | ✅ success (9b897dd) |
| Documentation Build | ✅ success (9b897dd) |
| Backend Tests | ⏳ running on 9b897dd |
| API Types | ⏳ running on 9b897dd |
| PR conventions | ✅ success (9b897dd) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean. Only real `entity_name` values from `/api/browse/top-items` are shown, and the row is hidden when the list is empty.
- Personal data: clean. The saved location is no longer put into these links unless it is the active scope.
- Destructive data changes: clean.

## Strengths
- It reuses the existing query, so there is no new request.
- The label names the scope the query actually used.
- The layout is correct: the row sits inside the hero section, and the banner sits between the hero and the Contested section inside `<main>`. The chips wrap on mobile.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- ~~`HomeV9.tsx:1277-1278`: the links carried `locState` / `locCity` while the label and data used `stateCode`, and `/policy-questions` starts on city scope (`PolicyQuestionsPage.tsx:75`).~~ **Fixed in 9b897dd.** Verified by tracing the code: `national` (`:470`) makes `stateCode` undefined, and the new code sets `state` only from `stateCode` and `city` only when `city` is set (`:472`, city level). The Browse flyouts have the same pattern and predate this PR; filed as #350.
- **Rendered check (coordinator, after the review):** rendered on a local Vite dev server with a throwaway mock API (questions labelled `TEST ·`, nothing committed) in headless Chrome. Desktop (1280px) and mobile (390px) lay out cleanly, and the chips wrap. With no location the label reads `NATIONWIDE` and the links carry no place. With a saved city (Tuscaloosa, AL) the label read `AL` but 9b897dd still added `city=Tuscaloosa`, because city is the active level while the list is a state-scoped query. **Fixed in the follow-up commit:** the links now carry only `state`, matching the label, and the re-check gives `/policy-questions?state=AL&question_id=…`.
### 🔵 Nits / suggestions (Minor)
- ~~The 🔥 emoji would be read aloud by screen readers.~~ **Fixed in 9b897dd** (`aria-hidden`).
- There are no tests for `HomeV9` anywhere in `web_app/src`. A test is out of scope for this PR; the behaviour is a small render guarded by real data.
- Checked in headless Chrome against a mock API (see above). It has not been seen with real data; check after deploy.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `feat/151-…`, `Closes #151`; four parts added to #151 under a dated note; follow-up #350 |
| Conventional Commits | ✅ | Co-author trailers present |
| No fabricated data | ✅ | |
| New Python in `packages/` | n/a | |
| dbt for transformations | n/a | |
| Naming / Keys / Calendar years | n/a | |
| Scope label matches filter | ✅ | After 9b897dd: label, data and link params all use the active scope |
| Match evidence on filtered tiles | n/a | Plain browse (no content filter) |
| Docs | n/a | |
| Telemetry and logging | n/a | |
| Tests | ⚠️ | No frontend test for HomeV9 (none exist) |
| Shared libraries | n/a | |

## Test Coverage
- `cd web_app && npx tsc --noEmit`: clean on 9b897dd.
- `npx eslint src/pages/HomeV9.tsx`: one `react-hooks/exhaustive-deps` warning at line ~702, there before this PR.
- No automated UI test. Rendered at desktop and mobile widths in headless Chrome against a mock API; links checked with and without a saved location.

## Verdict
**approve-with-nits.** Rendered and link-checked locally. Merge when CI is green.
