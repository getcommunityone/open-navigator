---
pr: 1212
branch: fix/1206-home-title-place-control
title: "fix(home): the place in the home story title is a subtle inline place control again"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: frontend-specialist subagent (read-only) and coordinator; supersedes the github-actions auto-review (ce26054a)
head_sha: 8cfd036c4acab6ee82d36c76da3d15b452625f99
verdict: approve-with-nits
---

# PR Review: the place in the home story title is a subtle inline place control again

## Summary
The PR answers the owner's 26 Nov feedback (#1206). The home hero's story title, on the data-centers card and every topic card, draws its place as the story pages' `PlaceControl` blank: "[America ▾] hates data centers." In the wider-scope title the control is the reader's chosen place, the second one: "America hates data centers; [Tuscaloosa, Alabama ▾] brought them up in 2 meetings."

The caption's words are untouched. A new pure helper (`splitCaptionAtPlace`, tested) only says where the place sits. A city or state pick goes through the header's `usePlacePick`, and "The United States" sets the home level to National. As a result the header label, the title, the map highlight and the Browse topics captions move together, which Playwright confirmed at 1440x900 and on iPhone 13.

No Critical or Important finding survived verification. Two Minor items are pre-existing patterns and are logged as follow-ups. Verdict: approve with nits.

## Scope of Change
- Files changed: 9 (+317 / -22), web_app and web_docs only
- Areas touched: web_app (home hero, HomeV9, PlaceControl optional prop, new helper and CSS), web_docs (guides/data-stories.md)
- Commits:
  - 74dfc676 fix(home): the place in the home story title is a subtle inline place control again
  - 8cfd036c Merge remote-tracking branch 'origin/main' into fix/1206-home-title-place-control
  - ce26054a docs(pr-1212): auto-write rubric review [skip review]
- Range reviewed: `2e4974c5..74dfc676`. The merge brings in origin/main only.

## CI Status
| Check | Status |
|---|---|
| Frontend Build | pass (8cfd036c) |
| Documentation Build | pass (8cfd036c) |
| Backend Tests | pass (8cfd036c) |
| API Types | pass (8cfd036c) |
| PR conventions | pass (8cfd036c) |
| Docker Build Test | skipped (no Docker files) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean. "tokens" in the diff are CSS design tokens.
- Fabricated data: clean. Every number in the title comes from the caption-facts response through `pickCaption`. The split never adds a figure. The helper tests use labelled stand-in caption shapes.
- Personal data: clean. A pick saves the place through the existing `LocationContext`, as the header picker already does. Nothing new is stored or logged.
- Destructive or bulky data changes: none.

## Strengths
- The caption logic is reused, not forked. `storyCaption.ts` is untouched, which avoids conflict with the open caption-wording PR.
- The pick path is the header's (`usePlacePick` with `PLACE_PICKED_EVENT`), so the level re-derives correctly and the header label follows.
- `PlaceControl` change is one optional prop, added only when set. Story pages render identically.
- The tap target is at least 44px via an `::after` layer, so the title's line height is unchanged on phones.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None after verification.
- *Dropped:* the reviewer suggested that a city-scope "leader" caption could name another city while the control showed the scope ("In [Tuscaloosa, Alabama], Northport …").
  - Traced in `storyCaption.ts` `stateGap`: the captions whose place is `name(top)` or "A and B" are only built in the `!scope.stateCode` (national) branch. City and state gaps use `storyScopeLabel(scope)`.
  - So the fallback only fires nationally, and there it reads "In [the United States ▾], California …", which is true (test `national title naming a leading state`).

### 🔵 Nits / suggestions (Minor)
1. `web_app/src/components/stance/PlaceControl.tsx` (toggle wrapper). The blank variant's wrapper is a `<div>` inside the `<h1>`, which is invalid HTML. Its `aria-label="Place, …"` also prefixes the heading's accessible name.
   - This was already true on the story pages' `SentenceHeading`.
   - `components/stance/*` belongs to another agent, so it is not changed here: **#1216**.
2. `web_app/src/pages/HomeV9.tsx` `applyTitlePlace`. "The United States" sets the in-memory home level only, so a refresh returns to the saved place.
   - The level menu's National already behaves this way, so this is not a regression.
   - Carrying `?scope=national` is out of scope: **#1217**.
3. `HomeStoryTitle.tsx` imports `folio.css` and `stance.css`, about 113 KB of CSS, into the home bundle.
   - Verified: no leakage. All selectors are class-scoped, and the `html.*-snap` rules need classes home never sets.
   - A smaller extract could follow if bundle weight matters.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #1206 has all four parts; branch `fix/1206-…`; `Closes #1206`; follow-ups #1216, #1217 |
| Conventional Commits | Yes | Co-author trailer present |
| No fabricated data | Yes | Scan clean |
| New Python in `packages/` | n/a | |
| dbt for transformations | n/a | |
| Naming / Keys / Calendar years | n/a | |
| Scope label matches filter | Yes | The title control names the scope; a pick updates label, query and map together. National-in-URL gap pre-exists (#1217) |
| Match evidence on filtered tiles | n/a | |
| Docs | Yes | `web_docs/docs/guides/data-stories.md` updated in the same PR |
| Telemetry and logging | n/a | |
| Tests | Yes | `captionPlace.test.ts` (7 tests) covers national, wider-scope, mid-sentence, question, leading-state and no-place-blank captions |
| Shared libraries | n/a | |

## Test Coverage
Run locally:
- `npx tsc --noEmit` clean.
- `npx vitest run`: 67 files and 615 tests pass, after merging origin/main.
- `npm run build` OK.
- Docs `npm run build` OK; the broken-link warnings are pre-existing.

Playwright (1440x900 and iPhone 13) on this branch's Vite, against the API on :8001:
- Tuscaloosa → **All of Alabama**: the title, header ("AL") and map highlight switch.
- → **The United States**: "America ▾ hates data centers." and the map is unmuted.
- Topic cards at national scope read "In the United States ▾, California brought up pickleball in 446 meetings, more than any other state."

Not covered by an automated test: the HomeV9 pick wiring. Playwright covered it manually.

## Verdict
Approve with nits. Nothing blocking. The nits are tracked in #1216 and #1217.
