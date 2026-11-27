---
pr: 1185
branch: fix/1182-story-start-next-map-title
title: "fix(stories): topic-named Start and Next story on every story, and the title says what the map shows"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: general-purpose reviewer subagent (read-only) and coordinator
verdict: approve
---

# PR Review: fix(stories): topic-named Start and Next story on every story, and the title says what the map shows

## Summary

Closes #1182. Four changes:

- The caption picker gets a scope-named fallback (`wider_sentiment`). When a place's own AI reading is too thin, the
  title states the nearest broader scope whose reading passes, by name, so the title matches the red map beside it.
  The other topics say "leaned against" (never "hates"), and `caption-facts` serves `wider`.
- Every story opens with a topic-named Start and Next story.
- The Data Center Story's opening moves out of the 244px sticky bar into a first-screen cover hold.
- The home card's numbered points are removed, at the owner's request.

A read-only reviewer found three important issues and two minor ones in the first commit. The important ones: a basis
line that could state something false, a cover hold that took over landing, and focus moving while on the cover. All
five were checked against the code and fixed in `44cec9df`, or moved to follow-up #1186. Verdict: approve.

## Scope of Change

- Files changed: 18 (+640 / -155, not counting the bot's review file)
- Areas touched: api, tests, web_app, web_docs
- Commits:
  - 372a9619 fix(stories): topic-named Start and Next story on every story, and the title says what the map shows
  - 04bb1373 docs(pr-1185): auto-write rubric review [skip review] (bot)
  - 44cec9df fix(stories): state the place's own reading truly, keep the opening as a cover hold, carry the state on topic stories
  - a9d99161 fix(home): remove the data-center card's numbered points on every screen size
- Range reviewed: `65cfb4e5..a9d99161`

## CI Status

| Check | Status |
|---|---|
| Frontend Build | required; see the PR checks on the head commit |
| Documentation Build | required; see the PR checks |
| Backend Tests | required; see the PR checks |
| API Types | required; see the PR checks |
| PR conventions | see the PR checks |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data:** clean. Every number in the new titles and basis lines comes from `caption-facts`:
  - `meetings`, `lean_meetings` and `public_against_meetings`;
  - `wider[]`, read from `data_center_meeting_lean` and `topic_meeting_lean`.

  The test fixtures are labelled as stand-ins and are only used in tests. The threshold constants are documented
  rules, not data.
- **Personal data:** clean. The change only uses aggregates.
- **Destructive data changes:** none. The new SQL is read-only and runs through the existing `_optional` wrapper.

## Strengths

- One title system. The home cards, the story header and the Overview all read `pickCaption`, so this fix lands
  everywhere at once.
- The fallback keeps the place as its blank, so the scope label and the place picker still name the reader's place.
  The broader claim is named in words (CLAUDE.md scope-label rule).
- The API addition is defensive: a missing lean table leaves that scope out of `wider`, never a 0 and never a 500.
- Measured before and after with Playwright at three viewports.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

All three were fixed in `44cec9df`.

1. `web_app/src/utils/storyCaption.ts`, `widerSentiment`: the basis always said "has too few AI-read meetings". That
   was false for a place with many readings that aren't "against" (Alabama: 71 read, 6 against). The basis now states
   the place's own reading, in one of three forms, each with a vitest:
   - "6 of Alabama's 71 meetings with an AI reading read as mostly against, under the 10 a reading of its own needs."
   - "None of …"
   - "has no AI reading of its own yet"
2. `web_app/src/pages/DataStory.tsx`, the land effect: `holds().find(round === at && kind !== 'r')` picked the new
   cover hold for screen 0, so a `?screen=overview` link or a screen rebuild pulled the reader back to the cover.
   - The fix finds `q` and `end` holds, and keeps the cover only for a fresh visit or a reader still above screen 0.
   - Checked in the browser: `?screen=overview` lands at y=1668, a fresh visit lands at y=0, and Start goes to
     screen 0.
3. `DataStory.tsx`, `onSettled`: settling on the cover focused screen 0's panel. Tab then skipped the cover's buttons,
   and a screen reader announced a screen that wasn't shown. It now returns early for `kind === 'cover'`.

### 🔵 Nits / suggestions (Minor)

1. A null `wider[].state` put a bare state code in the title. Fixed: it falls back to the scope's state name, with a
   test.
2. `web_app/src/pages/TopicStory.tsx` works at state grain but forwarded `?city=`. Fixed: it now carries only the
   state it shows. Honouring the city on topic stories is follow-up #1186.
3. On the folio story pages, the house style's `border-radius: 0 !important` squares the shared buttons. That's
   intended, to match the folio theme.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | Branch `fix/1182-…`, `Closes #1182`; the issue has all four parts, plus dated scope lines |
| Conventional Commits | ✅ | Co-author trailer on every agent commit |
| No fabricated data | ✅ | Scan clean; AI readings labelled "(AI reading)" |
| New Python in `packages/` | ✅ | No new scripts |
| dbt for transformations | ✅ | Counts only, through the existing lean SQL |
| Naming | ✅ | `state_code` and `state` on `CaptionWiderLean` |
| Keys | n/a | No models changed |
| Calendar years | n/a | |
| Scope label matches filter | ✅ | Broader claims are named; TopicStory links carry the state it shows |
| Match evidence on filtered tiles | n/a | |
| Docs | ✅ | `guides/data-stories.md`, `development/story-captions.md`, `development/story-statements-where-you-sit.md` |
| Telemetry and logging | ✅ | The new reads run inside the existing `topics.caption-facts` span; `_optional` logs loguru warnings |
| Tests | ✅ | See Test Coverage |
| Shared libraries | n/a | No `packages/` change |

## Test Coverage

New tests:

- vitest:
  - national scope, "hates";
  - a city in a red state names the state;
  - a thin state falls back to national;
  - the place's own reading wins when it passes;
  - a topic that isn't allowed "hates" says "leaned against";
  - the basis states the place's reading truly;
  - a null state name falls back to the scope's.
- pytest: `wider` for city, state and national scope.

Run locally:

- `npx tsc --noEmit`.
- `npx vitest run`: 63 files, 591 tests.
- `npm run build` in web_app.
- `npm run build` for the docs: it succeeds; the broken-link warnings are on pages this PR doesn't touch.
- `pytest tests/test_api_topic_caption_facts.py`: 14 passed.
- `ruff check` on the changed Python.
- Playwright before and after, at 1366x768, 1440x900 and 390x844, on `/`, `/?story=license-plate-readers`,
  `/?state=AL&city=Tuscaloosa`, `/stories/data-centers` and `/stories/guns`.
- DataStory scroll and keyboard checks: the cover, Start, wheel up and down, and a deep link.

## Verdict

Approve. Nothing blocking remains. Merge once the required checks are green on the head commit.
