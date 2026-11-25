---
pr: 990
branch: feat/989-story-conclusion
title: "feat(web_app): data stories lead with a data-gated conclusion; Start stays in view"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: coordinator
head_sha: see branch head
verdict: approve-with-nits
---

# PR Review: data stories lead with a data-gated conclusion; Start stays in view

Closes #989.
- **Headline:** the conclusion is a claim, so it is gated on the national speaker record (2:1, at least 10 speakers), and a basis line gives the real counts. It falls back to the neutral title. The gate is tested (on, under 2:1, too few speakers, nobody on the side).
- **Start:** in view on laptop and phone, measured in a browser.

- 🔴 None. 🟡 None.
- 🔵 Nits:
  - The headline is a strong editorial line; the basis line and the gate keep it tied to the record.
  - The drafts for other topics live only in docs.
- Scans: no secrets, no fabricated data (the claim is gated and its counts are live), no personal data.
- Tests: vitest 407; `tsc` and eslint clean.

**approve-with-nits**: merge when the required checks are green.
