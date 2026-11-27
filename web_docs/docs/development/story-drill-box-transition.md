---
sidebar_position: 64
title: State drill-down box transition
description: Why the Data Center Story's state drill-down animates its boxes on a canvas, how boxes are paired across the national and county grids, and what it never does (#1195).
---

# State drill-down box transition

[#1195](https://github.com/getcommunityone/open-navigator/issues/1195). The owner (26 Nov 2026) asked for the state
drill-down to "do fancy box animation reorganize", like the converging particle transitions in jcbowyer/kin
(`monochromeSparkInterlude.js`, `act1Hero.js`). Reader-facing behaviour: [Data stories](../guides/data-stories.md), "The
state drill-down transition".

## Decisions

- **No new dependency.** kin uses GSAP; this uses `requestAnimationFrame` and a 2D canvas. The page already loads GSAP
  for the scroll engine, but the transition doesn't need a timeline library, and a canvas keeps it independent of the
  scroll engine.
- **Canvas overlay, then the real SVG.** The county map has around 4,000 dots for Alabama and the national map around
  3,000; animating that many SVG nodes through React would drop frames. During the transition the real map stays in the
  DOM with `opacity: 0` (so the accessibility tree, focus and keyboard navigation are untouched) and a canvas draws the
  moving boxes. At the end the canvas is removed and the real map is visible.
- **End state read from the real map.** The county boxes' places, radii, colours and opacity are read from the rendered
  county SVG (`circle[data-box]`, via its screen matrix), not recomputed. So the last frame is the real map by
  construction, and a change to the county colours can't drift from the animation.
- **Pairing by map position, not by index.** Both maps use us-atlas's pre-projected Albers coordinates, so each county
  box is paired with the nearest national box of the same state in those coordinates. One child per parent carries the
  parent's box; the other children spawn from the parent, small and transparent; a parent with no child fades. No box is
  ever relabelled or given a value: it only starts somewhere else (No Fabricated Data).
- **Timing.** Lift 160 ms, flight 620 ms with exponential ease-out, stagger up to 260 ms by distance from the county
  grid's centre: about 1,040 ms in all. Other states fade and drift up to 80 px outward over about 500 ms (cubic
  ease-out). Colours cross-fade over the second part of each flight.
- **Reverse is the same plan played backwards** (`sampleAt(plan, ms, true)`), so in and out can't disagree.
- **Arrival from the home map** uses react-router navigation state (`{ drillFrom: 'national' }`), not a URL parameter:
  the URL stays the place's authority (CLAUDE.md, scope via the URL), and the flag is cleared with a `replace` once
  used so refresh and Back don't replay it.
- **Reduced motion and interruption.** With `prefers-reduced-motion` nothing is planned. A `pointerdown` or `keydown`
  inside the map during the transition ends it at once; the click then reaches the real map.
- **Waiting.** The transition can only plan once the county map has drawn. The county shapes are prefetched when the
  pointer or focus enters the national map; while the state's counts load, its national boxes stay lifted. After 10 s it
  gives up and shows the map as is.

## Where

- `web_app/src/utils/boxMorph.ts`: pure plan and sampling (`planDrillMorph`, `sampleStep`, `sampleAt`, colour mixing),
  tested in `boxMorph.test.ts`.
- `web_app/src/components/stance/MapDrill.tsx`: the wrapper and canvas, used by `StoryScreenView.tsx` on the Overview.
- `web_app/src/components/stance/nationalDots.ts`: the national grid and its colours, shared with `StoryDotMap.tsx`.

## Limits

- Only the Data Center Story has a county drill-down; topic stories highlight the state on the national map and have no
  transition.
- On a phone the county map is taller than the national map, so part of the flight lands below the fold.
- In the reverse direction the county boxes briefly overlap the legend and counts under the shorter national map while
  they gather back.
