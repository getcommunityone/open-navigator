---
sidebar_position: 52
title: Challenge scroll-to-answer — implementation plan
description: Bite-sized TDD plan for #969 — three full-viewport stops per challenge round (finding, question with answers below the fold, scrollable reveal), Gapminder-inspired rhythm without quiz framing.
---

# Challenge scroll-to-answer and scroll reveal — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each Data Center Challenge round three full-viewport scroll stops — Finding → Question (answers below the fold) → Reveal — with auto-scroll between stops, no right/wrong framing.

**Architecture:** Keep one `data-panel` per statement and the existing `roundBeat` state machine. Restructure `RoundPanel` into three `data-stop` sections. Extend snap/stacked `useActs` holds to land on those stops; reuse pinned `goToReveal` / question holds. Challenge calls scroll helpers after Ask me and after lock.

**Tech Stack:** React + TypeScript (`web_app`), Vitest, existing GSAP/Lenis `useActs`, `stance.css`, Docusaurus docs.

**Issue:** [#969](https://github.com/getcommunityone/open-navigator/issues/969). Design: [challenge-scroll-reveal-design.md](./challenge-scroll-reveal-design.md).

## Global Constraints

- No quiz “correct / wrong” copy or scoring; opinion only (Agree / Disagree / Not sure).
- Route `/challenge/:packId` and `?state=&city=&round=` unchanged; API and packs unchanged.
- Stop markers: `data-stop="finding" | "question" | "reveal"`.
- Reveal lead: player’s choice + “people who played”, never “of residents”.
- `prefers-reduced-motion`: same three stops; jump without smooth auto-scroll.
- Conventional Commits; branch `feat/969-challenge-scroll-reveal` off latest `main`.
- Docs under `web_docs/docs/` only; update the challenge guide in the same PR.
- No fabricated result numbers; empty / below-min-sample states stay as today.

---

## File map

| Path | Responsibility |
|---|---|
| `web_app/src/utils/stanceGame.ts` | Add `RoundStop`, `roundStop()`, keep `roundBeat` as source of truth |
| `web_app/src/utils/stanceBeat.test.ts` | Tests for `roundStop` mapping |
| `web_app/src/components/stance/RoundPanel.tsx` | Three `data-stop` sections; stacked answer pills; scroll-into-stop on transitions |
| `web_app/src/components/stance/useActs.ts` | Snap/stacked holds include `data-stop` positions; `goToStop(round, stop)` |
| `web_app/src/pages/Challenge.tsx` | After ask / answer / land-on-answered → scroll to the matching stop |
| `web_app/src/styles/stance.css` | Stop viewport height, stacked pills, reveal lead |
| `web_docs/docs/guides/data-center-challenge.md` | Player-facing pacing matches the design |
| `web_docs/docs/development/challenge-scroll-reveal-design.md` | Already written; tweak only if contract drifts |

---

### Task 1: `roundStop` pure helper

**Files:**
- Modify: `web_app/src/utils/stanceGame.ts` (near `roundBeat`)
- Modify: `web_app/src/utils/stanceBeat.test.ts`

**Interfaces:**
- Consumes: existing `RoundBeat` / `roundBeat(...)`
- Produces: `export type RoundStop = 'finding' | 'question' | 'reveal'` and `export function roundStop(beat: RoundBeat): RoundStop`

- [ ] **Step 1: Write the failing tests**

```ts
import { roundBeat, roundStop } from './stanceGame'

describe('roundStop', () => {
  it('maps finding → finding, question → question, results → reveal', () => {
    expect(roundStop('finding')).toBe('finding')
    expect(roundStop('question')).toBe('question')
    expect(roundStop('results')).toBe('reveal')
  })
  it('follows roundBeat for a fresh, asked, and answered round', () => {
    expect(roundStop(roundBeat({ answered: false, asked: false }))).toBe('finding')
    expect(roundStop(roundBeat({ answered: false, asked: true }))).toBe('question')
    expect(roundStop(roundBeat({ answered: true, asked: true }))).toBe('reveal')
    expect(roundStop(roundBeat({ answered: true, asked: true, changing: true }))).toBe('question')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web_app && npx vitest run src/utils/stanceBeat.test.ts`
Expected: FAIL — `roundStop` is not exported

- [ ] **Step 3: Minimal implementation**

In `stanceGame.ts` after `RoundBeat` / `roundBeat`:

```ts
/** Scroll stop inside a challenge round (#969). `results` beat lands on the reveal stop. */
export type RoundStop = 'finding' | 'question' | 'reveal'

export function roundStop(beat: RoundBeat): RoundStop {
  if (beat === 'results') return 'reveal'
  return beat
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web_app && npx vitest run src/utils/stanceBeat.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web_app/src/utils/stanceGame.ts web_app/src/utils/stanceBeat.test.ts
git commit -m "feat(web): map challenge roundBeat to scroll stop names"
```

---

### Task 2: RoundPanel three-stop markup + stacked pills

**Files:**
- Modify: `web_app/src/components/stance/RoundPanel.tsx`
- Modify: `web_app/src/styles/stance.css`

**Interfaces:**
- Consumes: `roundStop`, existing beat / answer / results props
- Produces: DOM with `[data-stop="finding"|"question"|"reveal"]` inside `[data-panel]`; answers only under the question stop

- [ ] **Step 1: Restructure markup**

Keep the outer `<section data-panel={index} data-beat={beat}>`. Inside, three siblings (not display:none for inactive stops — height still scrolls; hide only interactive answers / reveal content that must not appear early):

1. **`data-stop="finding"`** — category card, finding headline, chart column, SidesBlock, Ask me / Skip / countdown (only when `beat === 'finding'` for the ask row; chart can stay visible quietly later).
2. **`data-stop="question"`** — “Where do you stand?”, statement, stacked `.stance-answers.stance-answers-stack` pills (Agree / Disagree / Not sure), Skip / Change my answer as today when on question beat.
3. **`data-stop="reveal"`** — lead line `You chose {ANSWER_LABEL[answer]}.` (only when answered), ResultBars / loading / error, ScreenNav Next/Back.

Visibility rules (match design):

- Finding stop always in the document (first viewport of the round).
- Question stop always in the document so the reader can scroll to answers; disable answer buttons unless `showButtons` (question beat).
- Reveal stop always in the document after first paint of the round; show result content only when `revealed` (or when returning answered). Before reveal, the stop can show an empty/`aria-hidden` placeholder of full viewport height so scroll distance exists only once the player has asked — **prefer:** reveal stop is mounted when `asked || answer != null` so Finding→Question does not require scrolling past an empty reveal.

Preferred mount rule:

```ts
const showQuestionStop = beat !== 'finding' || p.asked || p.answer != null
const showRevealStop = beat === 'results' || (p.answer != null && !p.changing)
```

While still on finding and never asked, only the finding stop is in the tree (one viewport). After ask, question stop mounts and we scroll to it. After answer, reveal stop mounts and we scroll to it.

- [ ] **Step 2: Stacked answer CSS**

```css
.stance-answers-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: min(100%, 28rem);
  margin-top: 1.5rem;
}
.stance-answers-stack .folio-btn {
  min-height: 52px;
  width: 100%;
  justify-content: center;
  border-radius: 999px; /* only if house theme already allows pills; else keep folio square corners */
}
.stance-stop {
  min-height: calc(100svh - var(--hdr, 0px) - var(--top-h, 96px));
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 12px 0 24px;
}
```

If folio forbids full pills, keep rectangular full-width buttons — do not invent a new brand look; prefer existing `.folio-btn` shapes.

- [ ] **Step 3: Scroll helper inside RoundPanel**

```ts
function scrollToStop(root: HTMLElement | null, stop: RoundStop, smooth: boolean) {
  const el = root?.querySelector<HTMLElement>(`[data-stop="${stop}"]`)
  el?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' })
}
```

After `onAsk` path (when beat becomes question) and after lock clears into results, call `scrollToStop` with `!reduced`. Also accept optional `onNeedPageScroll?: (stop: RoundStop) => void` prop so Challenge can use `acts.goToStop` when the stop is a page-level hold.

- [ ] **Step 4: Manual check**

Run the app, open `/challenge/data-centers`. Finding fills the screen; Ask me → question + pills; answer → reveal with “You chose …”.

- [ ] **Step 5: Commit**

```bash
git add web_app/src/components/stance/RoundPanel.tsx web_app/src/styles/stance.css
git commit -m "feat(web): challenge RoundPanel three scroll stops and stacked answers"
```

---

### Task 3: `useActs` stop-aware holds + `goToStop`

**Files:**
- Modify: `web_app/src/components/stance/useActs.ts`

**Interfaces:**
- Consumes: `[data-stop]` inside `[data-panel]`
- Produces: `ActsApi.goToStop(round: number, stop: 'finding' | 'question' | 'reveal'): void`; snap/stacked `holds()` include stop positions with `kind: 'q' | 'r'` (finding/question → `q` refinement via optional `stop` field **or** encode finding as goToRound and question/reveal as distinct positions)

Add to `Hold`:

```ts
export interface Hold {
  pos: number
  round: number
  kind: HoldKind | 'end'
  /** Challenge three-stop rhythm (#969); absent on story screens. */
  stop?: 'finding' | 'question' | 'reveal'
}
```

- [ ] **Step 1: Snap/stacked holds**

When building holds for non-pinned modes, for each act `i < count`:

```ts
const stops = Array.from(act.querySelectorAll<HTMLElement>('[data-stop]'))
if (stops.length) {
  for (const el of stops) {
    const stop = el.dataset.stop as 'finding' | 'question' | 'reveal' | undefined
    if (!stop) continue
    out.push({
      pos: Math.max(0, el.getBoundingClientRect().top + window.scrollY - off),
      round: i,
      kind: stop === 'reveal' ? 'r' : 'q',
      stop,
    })
  }
} else {
  out.push({ pos: /* existing */, round: i, kind: 'q' })
}
```

Only push `reveal` stops when `isAnswered(i)` **or** the reveal node is in the DOM (RoundPanel mounts it when answered).

- [ ] **Step 2: `goToStop`**

```ts
goToStop: (round, stop) => {
  const h = holds().find((x) => x.round === round && x.stop === stop)
  if (h) scrollToPos(h.pos) // or window.scrollTo in snap
  else {
    // fallback: query DOM
    const act = acts[round]
    const el = act?.querySelector<HTMLElement>(`[data-stop="${stop}"]`)
    if (el) {
      const pos = Math.max(0, el.getBoundingClientRect().top + window.scrollY - frameOffset(game))
      scrollToPos(pos)
    }
  }
}
```

Pinned mode: map `finding` → start of pin / question hold slightly early; `question` → `QUESTION_HOLD`; `reveal` → existing `goToReveal` / `REVEAL_HOLD`. Implement by finding hold with matching `stop` once pinned holds also set `stop` on the q/r entries:

```ts
out.push({ pos: Math.round(st.start + 0.08 * span), round: i, kind: 'q', stop: 'finding' })
out.push({ pos: Math.round(st.start + QUESTION_HOLD * span), round: i, kind: 'q', stop: 'question' })
if (isAnswered(i)) out.push({ pos: Math.round(st.start + REVEAL_HOLD * span), round: i, kind: 'r', stop: 'reveal' })
```

- [ ] **Step 3: Export API**

```ts
export interface ActsApi {
  holds: () => Hold[]
  goToRound: (round: number, duration?: number) => void
  goToReveal: (round: number) => void
  goToStop: (round: number, stop: 'finding' | 'question' | 'reveal') => void
  lock: (locked: boolean) => void
}
```

Keep `goToReveal(r)` as `goToStop(r, 'reveal')`.

- [ ] **Step 4: Commit**

```bash
git add web_app/src/components/stance/useActs.ts
git commit -m "feat(web): useActs goToStop and data-stop holds for challenge rhythm"
```

---

### Task 4: Challenge wiring

**Files:**
- Modify: `web_app/src/pages/Challenge.tsx`
- Modify: `web_app/src/components/stance/RoundPanel.tsx` (props for scroll callback if needed)

**Interfaces:**
- Consumes: `acts.goToStop`, `roundStop`
- Produces: Ask me / answer / land-on-answered drive the correct stop

- [ ] **Step 1: After ask**

Where `ask(id)` is called (button, Space, timer), after state updates, on next frame:

```ts
acts.goToStop(active, 'question')
```

- [ ] **Step 2: After successful answer**

After `postStanceResponse` confirms (where lock → results already happens), call:

```ts
window.setTimeout(() => acts.goToStop(index, 'reveal'), reduced ? 0 : LOCK_HOLD_MS)
```

- [ ] **Step 3: Land on answered round**

When URL/scroll settles on a round that already has `confirmed[id]` and not `changing`, call `acts.goToStop(round, 'reveal')` once per landing (guard with a ref so it does not fight the user scrolling back to question to change).

- [ ] **Step 4: FloatingNext / focus**

Ensure `data-primary` remains on Ask me (finding), answer group (question), Next (reveal) so FloatingNext and keyboard settle targets follow the stop.

- [ ] **Step 5: Commit**

```bash
git add web_app/src/pages/Challenge.tsx web_app/src/components/stance/RoundPanel.tsx
git commit -m "feat(web): scroll challenge rounds between finding, question, reveal"
```

---

### Task 5: Docs + guide

**Files:**
- Modify: `web_docs/docs/guides/data-center-challenge.md` (Pacing and sound; How screens move)
- Optionally link from that guide to `development/challenge-scroll-reveal-design.md`

- [ ] **Step 1: Rewrite pacing bullets**

Replace “three beats on one screen” with the three stops table from the design (Finding / Question / Reveal), note stacked pills and auto-scroll, keep sound and reduced-motion notes.

- [ ] **Step 2: Commit**

```bash
git add web_docs/docs/guides/data-center-challenge.md
git commit -m "docs(web_docs): challenge guide three-stop scroll rhythm"
```

---

### Task 6: PR

**Files:** review file only

- [ ] **Step 1:** Ensure branch `feat/969-challenge-scroll-reveal`, all commits Conventional Commits, `Closes #969`
- [ ] **Step 2:** Open PR; write `pull_requests/pr-<n>-review.md`; wait for required CI; squash-merge when green and review approves

---

## Spec coverage checklist

| Spec requirement | Task |
|---|---|
| Three stops Finding → Question → Reveal | 2, 4 |
| Answers below the fold / stacked pills | 2 |
| Auto-scroll ask → question, lock → reveal | 3, 4 |
| Already-answered lands on Reveal | 4 |
| No right/wrong | 2 (copy), 5 |
| Reduced motion jumps | 2, 3 |
| `data-stop` contract | 2, 3 |
| Guide updated | 5 |
| API / packs / route unchanged | (no task changes them) |

## Placeholder scan

None intentional. Pill `border-radius: 999px` is conditional on house theme — implementer must follow existing folio corners if pills conflict.

---

## Execution

Plan saved to `web_docs/docs/development/challenge-scroll-reveal-plan.md`.

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  

**2. Inline Execution** — run tasks in this session with checkpoints  

Which approach?
