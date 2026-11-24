---
pr: 812
branch: fix/808-browse-topics-empty-state
title: "fix(web_app): show topic load failures and empty states; add default curated topics"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: api-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: fix(web_app): show topic load failures and empty states; add default curated topics

## Summary
`GET /api/topics` returned `200 []` when its query failed, and Browse Topics drew nothing for an empty list, so a
failure and an empty catalog looked the same. The PR returns 503 on failure, explains both states on the page, adds two
curated topics to the seed and changes the search suggestions. The reviewer traced every consumer of the endpoint and
the keyword path and found no blocking or should-fix defects. Two nits were fixed on the branch; one became issue #816.
The PR makes the production failure visible; it does not restore the topics on the live site.

## Scope of Change
- Files changed: 7 (excluding this review)
- Areas touched: api / web_app / dbt_project (seed) / web_docs / tests
- Commits: `26574f07` fix(web_app): show topic load failures and empty states; add default curated topics, plus the
  review-nit commit that carries this file
- Range reviewed: `origin/main...origin/fix/808-browse-topics-empty-state` at `26574f07`

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | Not run at review time: the bot's review commit became the head and does not trigger workflows. Read them on the commit that carries this file before merging. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data in a served path: clean. The search suggestions are query strings, not data. The "1,908 meetings"
  figure is in a development doc as a dated observation of the live API, and is recorded on issue #808.
- Personal data: clean.
- Destructive or bulky data changes: clean (two seed rows added).

## Strengths
- A failure is no longer reported as an empty result, and the page says which of the two it is.
- The new test fails on `main` (the old handler returned `200 []`).
- The curated keywords are phrases, so "flock" alone never matches.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- `web_app/src/pages/BrowseTopics.tsx` error banner: it printed axios's generic "Request failed with status code 503"
  instead of the API's `detail`. Verified by reading the banner. **Fixed on the branch** (reads `response.data.detail`).
- `tests/test_api_topics.py`: nothing covered the new seed keywords. **Fixed on the branch**:
  `test_default_curated_topics_match_phrases_and_never_a_bare_flock`.
- `api/routes/topics.py`, `list_topic_meetings`: still returns `total: 0` on a database error. Out of scope here;
  logged as #816.
- `web_docs/docs/development/browse-topics-catalog.md`: the live-site figure cannot be checked from the repo. Accepted
  as a dated observation; the evidence is on #808.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #808 with the four parts; branch `fix/808-browse-topics-empty-state`; `Closes #808`; follow-up #816 |
| Conventional Commits | Yes | |
| No fabricated data | Yes | Empty and unavailable states are explicit |
| Scope label matches filter | Yes | The empty state names the place scope and links to the national view |
| Docs | Yes | `web_docs/docs/development/browse-topics-catalog.md` |
| Telemetry and logging | Yes | The existing span records the exception before the 503 |
| Tests | Yes | 503 regression test and keyword test |
| Keys / naming / dbt | n/a | Seed rows only; unique ids, names and slugs, ids at or above 100000 |

## Test Coverage
`pytest tests/test_api_topics.py`: 12 passed. `npx tsc --noEmit` and `eslint` on `BrowseTopics.tsx` pass. Not run:
`dbt seed` and the build of `civicsearch_topic+` (no warehouse access), the docs build (left to CI).

## Verdict
approve-with-nits. Nothing must change first. After merge the two new topics need `dbt seed`, a build and a publish,
and the cause of the empty production catalog still has to be found (#808).
