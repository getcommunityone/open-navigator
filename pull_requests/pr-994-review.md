---
pr: 994
branch: feat/993-story-title-conclusion
title: "feat(web_app): story title states the place's conclusion"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: coordinator
head_sha: see branch head
verdict: approve-with-nits
---

# PR Review: story title states the place's conclusion

Closes #993.
- **Sentiment:** gated on the scope's own speakers.
- **Fact:** the scope's real meeting count.
- **Question:** when nothing is on record.
- **Basis:** a line under the title gives the numbers. No claim without data.

- 🔴 None. 🟡 None.
- 🔵 Nits:
  - "talked about … in N meetings" counts meetings where a data center came up, which the basis line states.
  - The sentiment verb is per story (`verb`).
- Scans: none.
- Tests: vitest 411; `tsc` and eslint clean; browser checks for national, WA, TX and Tuscaloosa.

**approve-with-nits**: merge when the required checks are green.
