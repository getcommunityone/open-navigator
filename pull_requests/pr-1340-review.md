---
pr: 1340
branch: feat/1330-all-positions-evidence
title: "feat(stories): stance evidence counts every recorded position, public and official, and headlines where they disagree"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: read-only reviewer subagent and coordinator
verdict: approve-with-nits
---

# PR Review: stance evidence counts every recorded position, public and official, and headlines where they disagree

## Summary
This PR implements the owner's direction on #1330. The stance minimum now counts meetings with any recorded position, public or official, and disagreement between officials and the public is headlined, with a way into those meetings. "Who spoke up" now says who the counts are about. Alabama clears the minimum (32 meetings with a position) and reads "Alabama is divided on data centers.", which agrees with its 8–1 vote. Georgia's "Who spoke up" headlines "officials sided against the public in 11 of 27 meetings where both took a side." A read-only reviewer found no Critical issues and one Important issue (named people undercounted from a capped list), which is fixed. The verdict is approve-with-nits.

## Scope of Change
- Areas touched: api (caption facts, one new drill endpoint), web_app (stance gate, PositionsSummary, drill, DataStory), web_docs, and generated `api.types.ts`.
- Range reviewed: `745b5b3f..2d4caa97`

## CI Status
| Check | Status |
|---|---|
| CI - Build & Test (Frontend, Docs, Backend, API Types) | success on b67eaf53; re-runs on this head |
| PR conventions | success |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data: clean. Each count comes from the lean marts or the decisions list, and missing data stays null. Named people are shown only when the decisions list is complete; a capped list would undercount, so the line is left out then.
- Personal data: clean. Only counts of distinct names are shown, and those names come from #1327's privacy-filtered `supported_by` / `opposed_by` (residents "First L.", no minors).
- Destructive data changes: none.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important)
- Fixed: `PositionsSummary` counted named people from a `limit: 500` list, which can be capped. Now it counts them only when `items.length` covers the whole-scope counts.

### 🔵 Nits / suggestions (Minor)
- Fixed: the disagreement count was found by searching the sentence for the number, so a place name with a digit could break it. It now comes as separate parts from `disagreementParts`, with a test.
- Fixed: "1 of 1 meetings" now reads "1 of 1 meeting". The `officialPositionsLine` doc example matches the output. The comment on missing official columns states the actual behaviour (the whole optional read goes null).
- Intended, per the owner's direction: any topic with a loaded reading is now held to the minimum, not only data centers.
- Left as is: `PositionsSummary` and `PositionsBlock` key caption facts on `city` only when a state is set, the same as the existing blocks.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | #1330 has all four parts |
| Conventional Commits | ✅ | |
| No fabricated data | ✅ | nulls, and no counts from capped lists |
| Scope label matches filter | ✅ | the drill echoes scope; its total equals the caption facts' `disagreement_meetings` |
| Privacy | ✅ | counts only; #1327 owns the names |
| Docs | ✅ | `story-captions.md` #1330 decision; `guides/data-stories.md` |
| Tests | ✅ | vitest 893/893, pytest 39/39, tsc clean |

## Test Coverage
- vitest covers the minimum constant at 5 and at 4, Alabama coming out divided, the disagreement line and its parts, the public and officials lines, the facts below the minimum, and named sides.
- pytest covers the official counts, the P 0.7 SQL, nulls from an older reading, and the drill's total, scope and missing mart.
- Checked live at Pixel 7 and 1440 on Vite 5368 with API 8062: Alabama, Georgia and national.

## Verdict
**approve-with-nits.** Nothing blocks the merge.
