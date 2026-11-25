---
title: Challenge scroll-to-answer and scroll reveal
description: Design for adapting Gapminder Upgrader-style scrolling into the Data Center Challenge — three full-viewport stops per round (finding, question with answers below the fold, then a scrollable reveal) without a quiz right/wrong framing.
---

# Challenge scroll-to-answer and scroll reveal

Approved design for issue work that follows. Inspired by [Gapminder Upgrader](https://upgrader.gapminder.org/t/climate-study-2024/1730) scrolling and answer layout; adapted for an opinion challenge (no correct answer).

## Problem

The Data Center Challenge already plays each round in three beats (finding → question → results) on one pinned panel. Answers and the reveal appear in place. Gapminder’s Upgrader instead:

1. Puts the question on the first viewport and the answer choices **below the fold** (scroll to answer).
2. After a choice, moves into a **long scrollable explanation** (verdict → context → how others answered → next).

Players asked to reuse both (option **C**): one new round rhythm with scroll-to-answer and a post-answer scroll reveal.

## Decision

**Approach: same round, three scroll stops** — keep one round per statement and the existing `?round=` / `useActs` model. Inside each round, three full-viewport sections replace in-place beat swaps:

| Stop | On screen | How you leave |
| --- | --- | --- |
| **Finding** | Category, record headline, chart, optional quotes; **Ask me** / Skip. Fills the first viewport. | Ask me, Space, or the ask timer → scroll to Question |
| **Question** | “Where do you stand?” and the statement fill the viewport; **Agree / Disagree / Not sure** as large stacked pills **below** (scroll to reach). | Answer locks → short hold → scroll to Reveal |
| **Reveal** | Your choice (opinion only — never “right” / “wrong”) → “Here’s how people who played answered” with national / state / place bars → **Next: …** | Next / keys → next round’s Finding |

Rejected alternatives:

- **Separate routes per beat** (Gapminder’s `/question` → `/explanation`) — cleaner share URLs for the reveal, but fights `?round=` and pinned scroll.
- **CSS-only restyle** — bigger pills without a new scroll rhythm; would not feel like Upgrader.

## Contract

### Unchanged

- Route `/challenge/data-centers` (and pack redirects); query `?state=&city=&round=`.
- Three answers: Agree, Disagree, Not sure. No score, no answer key.
- Reveal copy stays “of people who played”, never “of residents”.
- API: stance packs, POST choice, results by national / state / place, `STANCE_MIN_SAMPLE`.
- Shared sound board (`stance.sound`); cues for open / question / lock / bar / finish.
- Scope bar, FloatingNext, progress pips / rail naming rounds by category (not numbers).

### Changed behaviour

- Each round is three scroll stops, not one panel that swaps content in place.
- Auto-scroll (smooth when motion is allowed) Finding → Question and Question → Reveal.
- Returning to an already-answered round lands on **Reveal** (Change my answer still available).
- Phone: snap between the three stops; desktop: pinned / scrubbed scroll consistent with the story and today’s challenge modes.
- `prefers-reduced-motion`: same three stops; no animated auto-scroll (instant jump or button-driven move only).

### UI names (for tests and docs)

- Stop markers: `data-stop="finding" | "question" | "reveal"` on each section inside the round.
- Answer pills: existing answer buttons, restyled as a stacked column under the question stop.
- Reveal lead: a short opinion line (e.g. “You chose Disagree.”) then the existing result bars.

## Out of scope

- Quiz correctness, stars, or “You are right / wrong”.
- Gapminder purple theme, logo, or copy.
- Changing statement packs or the API.
- Hub `/stories` or the Data Center Story screen order (only the Challenge).

## Read first

- `web_app/src/pages/Challenge.tsx`
- `web_app/src/components/stance/RoundPanel.tsx`
- `web_app/src/components/stance/useActs.ts`
- `web_app/src/components/stance/FloatingNext.tsx`
- `web_app/src/utils/stanceGame.ts` (`roundBeat`, result helpers)
- `web_docs/docs/guides/data-center-challenge.md`
- `web_docs/docs/development/where-you-stand-game-design.md`

## Done when

- A round’s Finding fills one viewport; answers are not visible until the reader scrolls (or is scrolled) to Question.
- After answering, the page scrolls to Reveal with the player’s choice and the people-who-played bars, then Next.
- Skip, Change my answer, sound, scope, reduced motion, and keyboard shortcuts still work as documented in the challenge guide.
- The challenge guide and this design page agree.

## Relation to earlier design

This updates the **pacing** of the challenge screens described in [Where Do You Stand? game design](where-you-stand-game-design.md) and the player-facing [Data Center Challenge](./archive/data-center-challenge.md). Storage, anonymity, minimum sample, and “no right answer” decisions are unchanged.
