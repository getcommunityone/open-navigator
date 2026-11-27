---
pr: 1283
branch: feat/1277-map-hover-video-card
title: "feat(stories): story maps drill on tap with no card on phones; desktop hover card autoplays the recording beside the map"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: coordinator (agent self-review against .claude/review-rubric.md), after the github-actions auto-review
verdict: approve-with-nits
---

# PR Review: feat(stories): story maps drill on tap with no card on phones; desktop hover card autoplays the recording beside the map

## Summary
The PR implements the owner's 27 Nov requests for the three story maps (the state box map, and the Data Center Overview's national and county maps).
- **Phones:** no card at all, and a tap drills in at once.
- **Desktop:** one person-first hover card beside the map, never over it. The recording autoplays muted from youtube-nocookie at the quoted second, then come the quote, the speaker, and the meeting · place · date. A real link goes to the state's story.
- **Drill-down:** the hovered state is outlined and lit.
- **Keyboard, reduced motion and data saving:** no autoplay.
- **Labels:** "(AI reading)" is dropped from the map labels.

Unit tests, typecheck, build, the docs build and the rewritten browser check (`e2e/map-taps.check.mjs`, at Pixel 7, iPhone 13 and 1440) all pass locally. CI was green on df0d9a40. Nothing is blocking; there are two nits.

## Scope of Change
- Files changed: 24 (+762 / -568, excluding this review)
- Areas touched: web_app, web_docs
- Commits:
  - c14a380a feat(stories): story maps drill on tap with no card on phones; desktop hover card autoplays the recording at the bottom-left
  - e5c334df Merge remote-tracking branch 'origin/main'
  - df0d9a40 feat(stories): map hover card is person-first and sits beside the map, never over it
  - de5e7523 docs(pr-1283): auto-write rubric review [skip review]
- Range reviewed: `merge-base(origin/main)..df0d9a40`

## CI Status
| Check | Status |
|---|---|
| CI - Build & Test (df0d9a40) | success |
| PR conventions (df0d9a40) | success |
| Runs on de5e7523 (bot review commit) | action_required (bot-triggered; the code is identical to df0d9a40) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. No key, token or password patterns in the added lines.
- **Fabricated data:** clean. The card renders only served passage fields, a missing field is left out (no "In the meeting" filler), and the test fixtures stay in tests.
- **Personal data:** clean. Speaker names are shown only as the API serves them ("First L."), and no new personal fields are added. The YouTube embed uses the privacy-enhanced host and is built only on a desktop mouse hover.
- **Destructive data changes:** none (frontend and docs only).

## Strengths
- One shared `QuoteCard` mode (`compact`, `inlineVideo`) serves all three maps. Mode selection (autoplay vs click) sits in one line per map, driven by `useMapKeyboard().keyed` and `prefersStillMedia()`.
- The card keeps one passage per state, so moving within a state does not restart the video.
- Touch and mouse paths are separated cleanly. The removed Close and outside-tap code is fully deleted, with its tests.
- The e2e check covers the owner's regression report: a click on Alabama on `/`, and the card link.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- `web_app/src/components/home/StoryStatesMap.tsx`, card portal: on the home page the card renders in the text column, which comes before the map in tab order. From keyboard focus, Tab can't reach the card's play button. Enter still drills. Verified by reading the DOM order. Possible fix: in the portal case, render the keyboard card under the legend.
- `web_app/src/components/stance/QuoteCard.css`, `.map-card-slot { min-height: 196px }`: the reserved height leaves about 70px of blank space under the hint at rest. This is a deliberate trade so the page doesn't jump (see the 1440 screenshots).

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first, four parts | Yes | #1277, label ux-friction |
| Branch / PR naming, Closes | Yes | feat/1277-…, "Closes #1277" |
| Conventional Commits + attribution | Yes | |
| Docs with the change | Yes | guides/data-stories.md, #1277 section |
| No Fabricated Data | Yes | |
| Scope label matches filter | N/A | Scope is unchanged; the local zoom is the follow-up PR |
| Match evidence on filtered tiles | Yes | Verbatim highlighted quote kept via highlightSnippet |
| Privacy | Yes | nocookie embed, served names only |

## Test Coverage
- **Unit:** `QuoteCard` inline video (autoplay/click/no id), compact person-first order, `youtubeHoverEmbedUrl`, `isTouchOnly` coarse pointer, `prefersStillMedia`, `useMapKeyboard` keyed, plus updated wording tests.
- **Local runs:**
  - `npx tsc --noEmit`, `npx vitest run` (753 passed), `npm run build` and the docs build.
  - `node e2e/map-taps.check.mjs --base http://localhost:5191`: phones (tap drills, no card, hint) and desktop (hover card off-map with autoplay iframe, swap, leave, keyboard no-autoplay, Escape, Enter, clicks on `/`, `/stories/guns`, `/stories/data-centers`, card link).

## Verdict
approve-with-nits. Nothing has to change before merge.
