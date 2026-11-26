---
pr: 996
branch: feat/995-home-stories-first
title: "feat(web_app): home opens on Data Stories; search second; thesis under Impact"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: coordinator
head_sha: see branch head
verdict: approve-with-nits
---

# PR Review: home opens on Data Stories; search second; thesis under Impact

Closes #995. The layout follows the owner's mockup.
- **Honesty:** the quote card shows a real speaker's words labelled with their side, or a verbatim meeting passage, always with the place, date and source link. A state with no data has no pin or card.
- **Gating:** the headline is gated (#989).
- **Fix found along the way:** the positions request was asking for 50 quotes per side, above the API's maximum of 10, which returned a 422.

- 🔴 None. 🟡 None.
- 🔵 Nits:
  - At rest the card prefers a speaker quote, which makes it an "against" quote while those dominate the record. The card says the side.
  - Search is now an `h2`, so the page has one `h1`.
- Scans: none.
- Tests: vitest 413; `tsc`; browser checks on desktop and phone.

**approve-with-nits**: merge when the required checks are green.
