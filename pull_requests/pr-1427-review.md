---
pr: 1427
issue: 1426
verdict: approve
---

# PR #1427 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `feat/1426-page-close-button`, `Closes #1426`; four parts present.
- **Scans:** no secrets, no fabricated data, no personal data, no data changes.
- **Correctness:** the destination logic (`lib/pageClose.ts`) goes back only when the previous history entry (tracked by router index) is ours and the scope matches; otherwise it goes home or to the previous page with the current scope applied, so the scope is never dropped. Escape is skipped when a dialog, field or map card has focus. Stories and Settings keep their own Close.
- **Verification:** vitest (9), tsc, and a Playwright check at 360, 412 and 1440 on 18 pages, plus the story caption-off-the-rule assertion.
- **Docs:** UI-only; no contract page changes.

No blocking findings.
