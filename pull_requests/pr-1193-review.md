---
pr: 1193
branch: fix/1190-plain-stance-wording
title: "fix(stories): say \"the public mostly opposed\" instead of \"leaned against\""
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: fix(stories): say "the public mostly opposed" instead of "leaned against"

## Summary
Replaces every user-visible "leaned against / leaned for / Mixed" with plain wording, following the owner's feedback in #1190. Non-"hates" titles now read "In 81 meetings, the public mostly opposed water fluoridation." Legends, hover cards and tables read "Public mostly opposed / mostly supported / split". The "[Place] hates X." titles do not change. Counts and "(AI reading)" labels do not change. No field, column or table is renamed. tsc, vitest, the web build, the docs build, pytest and a Playwright spot check all pass. Two minor nits remain and nothing blocks merge.

## Scope of Change
- Files changed: 23 (about +175 / -98, excluding `api.types.ts`)
- Areas touched: api (Field descriptions and docstrings only), web_app, web_docs, pull_requests
- Commits: 21ed3eca fix(stories): say "the public mostly opposed" instead of "leaned against" (#1190); b46ff1e9 docs(pr-1193): auto-write rubric review; plus a follow-up test commit with this review
- Range reviewed: `fbecec6f..HEAD`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | read on the head commit before merge |
| Documentation Build | read on the head commit before merge (passed locally) |
| Backend Tests | read on the head commit before merge (75 related tests passed locally) |
| API Types | read on the head commit before merge |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data: clean. Every number in a title or basis line still comes from caption-facts. The example numbers appear only in tests and docs.
- Personal data: clean.
- Destructive data changes: none. Copy only.

## Strengths
- The "hates" path is unchanged in behaviour; only its basis wording moved.
- `CaptionCopy.opposed` keeps the guns phrasing per topic.
- A plain title states the AI count, so it is now gated on the meeting reading. No topic changes today: only data centers has a speaker gate, and data centers says "hates".
- Tests assert exact new strings. Edge cases are covered: 1 meeting, "nationwide", and a title that counted speakers alone can't produce.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `web_app/src/utils/storyCaption.ts` `captionSubhead`: the subhead says "the public has mostly spoken against X", while the title now says "mostly opposed". Both are plain and the subhead was never "leaned", so it is left as is.
- `lib/api.types.ts` "Public Mixed Meetings" is the title openapi-typescript generates from the field name `public_mixed_meetings`. Field names are kept by design.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #1190 has all four parts; branch `fix/1190-plain-stance-wording`; `Closes #1190` |
| Conventional Commits | Yes | Co-author trailer present |
| No fabricated data | Yes | Scan clean |
| New Python in `packages/` | N/A | |
| dbt for transformations | N/A | |
| Scope label matches filter | Yes | The place stays in the title at state and city scope |
| Docs | Yes | data-stories.md, story-captions.md (decision section), data-center-meeting-lean.md, topic-meeting-lean.md |
| Telemetry and logging | N/A | |
| Tests | Yes | Expectations updated, new assertions added |

## Test Coverage
Run locally:
- `npx tsc --noEmit`
- `npx vitest run`: all pass, 596 tests
- `npm run build`
- Docusaurus build
- pytest on the topic and data-center route tests: 75 passed
- `ruff`: no new findings (the existing counts match main)

Playwright on `/`, `/?story=water-fluoridation`, `/stories/water-fluoridation`, `/stories/guns`, `/stories/short-term-rentals`, `/stories/data-centers` and `/?state=AL&city=Tuscaloosa`, against this branch's API, found no "lean" copy. The one hit was a verbatim transcript quote.

## Verdict
approve-with-nits. Merge once the required CI is green.
