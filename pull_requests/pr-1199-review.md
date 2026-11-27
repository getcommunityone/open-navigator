---
pr: 1199
branch: fix/1192-story-nav-simplify
title: "fix(stories): one exit, one progress indicator, no floating Next on the cover; dumbbell on the Overview"
author: johncbowyer
reviewed_at: 2026-11-26
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: one exit, one progress indicator, no floating Next on the cover; dumbbell on the Overview

## Summary
This PR simplifies navigation on the story pages.

- **Data Center Story cover:** Start is the only forward action there. The floating Next and the phone bar's Next stay hidden while Start is in view.
- **Progress:** each device has one progress indicator. On wide screens it is the segmented bar, whose segments are now buttons; the numbered rail and the thin fill bar are removed. On phones it is the bottom bar.
- **Exit:** the × is removed. "← Data stories" is the single exit, on topic stories too.
- **Topic-story copy:** the basis line reads "Then Ohio, …" instead of "Next: Ohio, …", and the coverage line appears once.
- **Period dumbbell:** it moves to the Overview screen. It now has explicit loading, failed and not-available states instead of rendering nothing.

The reviewer found nothing Critical. One Important wording issue (a claim of missing data in the dumbbell's empty state) and the Minor items are fixed in a7dd7b68. Required CI was green on 41a834ac and is re-running on the head commit. Verdict: approve with nits.

## Scope of Change
- Files changed: 12 (+244 / -210), web_app and web_docs only
- Areas touched: web_app (DataStory, TopicStory, stance components, stance.css, storyCaption, e2e check), web_docs (guides/data-stories.md)
- Commits:
  - 3ac325b6 fix(stories): one exit, one progress indicator and no floating Next on the story cover
  - dbcefee6 chore: merge origin/main into fix/1192-story-nav-simplify
  - 41a834ac feat(stories): period dumbbell on the Data Center Story's Overview, with an honest empty state
  - a7dd7b68 fix(stories): neutral dumbbell empty-state wording, no counted-line shift while the caption loads
- Range reviewed: `ee3e69b9..HEAD`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | pass (41a834ac) |
| Documentation Build | pass (41a834ac) |
| Backend Tests | pass (41a834ac) |
| API Types | pass (41a834ac) |
| PR conventions | pass |
| Docker Build Test | skipped (no Docker changes) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean.
- **Fabricated data:** clean. No numbers are added. The dumbbell's new states are explicit empty and unavailable messages, and figures still come from the API.
- **Personal data:** clean.
- **Destructive data changes:** clean. There are no data or warehouse changes.

## Strengths
- `onCover` is driven by an IntersectionObserver on the real Start button. Every hook runs before the early return. A deep link (`?screen=`) flips it to false on the first callback, and a change of `wide` re-observes.
- The progress segments are a named `nav` holding an `ol` of buttons ("3 of 11: Sites", with `aria-current="step"` and a focus ring).
- No dangling selectors remain for the removed dots, top bar or close button.
- `e2e/story-nav.check.mjs` now checks the cover (no floating Next beside Start, one progress indicator, no ×) and then presses Start. On main it was failing on every screen because the cover came first.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- **Fixed in a7dd7b68.** `DumbbellChart.tsx`: the `rows=[] && hidden_rows=0` branch claimed the recorded-meeting counts were missing. The same response also comes back when the topic has no meetings in either year.
  - The wording now covers both cases neutrally.
  - A reason flag from the API is follow-up #1202.

### 🔵 Nits / suggestions (Minor)
- `DataStory.tsx` `onCover` observer: `rootMargin` is computed once from the header and title-bar heights.
  - If the title bar later reflows (a place change wraps the sentence), the hide/show threshold is off by a few pixels.
  - On a very short viewport where Start is below the fold, the floating Next can show on the cover.
  - Both are cosmetic and left as is.
- **Fixed in a7dd7b68.** `TopicStory.tsx`: the coverage line rendered while the caption was pending, then disappeared. It now waits for the caption.
- **Fixed in a7dd7b68.** `data-stories.md`: the guide said "Twelve screens". It now says up to eleven and that "N of M" counts only the screens shown.
- `ProgressPips.tsx`: `title` repeats `aria-label`. This is harmless, and the segments are 24px tall (wide screens only).
- **Tests:** there are no new unit tests. The behaviour is covered by the updated Playwright check (`story-nav.check.mjs`) and the updated `storyCaption.test.ts`.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | yes | #1192 has all four parts, plus a dated comment for the dumbbell scope; branch `fix/1192-story-nav-simplify`; `Closes #1192`; follow-up #1202 |
| Conventional Commits | yes | co-author trailer on each |
| No fabricated data | yes | explicit empty states |
| New Python in `packages/` | n/a | |
| dbt for transformations | n/a | |
| Naming / Keys / Calendar years | n/a | |
| Scope label matches filter | yes | the dumbbell gets `storyScopeLabel(scope)` and queries the same `stateCode`; at city scope it says it is drawn by state or town and points to All of [state]; the exit link keeps `?state=` |
| Match evidence on filtered tiles | n/a | |
| Docs | yes | `web_docs/docs/guides/data-stories.md` updated in this PR |
| Telemetry and logging | n/a | |
| Tests | partial | Playwright check plus storyCaption test; no new unit test for the cover hide |
| Shared libraries | n/a | |

## Test Coverage
Run locally against Vite on :5291 with the local API:
- `node e2e/story-nav.check.mjs`: cover ok, all screens line up (national and AL).
- A Playwright audit of first-screen navigation controls at 1366x768, 1440x900 and iPhone 13. After the change: no ×, no floating Next or bar Next on the cover, one progress indicator, Start and Next story in the first screen.
- A stubbed `period-compare` with no rows renders the empty state.
- `npx tsc --noEmit`, `npx vitest run` (596 passed), `npm run build`, and the docs build all pass.

## Verdict
Approve with nits. Nothing is blocking. Merge once the required CI passes on the head commit.
