---
pr: 830
branch: fix/829-other-is-not-non-meeting
title: "fix(llm): load meetings the scraper typed Other when something says they are meetings"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: coordinator
verdict: approve-with-nits
---

# PR Review: fix(llm): load meetings the scraper typed Other when something says they are meetings

## Summary
The loader skipped every video the scraper typed `Other`, and the scraper types anything outside six title keywords
that way, so committee meetings, commissions, work sessions and briefings were dropped as "Not a meeting". The PR
keeps such a video when a person, the Jev keep-score or the title says it is a meeting, and leaves the other skip rules
alone. The changed query was run against a real PostgreSQL with test rows. Approve with nits: the title rule is a
heuristic, and the PR says so.

## Scope of Change
- Files changed: 5 (excluding this review)
- Areas touched: packages (llm) / tests / web_docs
- Commits: `c274fd4f` fix(llm): load meetings the scraper typed Other when something says they are meetings
- Range reviewed: `origin/main...origin/fix/829-other-is-not-non-meeting`

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | Read on the commit that carries this file before merging. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
All four clean. The gate module still only reads (its own test asserts no write statements); table names are constants.

## Strengths
- The evidence is the owner's drill-down, and the five reported titles are test cases.
- A person's verdict is honoured in both directions, which also makes the Meeting kinds override effective for these
  videos for the first time.
- Optional tables are checked with `to_regclass` before being read, as the existing query did.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- The title pattern keeps anything naming a "board", "hearing" or "authority". A non-meeting video with such a title on
  a non-junk channel, never screened by Jev, would now load. Mitigations in place: the junk-channel and excluded rules
  run first, a low Jev score still skips, and the Meeting kinds tab can mark it. Watch the `kept_other_by_title` count
  on the first real run.
- `decide_skip` gained an optional third argument; the one caller passes the run's floor. A test covers a custom floor.
- The first draft used `??` for the jsonb operator, which psycopg2 would have sent as written and PostgreSQL would
  have rejected. Fixed before the commit; a test asserts the query has no `??`, and the query was run for real.
- The scraper still stores `Other` for these titles; logged as #831.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #829 with the four parts; branch `fix/829-other-is-not-non-meeting`; `Closes #829`; follow-up #831 |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |
| New Python in `packages/` | Yes | |
| dbt for transformations | Yes | A loader gate reading bronze flags, as before |
| Docs | Yes | `web_docs/docs/development/batch-load-tab.md` |
| Telemetry and logging | Yes | loguru; the summary line reports the new counts |
| Tests | Yes | Titles, counter-examples, each kind of evidence, precedence, the loader path |
| Shared libraries | Yes | Loader, gate and runner tests run together: 95 passed |

## Test Coverage
`pytest tests/test_loader_gate_796.py tests/test_load_tab_counts_823.py tests/test_load_tab_steps_796.py`: 95 passed.
The real query ran with psycopg2 on a scratch PostgreSQL 16: title, keep-score and override each keep a video; a low
score, an old-wording screen row and a non-meeting title are skipped; it still runs with the optional tables dropped.
Not run: the loader against the real warehouse.

## Verdict
approve-with-nits. Nothing must change first.
