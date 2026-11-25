---
pr: 998
issue: 997
verdict: approve
---

# PR #998 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `fix/997-story-bounce`, `Closes #997`; the issue has all four parts.
- **Scans:** no secrets, no fabricated data, no personal data, no data changes.
- **Correctness:**
  - The `onActive` guard compares `window.location.pathname` with the path captured when the story mounted, so a scroll update arriving after navigation can't write `?screen=`. `alive` resets when `story` changes, so it doesn't block moving from one story to another.
  - `isRefreshing` is read off ScrollTrigger at runtime. gsap sets it for the whole `refreshAll` pass. `paintStates` still runs and only skips the active write. After a refresh, the landed `activeRef` stands until the next real scroll.
- **Verification:** browser reproductions were run before and after (bounce 12/12 fixed, deep link fixed), trackpad paging is unchanged, and tsc and the build pass.
- **Docs:** no contract change, so no docs page is needed.

No blocking findings.
