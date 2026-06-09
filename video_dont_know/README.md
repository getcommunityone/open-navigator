# Phoenix City Council — "You Don't Know Jack" edition 🎙️

A ~90-second, **vertical 1080×1920 (9:16)**, game-show-style explainer of the
**most controversial decision** in the Phoenix City Council Formal Meeting of
**April 8, 2026** — built with
[canvas-commons](https://github.com/canvas-commons/canvas-commons).

It combines **frame analysis** (how each side framed the issue: problem → story → fix)
with the irreverent, fast-talking *You Don't Know Jack* trivia-show vibe — complete
with synthesized **sound cues** (title stinger, ticks, ding, whoosh, VS clash, boom,
applause).

## The decision it covers

Of the five decisions Open Navigator's policy analysis surfaced from this meeting, the
video focuses on **D004 — accepting reallocated FY2022 federal Homeland Security grant
funds**. It's the most controversial: the only one pairing a **split 8–1 vote** with
charged civil-liberties subject matter — the definition of "terrorism," monitoring of
hate groups, and potential **ICE collaboration**. Councilwoman Hernandez cast the lone NO.

All on-screen facts (the FY2022 funds, the 38 AZ hate groups from the 2023 SPLC report,
the 8–1 tally, and both competing frames) come straight from the meeting's analysis
record — see [`src/decision.ts`](src/decision.ts). Source video: `CGDA6fZy7Ok`.

## Storyboard (6 scenes, plays back-to-back)

| # | Scene | Beat |
|---|-------|------|
| 1 | `01_intro`     | "YOU DON'T KNOW… PHOENIX" cold-open title slam |
| 2 | `02_round1`    | Round 1 trivia: *which fiscal year?* → **C) 2022** |
| 3 | `03_frameoff`  | **FRAME-OFF!** Blue *Team Public Safety* vs Red *Team Protect Communities* — each frame's problem / story / fix |
| 4 | `04_lightning` | By-the-numbers: FY2022 · 38 hate groups · 8–1 |
| 5 | `05_finalvote` | Final answer: *how did it end?* → **Approved 8–1** + scoreboard |
| 6 | `06_outro`     | "Now you know more than most of Phoenix" + attribution |

## Run it

```bash
npm install
npm start          # editor at http://localhost:9000
```

## Render the MP4

canvas-commons renders from the browser editor (there is no headless CLI render):

1. `npm start` and open <http://localhost:9000>.
2. Open the **Video Settings** tab → click **RENDER**.
3. The MP4 (FFmpeg exporter, already wired in `vite.config.ts`) is written to `output/`.

Resolution/FPS are preset to **1080×1920 @ 30fps** in [`src/project.meta`](src/project.meta)
(`shared.size`); change them there or in the editor's Video Settings. Runtime is ~90s;
trim or extend the `waitFor(...)` holds in each scene to retune pacing.

## Audio

Sound cues are scheduled in-scene via canvas-commons' `sound(url).play()` API (see the
`sfx()` helper in [`src/lib.tsx`](src/lib.tsx)) and are muxed into the MP4 by the FFmpeg
exporter. The WAV files in `public/audio/` are synthesized — pure-stdlib, deterministic —
by [`tools/gen_sfx.py`](tools/gen_sfx.py):

```bash
python3 tools/gen_sfx.py      # regenerates public/audio/*.wav
```

Swap in your own clips by dropping same-named files in `public/audio/`, or change the
names passed to `sfx(...)` in the scenes.

## Verify it compiles

```bash
npm run build      # tsc typecheck + vite bundle
```

## Files

```
src/
  project.ts        scene order
  project.meta      canvas size (1080x1920) + fps
  decision.ts       the real D004 data + both frames (single source of truth)
  lib.tsx           palette, fonts, background, host bar, answer chips, sfx(), helpers
  scenes/           01_intro … 06_outro
public/audio/       synthesized sound cues (*.wav)
tools/gen_sfx.py    regenerates the sound cues
```
