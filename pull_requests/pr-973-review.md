---
pr: 973
branch: feat/972-meeting-dot-video
title: "feat(web_app): meeting dots preview a thumbnail and play the recording in a modal"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: general-purpose subagent (read-only, two passes) and coordinator
head_sha: see branch head
verdict: approve-with-nits
---

# PR Review: feat(web_app): meeting dots preview a thumbnail and play the recording in a modal

## Summary

Closes #972. A meeting dot previews its YouTube thumbnail on hover or focus, and click, Enter or Space plays the recording in a dialog from the quoted moment. The iframe exists only while the dialog is open.

The first independent pass said **request-changes**. Every Blocking and Should-fix finding is fixed on the branch, and
the second pass says **approve-with-nits**. The CI bot's heuristic auto-review is superseded by this file.

## Findings and their fixes

### 🔴 Blocking (fixed)
1. **Arrow keys in the dialog moved focus to a dot behind it.** Portal events bubbled to the grid's key handler. **Fixed:** the dialog renders outside the grid and stops key propagation.

### 🟡 Should fix (fixed)
- **The story scrolled under the open dialog.**
  - Fixed: `html` and `body` are locked; `data-lenis-prevent` is set; wheel and touch are blocked on the backdrop; story keys are stopped while it is open; the dialog takes focus when its text is clicked.
  - Checked in a browser: the page moved 0px.
- **The dialog couldn't scroll in short windows** (second pass). Fixed: only the backdrop blocks wheel and touch; the dialog has `overscroll-behavior: contain`.
- The focus-restore side effect left the state updater.
- The caption says "hover or focus".
- `altKey` counts as a modifier click.

### 🔵 Nits (open)
- While the dialog is open, story keys are stopped for every element. Native activation still works, but a future `onKeyDown` inside the dialog wouldn't fire.
- Desktop scrollbar shift when the page locks (`scrollbar-gutter` could fix it).

## Tests
- vitest: 8 new tests; the full suite (388) green. `tsc` is clean.
- Browser:
  - No YouTube request before a hover; one thumbnail on hover.
  - The dialog plays from 6:57.
  - Escape removes the iframe and returns focus to the dot.

## Scans

- Secrets: clean.
- Fabricated data: clean.
- Personal data: none.
- Destructive changes: none.

## Verdict

**approve-with-nits**: merge when the required checks are green.
