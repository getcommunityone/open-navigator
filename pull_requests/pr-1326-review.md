---
pr: 1326
issue: 1325
verdict: approve
---

# PR #1326 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `fix/1325-story-scroll-jump`, `Closes #1325`; the issue has all four parts.
- **Scans:** no secrets, no fabricated data, no personal data, no data changes.
- **Correctness:**
  - `useActs` (snap mode) holds back active-screen changes while a touch or wheel gesture is inside an overflowing scroller or a `role="dialog"` block, or while a modal is open, and puts the page back on the screen it rests on. Moves the reader asks for set `programmatic` and are not held back.
  - The wheel handler never pages from inside a scroller or modal, and a modal gets `preventDefault`; the screens' scrollers have `overscroll-behavior-y: contain`, so reaching a block's end does not chain to the page.
  - `useScreenKeys` ignores keys while a modal is open, so arrows and Space in the drill sheet no longer page the story.
- **Tests:** `e2e/story-scroll.check.mjs` fails before the fix (4 failures at Pixel 7 size) and passes after; vitest (stance) and tsc pass.
- **Docs:** guides/data-stories.md snap paragraph updated.
- **Behaviour change to note:** on a long screen the wheel/vertical swipe no longer carries on to the next screen at the block's end; Next, a key, a segment or a sideways swipe does.
- **Scope change (added):** `useStoryScreens` treats a change of place with no new `?screen=` as a reset: lands on the first screen (Overview), rewrites `?screen=`, and returns the screens' scrollers to the top. Covers the map pick, place picker and header National. The e2e check has both cases (map pick; National from `?screen=sites`).
