---
pr: 1169
branch: fix/1138-story-nav-consistent
title: "fix(stories): Next and Back buttons are consistent on every desktop story screen"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: fix(stories): Next and Back buttons are consistent on every desktop story screen

## Summary
Every story screen now renders the one `ScreenNav` (the question and verdict screens included, through a `primary` slot), and on wide screens the row is pinned to the bottom of the left column so Back and Next keep one place and size. A new Playwright check steps through `/stories/data-centers` (national and `?state=AL`) at 1440×900: 11 of 12 screens were out of line on main, all line up on the branch. Two reviewer findings were fixed in b7290bfd. The remaining notes are minor. Approve with nits.

## Scope of Change
- Files changed: 6 (ScreenNav.tsx, StoryVoteScreens.tsx, stance.css, e2e/story-nav.check.mjs, guides/data-stories.md, this review)
- Areas touched: web_app, web_docs
- Commits: a1a8a05d fix(stories): Next and Back sit in one place and size…; b7290bfd fix(stories): pinned story nav covers scrolled text…
- Range reviewed: `ff94e85f..b7290bfd`

## CI Status
| Check | Status |
|---|---|
| Frontend Build / Documentation Build / Backend Tests / API Types | read on the head commit before merge |

## Scans (secrets, fabricated data, personal data, destructive data changes)
All clean. The e2e check intercepts the vote POST and answers it from the real results GET, so it stores no vote and invents no figures.

## Strengths
- One nav component, as the Contract asks; a measured before/after check rather than eyeballing.
- Phones untouched: the pinned rule is scoped to `data-mode='pinned'`.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- stance.css pinned rule: the transparent absolute nav let a tall, scrolling left column show through the buttons. Verified from the CSS (`.stance-left` is the scroller, the nav anchors to `.stance-grid`). **Fixed** in b7290bfd with a `var(--paper)` background.
### 🔵 Nits / suggestions (Minor)
- StoryVoteScreens.tsx QuestionScreen: `nextLabel ?? 'Next'` produced the name "Next: Next". **Fixed** in b7290bfd (ScreenNav names it "Next").
- QuestionScreen's unanswered "Skip, I'd rather read first" is a text link in Next's spot, not the pill. The story no longer has a question screen (#950: `kind === 'question'` is not in the 12 screens), so this is latent; the check can't reach it.
- Reduced-motion desktop readers get `stacked` mode (useActs), so the row stays in the flow for them, as before.
- Verdict `onNext={() => {}}` is never attached (no Next without `nextLabel`); making `onNext` optional would be cleaner.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | `fix/1138-…`, `Closes #1138`, issue has the four parts |
| Conventional Commits | Yes | co-author trailer present |
| No fabricated data | Yes | |
| New Python in packages/ | n/a | |
| dbt / naming / keys / years | n/a | |
| Scope label matches filter | Yes | unchanged; `?state=AL` path checked |
| Match evidence | n/a | |
| Docs | Yes | guides/data-stories.md, story navigation |
| Telemetry | n/a | |
| Tests | Yes | e2e check fails on main (11/12), passes on branch |
| Shared libraries | n/a | |

## Test Coverage
Run locally: `node e2e/story-nav.check.mjs` (before: 11 screens out of line; after: all line up, both paths), `npx vitest run` story/stance tests (21 files, 245 passed), `npx tsc --noEmit` clean, `npm run build` passed.

## Verdict
After main moved (#1164), main was merged in (a20c0b83) and the dropped `ScreenNav` import restored (cc351f76); the check re-run on the merged tree: 11 screens per path (main dropped one), all line up; vitest 20 files / 255 passed; build passed.

approve-with-nits. Nothing blocking; merge once required CI is green.
