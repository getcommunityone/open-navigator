---
pr: 781
branch: fix/778-shared-channel-upsert-ownership
title: "fix(youtube): keep a shared-channel video's place when another town re-crawls it"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: python-packages-specialist subagent (read-only) and coordinator
verdict: approve
---

# PR Review: fix(youtube): keep a shared-channel video's place when another town re-crawls it

## Summary
Closes #778. The loader's upsert overwrote `jurisdiction_id` on every refresh, so on a channel linked to several towns, a video whose title names no town moved to whichever town ran last. The geo columns now keep the stored place on a shared channel unless the incoming title names the jurisdiction being refreshed. The reviewer's Important finding was that stale or placeholder ids would be frozen. It is fixed in the second commit: the rule now applies only to shared channels, never keeps a NULL or `c-XX-nnnnn` id, and matches GEOIDs only on 5 or more trailing digits. Approve.

## Scope of Change
- Areas: packages (scrapers), web_docs
- Commits: 858ccae4 (upsert ownership), plus the follow-up commit that scopes it after review
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| Required checks | pending on the new head at time of writing |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean. The integration test reads the password from the environment.
- Fabricated data: clean (no `api/` or `web_app/` changes).
- Personal data: clean.
- Destructive data changes: none. The upsert keeps more data than before, and the integration test writes only to a TEMP table in a rolled-back transaction.

## Findings
### 🔴 Blocking
None.
### 🟡 Should fix
- ~~Stale or placeholder ids frozen by the keep rule (`c-AL-01125` → `tuscaloosa_0177256` never corrected; the #501 name cleanup skipped).~~ **Fixed:** placeholder ids are never kept, and the rule applies only when the loader marks the channel as shared (it already looks up the channel's siblings). The warehouse has 0 placeholder ids and 0 ids without a 5+-digit suffix today. Covered by `test_upsert_against_postgres`.
### 🔵 Nits
- ~~The suffix match compared any trailing digits (`city_1` = `school_district_1`)~~. **Fixed:** it now requires 5 or more digits.
- ~~Tests didn't exercise the SQL~~. **Fixed:** an opt-in `test_upsert_against_postgres` (`OPEN_NAVIGATOR_PG_TESTS=1`) runs the real ON CONFLICT on a TEMP table with six cases, and it passes locally.
- Coordinator caught a bug in its own edit: `.format` inserts the keep fragment verbatim, so it must use single braces. A test now asserts `"{{" not in` the fragment.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | `fix/778-...`, `Closes #778`; the issue has all four parts |
| Conventional Commits | Yes | |
| New Python in `packages/` | Yes | |
| Docs | Yes | "Ownership on re-crawl" bullet in `youtube-discovery.md` |
| Tests | Yes | New tests fail on `main`; the #501 test patterns are updated with the behaviour unchanged |
| Shared libraries | Yes | `pytest packages/scrapers/tests`: 351 passed, 2 skipped |

## Test Coverage
- Unit: parameters, the SQL fragment, and the guard on all six geo columns.
- Integration (opt-in, run locally): neutral title kept; titled move; wrong town re-crawl kept; same GEOID normalized; placeholder replaced; non-shared channel keeps the old behaviour.

## Verdict
approve. Merge when required checks are green.
