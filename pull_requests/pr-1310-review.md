---
pr: 1310
branch: feat/1302-topic-upcoming
title: "feat(stories): what's coming up on a topic — scheduled meetings, hearings and open state bills"
author: agent (Claude Code)
reviewed_at: 2026-11-27
reviewer: authoring agent, reviewing against .claude/review-rubric.md (no second human reviewer)
verdict: approve-with-nits
---

# PR Review: what's coming up on a topic

## Summary
Adds `topic_upcoming` (gold mart, public view, PK/FKs enforced), `GET /api/topics/{topic}/upcoming`, a "Coming up"
screen on every story and a "What happens next" strip on the home page. Every item has a real future date, a verbatim
`<mark>`ed passage and a link to take part. Empty scopes say "Nothing upcoming on record for <place>" and offer the
next level up. Two data problems found on the way (dead and enacted bills read as `pending`) are guarded in the API and
logged as #1308. Freshness/nightly rebuild is #1311. Verdict: approve-with-nits.

## Scope of Change
- Files: 25 (one generated ODCS contract + product file)
- Areas: dbt_project (mart, schema, publish list, contracts) / api / tests / web_app / web_docs
- Commits: bdfffd97 (+ this review)

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types, PR conventions | read on the head commit before merge |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean (pre-commit detect-secrets passed).
- Fabricated data: none. Loading and errors show a dash or a sentence. Zero shows "Nothing upcoming on record …" / "No open state bill …". No fallback constants.
- Personal data: the evidence is a meeting-transcript passage already served by `topic_transcript_link`, an agenda passage or an official notice. No private person is added or enriched.
- Destructive data changes: none. New table only. No Neon write.
- Third-party sources: verified hearing rows show our own fetched passage and the government page link; the lead source's name is not carried.

## Strengths
- The evidence basis is explicit per row (`match_basis`), and the UI states it ("Agenda not posted yet. Gwinnett County discussed data centers on Jun 15, 2026:"). Nothing claims a topic is on an agenda it isn't.
- Keyword false hits (AI reading `no_item`) are excluded, and so are livestream ceremonies and webinars. Livestream "times" are not shown because they are publish times.
- The API counts are tested against the live mart (5 parametrized cases, skipped without the warehouse).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- `topic_upcoming` is not in the nightly rebuild or the Neon allow-list, so it decays and production shows `available: false`. Tracked in #1311 (Neon needs the owner's yes on size; no Neon writes in this PR).
- Still-open bills depend on two API guards (latest action from last year or this one; not chaptered or signed) until `topic_legislation_bill` status is fixed (#1308).

### 🔵 Nits / suggestions (Minor)
- The mart reads `source('bronze', 'bronze_event_youtube')` for the video → jurisdiction map and scheduled livestreams. `stg_youtube__event` exists but is not materialized locally. Move to a staging ref when it is.
- `place_discussed_before` can list two sessions of the same body on one day (Gwinnett work and business sessions). Both are real calendar rows.

## Repo-Rule Compliance
| Rule | Status |
|---|---|
| Issue first | ✅ #1302 (four parts), epic #1300, follow-ups #1308 #1311 |
| Conventional Commits | ✅ |
| No fabricated data | ✅ |
| New Python in `packages/` | ✅ n/a (API route only) |
| dbt for transformations | ✅ matching, evidence and dedup in dbt; API only filters by date and scope |
| Naming | ✅ `state_code` + `state`; no dim/fact |
| Keys | ✅ PK + 4 FKs, contract enforced, built |
| Calendar years | ✅ dates as ISO strings on the wire; `year` compared as integer |
| Scope label matches filter | ✅ the panel title, headline and API query all read `?state=` (and `?city=` on the Data Center Story); the home strip reads the same params and doesn't change them |
| Match evidence | ✅ `matched_text` `<mark>` → `highlightSnippet`; no `dangerouslySetInnerHTML` |
| Docs | ✅ guides/data-stories.md, development/topic-upcoming.md |
| Telemetry | ✅ span `topics.upcoming` with topic/state/city/total |
| Tests | ✅ pytest 12, vitest 772 (new topicUpcoming.test.ts; screen-order tests updated), tsc clean |
| Shared libraries | ✅ n/a (no packages/ change; ODCS regenerated) |

## Test Coverage
API shape, empty → broader (state → national, city → state), city without state ignored, pending bills, missing
relation, bad input, plus live count parity. UI words and hrefs unit-tested. Screens checked with Playwright at Pixel 7
and 1440 (home national and GA, fluoridation GA, data centers VA and GA).

## Verdict
approve-with-nits. Merge when the required checks are green.
