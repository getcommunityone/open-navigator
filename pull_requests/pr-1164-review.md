---
pr: 1164
branch: fix/1134-hero-speaker-basis
title: "fix(stories): one title for hero, story header and Overview; hero basis leads with the meeting reading"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: subagent (frontend-specialist, read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: fix(stories): one title for hero, story header and Overview; hero basis leads with the meeting reading

## Summary
The PR makes the home hero, the story header and the Overview screen take one title from the shared `pickCaption`
picker (#1141), replaces the misleading "Of 29 speakers" hero line with the AI meeting reading plus scoped hand counts,
gives the hero and story header place-scoped numbered points ("Nationally:" when a figure is national), and drops zero
clauses. The reviewer found no blocking issue. Three of its Important findings were fixed on the branch in 33d2394a
(Overview title mismatch, missing "across N states", state-scope hero flashing national points). The rest are
duplication that doesn't change what users see, filed as #1165. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 23 (+772 / -245, excluding `api.types.ts` and review files)
- Areas touched: api / web_app / web_docs / tests
- Commits:
  - ea17664d fix(home): hero leads with the meeting reading and matches the state scope
  - 9af55fbf fix(stories): one title for hero, story header and Overview, with divided, place points and no zero clauses
  - 33d2394a fix(stories): Overview states every non-question caption, national basis names its states, hero points wait for the place
  - merges of `origin/main` (conflicts in `HomeDataStories.tsx`, `DataStory.tsx` resolved keeping #1142 glyphs and #1133 live topic stories)
- Range reviewed: `ff94e85f..HEAD`

## CI Status
| Check | Status |
|---|---|
| PR conventions | pass |
| Frontend Build, Documentation Build, Backend Tests, API Types | read on the head commit before merge |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data: clean. Every figure traces to `caption-facts`, `lean_totals`, `scope_lean_totals` or `totals`. Missing
  data falls through to the next caption rule or to the question.
- Personal data and privacy: clean. No speaker names are added. Counts only.
- Destructive or bulky data changes: none.

## Strengths
- One picker (`pickCaption`) feeds the hero, the header, the Overview and the topic tiles.
- Zero sides are dropped through `countClauses`, and tests assert no zero clause in any title or basis.
- The AI reading is labelled as AI, and the hand counts always name their scope.
- The new API fields are guarded and return null when the lean table is missing.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- **Fixed in 33d2394a.** `web_app/src/utils/dataStory.ts` `overviewText`: a volume or state-gap caption fell through to
  `overviewLean`, so the title could read "Alabama talked about data centers in 3 meetings." over an Overview headline
  saying "Alabama pushed back…". Verified with the existing test, which asserted the mismatch. Any caption except the
  bare question is now the headline, and the test is updated.
- **Fixed in 33d2394a.** The national basis said "nationwide", not "across 32 states" as #1134 asks. Caption-facts now
  serves `public_against_states`, and the basis reads "In 283 meetings across 32 states, …". pytest and vitest are
  updated.
- **Fixed in 33d2394a.** `HomeDataStories.tsx`: at a state scope the points rendered "Nationally: …" while the scoped
  positions query was pending, then flipped. The points now wait for that query to settle.
- **Follow-up #1165.** Some helpers are duplicated:
  - three hand-count formatters: `speakerBasis`, `handCountLine` and `handCountSentence`;
  - two copies of the hates gate: `HATES_MIN_MEETINGS` and `conclusion.minLeanMeetings`;
  - legacy headline helpers and the dead `'scope'` screen kind.

  The state basis and point 1 also read two SQL paths with no parity test. None of this changes what users see today.
- **Follow-up #1165.** `lean_totals.public_for_meetings`, `public_mixed_meetings` and `public_spoke_meetings` are served
  but unused. The 2x for/mixed gate wasn't adopted because for/mixed readings were found unreliable, as recorded in
  `data-center-meeting-lean.md`.

### 🔵 Nits / suggestions (Minor)
- **Fixed.** `useStoryConclusion.ts` docstring referred to the removed `storyTitle`.
- `scope_lean_totals` filters cities with `ILIKE %city%`, the same as the existing speaker totals. This is a
  pre-existing behaviour.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `fix/1134-…`, `Closes #1134`, and the issue has all four parts |
| Conventional Commits | Yes | Co-author trailers present |
| No fabricated data | Yes | Scan clean |
| New Python in `packages/` | n/a | Only API route changes |
| dbt for transformations | Yes | Aggregate counts over existing marts only |
| Scope label matches filter | Yes | Place points or an explicit "Nationally:"; no national headline over a state |
| Docs | Yes | `guides/data-stories.md` and `development/data-center-meeting-lean.md` |
| Tests | Yes | vitest and pytest cover the new behaviour |

## Test Coverage
Run locally on the head commit:
- `npx vitest run src/utils src/lib`: 50 files and 508 tests passed.
- `npx tsc --noEmit`: clean.
- `npm run build`: built.
- `pytest tests/test_api_data_center_positions.py tests/test_api_topic_caption_facts.py tests/test_api_data_center_concerns.py tests/test_api_topic_state_map.py`: 44 passed.
- `ruff check`: no new findings. The 3 B008 findings in `data_centers.py` are on lines this PR doesn't touch.

There is no component-level test for the hero's scoped points. This is noted in #1165.

## Verdict
approve-with-nits. Merge once the required CI is green. The remaining duplication is tracked in #1165.
