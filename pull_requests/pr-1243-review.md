---
pr: 1243
branch: fix/1234-story-start-titles-swipe
title: "fix(stories): Start skips the cover, short conclusion titles, swipe and phone Back"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve
---

# PR Review: fix(stories): Start skips the cover, short conclusion titles, swipe and phone Back

## Summary
The PR applies the owner's feedback from 26 and 27 Nov 2026 to the Data Center Story and the home story cards:
- Start opens the story on the Overview.
- Titles are the short conclusion only, with no counts and no "AI reading" text. A place too thin of its own gets the broader conclusion; its own facts go in the basis line, and its place control moves to the subhead.
- The Overview never repeats the title.
- Swipe left and right moves between screens on touch screens.
- The phone bottom bar has a Back button.
- Close (×) is in the top right and goes home with the place kept.
- One green Next is fixed at the bottom right; on the last screen it becomes a quiet Done.
- "Next story" buttons are gone from the story and the home cards.
- #1208: a progress-segment jump made while the page is still growing now re-aims at its screen.

A read-only reviewer found one Important issue (an unknown place count printed as "no meetings") and six Minor ones. All were fixed and re-verified. Unit tests, the build, the docs build and both Playwright checks pass. Verdict: approve.

## Scope of Change
- Files changed: 30 (+1,299 / -264, excluding generated files)
- Areas touched: web_app, web_docs
- Commits:
  - c3fae6f2 fix(stories): Start skips the cover, short conclusion titles, swipe and phone Back
  - 81111922 fix(stories): Close top right, one fixed Next bottom right, no Next story buttons
  - 4adce331 docs(pr-1243): auto-write rubric review [skip review] (bot; replaced by this file)
  - merges of origin/main (conflicts with #1248's "gun control" wording, resolved by keeping both)
- Range reviewed: `merge-base(origin/main)..HEAD`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | see PR checks on the head commit (pending at writing) |
| Documentation Build | see PR checks (pending at writing); local `npm run build` passes |
| Backend Tests | see PR checks (no Python changed) |
| API Types | see PR checks (no API changed) |
| PR conventions | see PR checks; issue #1234 has the four parts |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean after fixes.
  - Every title and basis number comes from `caption-facts`.
  - An unknown place count (`meetings: null`) used to read as "has no meetings on record yet". It now says nothing (review finding 1).
  - Test values are marked as stand-ins in the test files.
- Personal data: clean. No personal data is stored or logged.
- Destructive or bulky data changes: none.

## Strengths
- One title system covers the home card, the story header and the `/stories` cards (`pickCaption`). The Overview reuses `distinctHeadline`, which a topic story can reuse too.
- Shared pieces are ready for the topic-stories work (#1224): `useSwipeNav`, `StoryNextButton`, `StoryClose` and `storyStartHref` / `storyCloseHref`.
- The swipe needs a horizontal-dominant gesture and never calls `preventDefault`. It skips maps, charts, dialogs and fields, and is unit-tested (`swipeDirection`).
- The Playwright coverage is real: 90 checks at Pixel 7, iPhone 13 and 1440x900.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **Fixed.** `storyCaption.ts`, `placeCount`.
   - Problem: `facts.meetings ?? 0` turned an unknown count into "X has no meetings on … on record yet".
   - Verified against `TopicCaptionFacts.meetings: number | null`.
   - Fix: `placeCount` takes `null` and returns `''`. Both wider bases now filter empty parts.

### 🔵 Nits / suggestions (Minor)
2. **Fixed.** `DataStory.tsx` place control when the title names another place.
   - Problem: on the story page (unlike home) the title's place blank still showed a control reading the other place, for example a national title naming the leading state.
   - Fix: the blank becomes plain text, and the subhead carries the scope's control, on its name or as a "Showing [place]" lead.
3. **Fixed.** `DataStory.tsx` `goTo` set an `intent` for a move to the screen already shown, which might never settle and clear it. Such a move now sets no intent.
4. **Fixed.** Swipe left on the last screen called a no-op `goTo(n-1)`. It now returns early.
5. **Fixed.** `positionClaim` for generic topics read "most meetings on X mostly opposed it". It now reads "The public mostly opposed X in N of M meetings where it spoke."
6. **Fixed.** Stale header and doc comments in `storyCaption.ts` still described the "(AI reading)" count titles.
7. **Fixed.** `StoryBottomBar` showed Back with an empty label ("Back: "). It now needs a non-empty label.

Not in this PR, logged as #1236: the home box map's hover cards and captions (`StoryStatesMap.tsx`, another agent's file) still say "AI reading of N meetings". The legend's disclosure stays by design.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `fix/1234-…`; `Closes #1234`, `Closes #1208`; #1234 has all four parts; follow-up #1236 |
| Conventional Commits | ✅ | Both commits use `fix(stories): …` with the co-author trailer |
| No fabricated data | ✅ | See the scans (finding 1 fixed) |
| New Python in `packages/` | n/a | No Python |
| dbt for transformations | n/a | |
| Naming / Keys / Calendar years | n/a | |
| Scope label matches filter | ✅ | The place control always names the scope in effect (finding 2). Close and Start carry `?state=&city=`. The story URL keeps `?screen=` |
| Match evidence on filtered tiles | n/a | |
| Docs | ✅ | `guides/data-stories.md` and `development/story-captions.md` record both decisions with dates and the owner's words |
| Telemetry and logging | n/a | |
| Tests | ✅ | Updated vitest cases for titles, bases, the Overview, captionPlace and swipe. New `e2e/story-flow.check.mjs`. `story-nav.check.mjs` updated |
| Shared libraries | n/a | |

## Test Coverage
Run locally on the merged head:
- `npx tsc --noEmit`: clean.
- `npx vitest run`: 707 passed, 1 skipped.
- `npm run build`: passes.
- Docs `npm run build`: passes.
- `node e2e/story-nav.check.mjs` (national and AL): all screens line up.
- `node e2e/story-flow.check.mjs`: 90/90.

Both e2e checks ran against this worktree's Vite on :5311, proxied to the local API on :8001.

Not covered by an automated check: real-finger swipes on a physical phone. The check dispatches touch events.

## Verdict
approve: nothing blocking. Merge once the required CI checks are green.
