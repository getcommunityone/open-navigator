---
pr: 1335
branch: feat/1314-meeting-outcomes
title: "feat(stories): what happened next — link meetings to state bills and show the chain from meeting to outcome"
author: agent (Claude Code)
reviewed_at: 2026-11-27
reviewer: authoring agent, reviewing against .claude/review-rubric.md (no second human reviewer)
verdict: approve-with-nits
---

# PR Review: what happened next

## Summary
Adds `meeting_bill_link` (gold mart, public view, PK/FKs enforced; ports #1072's draft and adds decision, agenda and
minutes evidence), `GET /api/topics/{topic}/outcomes`, a "What happened" chain screen on every story and a Votes card
on the home strip. Each link and each example carries verbatim evidence and a source link. Empty steps say
"No recorded … yet". Verdict: approve-with-nits.

## Scope of Change
- Files: 24 (one generated ODCS contract + product file)
- Areas: dbt_project / api / tests / web_app / web_docs
- Commits: d3f08fc6, d741bd95 (+ this review)

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types, PR conventions | read on the head commit before merge |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data: none. Every count is a COUNT over a mart. Unavailable relations answer `available: false` and the page shows a dash.
- Personal data: the evidence is meeting-transcript, decision, agenda or minutes text already served. No private person is enriched. Counts are of meetings, never people.
- Destructive data changes: none. New table only. No Neon write.

## Strengths
- Evidence-only linking with an explicit method vocabulary. Decisions that cite law without a bill number are not linked.
- The links step counts only the topic's own bills. A first version also counted any bill named at a topic meeting, which pulled in unrelated bills (firefighter hours, cannabis); that was caught on review of real output and removed.
- Data centers read their own marts, so the chain's counts equal the Data Center Story's own figures (1,859 meetings, not the 2,257 keyword links).
- Example lookups run after `LIMIT`, so the endpoint answers in 0.1–0.8 s (it was 5–10 s).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- The State bills step shows `topic_legislation_bill` status as is, so a dead 2023-24 bill can read "pending" (GA fluoridation: 1). What's next already applies #1302's guard. The root fix is #1308.
- `meeting_bill_link` takes about 17 minutes to build locally (regex over every transcript that mentions a bill form). It is not in the nightly selector (#1311 covers the serving tables). Consider an incremental build on `event_documents.created_at` if it joins the nightly run.

### 🔵 Nits / suggestions (Minor)
- The topic story's header can state a stepped-up scope (the #1297 rule: "America mostly wants fluoridation ended" on `?state=GA`) while this screen's panel says Georgia. The panel matches its own data and query; the header belongs to on-mapcard.
- "See all" on a Data Center Story step whose target screen dropped out (no data) does nothing. It is rare; the button could hide when the screen is absent.

## Repo-Rule Compliance
| Rule | Status |
|---|---|
| Issue first | ✅ #1314 (four parts), epic #1300; #1072 noted |
| Conventional Commits | ✅ |
| No fabricated data | ✅ |
| New Python in `packages/` | ✅ n/a |
| dbt for transformations | ✅ linking and evidence in dbt; the API only counts and filters |
| Naming | ✅ `state_code` + `state` |
| Keys | ✅ PK + 3 FKs, contract enforced, built and tested (PASS=17) |
| Calendar years | ✅ ISO dates on the wire |
| Scope label matches filter | ✅ the panel title and headline name the scope the API was queried with |
| Match evidence | ✅ `<mark>` passages via `highlightSnippet` for meetings and links |
| Docs | ✅ guide + development/meeting-bill-links.md |
| Telemetry | ✅ span `topics.outcomes` |
| Tests | ✅ pytest (mocked shape + live parity per step), vitest topicOutcomes.test.ts, screen-order tests |
| Shared libraries | ✅ ODCS regenerated, test_odcs passes |

## Test Coverage
Step shapes, DC vs generic readings, unpublished relations, bad input, live count parity for 4 scopes; UI words for
empty and full chains, step → screen mapping.

## Verdict
approve-with-nits. Merge when the required checks are green.
