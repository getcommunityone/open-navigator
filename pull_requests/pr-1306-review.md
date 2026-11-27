---
pr: 1306
issue: 1293
verdict: approve-with-nits
---

# PR #1306 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `feat/1293-said-people-positions`, `Closes #1293`; the issue has all four parts. The decisions split was added mid-task on owner feedback and is in the PR body and docs.
- **Scans:** no secrets. No fabricated data: every name, chip and count comes from `meeting_passage_speaker`, `meeting_comment`, `topic_meeting_lean`, `event_decision` or `data_center_decision`; no chip without a source, and a meeting-level position is labelled as the meeting's. Test rows are marked as stand-ins; the two Alabama headlines and statements are quoted verbatim from the record.
- **Privacy (AGENTS.md):** residents are "First L." (re-cut in `speaker_fields` / `commenter_names`); `meeting_comment` names are filtered for `possible_minor`, `is_public_comment` and school-board meetings (school_district jurisdiction, or a jurisdiction or title naming a school board, the `meeting_speaker_intro` rule). No sensitive traits inferred. Test asserts the SQL keeps these filters.
- **Correctness:**
  - `/meetings` keeps its old shape and default order; new fields are optional, and a serving copy without the tables falls back to the plain list (covered by the existing tests, now running through the fallback).
  - Counts run only with the first page (`offset == 0`); later pages fetch the total only. National guns (7,684 meetings) answers in about 0.4 s locally; the event_meeting lookup is per page, not per row (a per-row lateral took 36 s and was removed).
  - `said_position` never lets a five-position reading contradict the lean side; tests cover each source.
  - Decision relevance: off-topic wording wins, then named policy, then permit-like wording needs a public side at that meeting, then anything else needs a body action. The Shelby reallocation and Wetumpka sale permit are in passing; tests pin both.
- **Verification:** pytest 49 passed (new `tests/test_api_topic_said.py`); vitest 791 passed; `tsc --noEmit` clean; Playwright at Pixel 7 and 1440 on GA fluoridation, guns (national, AL) and data centers AL.
- **Docs:** `web_docs/docs/guides/data-stories.md` documents both changes, the API fields and the rules.

Nits (non-blocking):
- `topic_meeting_lean` reads two Fayette County virtual plant tours as votes, so their cards show a vote chip; logged as #1305.
- `api.types.ts` is not regenerated here; the API Types CI job regenerates it, and the hand-written types in `api/topics.ts` / `api/dataCenters.ts` match.
- Rule lists cover the seven topics with their own position words; other topics rely on the meeting reading only, which keeps more of their decisions in passing.

No blocking findings.
