---
pr: 253
branch: feat/242-core-3-1-meeting-model
title: "feat(ingestion): one meeting model across platforms (CORE-3.1)"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: maintainer session (self-review, verified by tests and ruff)
verdict: approve-with-nits
---

# PR Review: feat(ingestion): one meeting model across platforms (CORE-3.1)

| Attribute | Value |
|---|---|
| Epic | [CORE · Meetings, Legislation and Officials](https://github.com/getcommunityone/open-navigator/issues/235) |
| User story | [CORE-3.1 · One meeting model across platforms](https://github.com/getcommunityone/open-navigator/issues/242) |

## Summary

This PR adds `ingestion.meetings`, a library module with three parts. `Meeting` holds the agenda, recording,
transcript and minutes in fixed slots for every platform. Two reference adapters fill it: `youtube` from LocalView
rows and `legistar` from Web API events. And `adapter_for()` raises `UnsupportedPlatformError` instead of falling
back to a generic scraper, with `coverage_report()` listing what each run leaves uncovered. It meets both of #242's
"Done when" lines, with tests. Nothing existing changes: no table, API or UI, and `MeetingEvent` is untouched. The
decision is written up in `web_docs/docs/development/meeting-model.md`. The verdict is approve, with two nits.

## Scope of Change

- Files changed: 7 (+~640): the module (4 files), one test file, one docs page and this review
- Areas touched: `packages/ingestion` (new module), `web_docs/docs/development`
- Commits: 086f55d feat(ingestion): one meeting model across platforms (CORE-3.1); b6165cd fix(ingestion): treat
  pandas missing markers as missing in the meeting model
- Range reviewed: `main` (8204c98) to b6165cd

## CI Status

Checked green on the head before merging (Frontend Build, Documentation Build, Backend Tests, API Types). CI's
Backend Tests job compiles and imports but doesn't run pytest, so the tests were run locally: 15 passed, and
`ruff check` passes.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data in a served path:** clean. Nothing is served yet. The model never fills a missing artifact, and
  an unknown state name gets no code rather than a guess from its first letters. The test fixtures (a LocalView row,
  a Legistar event) live only in the test file.
- **Personal data:** clean. The fixtures use made-up places.
- **Destructive data changes:** none.

## Strengths

- It turns the silent-empty failure into an error that names the platform, the jurisdiction and what is supported,
  and the coverage report makes the gap visible in every run.
- `to_record()` gives every platform the same keys, and a test pins that.
- It adds no dependency. LocalView's own module pulls in pandas, SQLAlchemy and the database client, so the
  meetings module keeps its own exact state table.
- The follow-up it found, `get_scraper_class()` falling back to a missing `GenericScraper`, is filed as #252
  instead of left in a comment.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

1. **Only ISO-style dates parse.** `parse_meeting_date` reads dates, datetimes, pandas Timestamps and ISO strings.
   Anything else becomes `None`. That's honest, but a US-style "10/06/2026" from a council site would lose its date.
   CORE-3.2 should check the baseline councils' formats and widen the parser if needed.
2. **The registry is module-global.** Adapters register when the module is imported. That's fine for two built-in
   adapters, but a test that registers a throwaway adapter would leak into others. A context manager that restores
   the registry would help once a third adapter arrives.

## Repo-Rule Compliance

| Rule | Status |
|---|---|
| Issue first, four parts, Contract as a dated line (AGENTS.md) | ✅ #242, Contract dated 2026-11-13 |
| Branch `<type>/<issue>-<slug>`, `Closes #<issue>` | ✅ `feat/242-core-3-1-meeting-model`, `Closes #242` |
| Epic and User story links in the PR (the owner's PI4 rule) | ✅ Attributes table in the PR and in this review |
| Test first | ✅ the tests failed at import before the module existed; the pandas test failed before its fix |
| New Python in `packages/`, not `scripts/` | ✅ `packages/ingestion/src/ingestion/meetings/` |
| No Fabricated Data | ✅ |
| Decisions written down (`web_docs/docs/development/`) | ✅ `meeting-model.md` |
| Follow-ups become issues | ✅ #252 |
| Conventional Commits | ✅ |

## Test Coverage

`packages/ingestion/tests/test_meetings_model.py` has 15 tests:

- An artifact needs a url or text.
- The meeting key is stable per platform and id.
- Every platform gives the same record keys.
- LocalView gives the recording and transcript, and no agenda.
- Missing values stay missing, including NaN, `pd.NA` and `NaT`, and an unknown state gets no code.
- Rows or events without an id are rejected.
- Legistar gives the agenda and recording, and no minutes.
- The supported list is right, and lookups ignore case and spaces.
- Granicus, blank and missing platforms each fail loudly.
- The coverage report counts what's supported and lists what isn't.

## Verdict

**Approve with nits.** Merge when the four required checks are green on the head.
