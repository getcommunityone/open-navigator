---
pr: 832
branch: fix/831-meeting-type-from-title
title: "fix(scrapers): type committee, commission, work session and briefing videos from their titles"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: coordinator
verdict: approve-with-nits
---

# PR Review: fix(scrapers): type committee, commission, work session and briefing videos from their titles

## Summary
Replaces the scraper's six substring checks with a whole-word classifier over a documented list of types, and adds a
dry-run-first command to re-type rows already stored as `Other`. Existing answers for council, planning and school
board titles are preserved and tested. The command was run against a real PostgreSQL with test rows. Approve with
nits: one downstream effect on channel classification is worth knowing about, and the command has not run on the real
warehouse.

## Scope of Change
- Files changed: 4 (excluding this review)
- Areas touched: packages (scrapers) / web_docs
- Commits: `1418dad5` fix(scrapers): type committee, commission, work session and briefing videos from their titles
- Range reviewed: `origin/main...origin/fix/831-meeting-type-from-title`

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | Read on the commit that carries this file before merging. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets, fabricated data, personal data: clean.
- Data changes: the re-type command updates `bronze.bronze_event_youtube.meeting_type` outside dbt. That column is
  written by this package's own loader, the command is a dry run unless `--apply`, it resolves only the local warehouse,
  and it touches only untyped rows. Not destructive: a re-typed row could be set back to `Other` by hand, and no row
  with a real type is changed. 🟡-level care, not a blocker.

## Strengths
- The old answers are pinned by tests before anything new is added.
- The update statement repeats the "still untyped" condition, so a row typed between the read and the write is not
  overwritten.
- The database rule is tested with the production variable set.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- **Channel classification will shift slightly.** `classify_channel_purpose.is_civic_meeting_type` counts a video as
  civic when its `meeting_type` matches council, board, commission, committee and similar. Videos that were `Other`
  and become `Committee`, `Commission` or `Board` now count as civic, so a channel's civic share can rise and fewer
  channels are judged junk. That is the correct direction (they are civic meetings), but it is a behaviour change
  beyond the label. `Work Session`, `Briefing`, `Public Hearing` and `Authority` are not in that pattern and stay
  uncounted, as `Other` was.
- "hearing" and "board" are broad words; "board game" is excluded, other false friends are not. A wrong type is a wrong
  label, not a wrong skip, since #829 no longer drops on type alone.
- The local-warehouse rule now exists in three modules (loader, promote, here). Worth one shared helper in
  `core_lib.db` later.
- The 17 failing tests in `packages/scrapers/tests` in the review container are missing-library failures that fail
  identically on `main`.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #831 with the four parts; branch `fix/831-meeting-type-from-title`; `Closes #831` |
| Conventional Commits | Yes | |
| No fabricated data | Yes | A title that names nothing stays `Other`; nothing is guessed |
| New Python in `packages/` | Yes | A `python -m scrapers.youtube.meeting_type` CLI |
| dbt for transformations | Yes | An ingestion-time classification in the package that owns the column |
| Docs | Yes | `web_docs/docs/development/meeting-type-label.md` |
| Telemetry and logging | Yes | loguru |
| Tests | Yes | 32 cases |
| Shared libraries | Yes | The scrapers suite was run on the branch and on `main`: the same tests fail on both |

## Test Coverage
`pytest packages/scrapers/tests/test_meeting_type_831.py`: 32 passed. The command ran on a scratch PostgreSQL 16:
dry run wrote nothing; `--states AL --apply` re-typed only Alabama's untyped rows; typed rows and non-meeting titles
were untouched. Not run: the real warehouse.

## Verdict
approve-with-nits. Nothing must change first. Run the command as a dry run and read the per-type counts before `--apply`.
