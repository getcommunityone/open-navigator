# Final fix report — #969 challenge scroll reveal

## Snap mode fenced at act grain (fixed)

**Finding:** In `useActs` snap path, `fence()` and `settle()` used `stops()` built from one scroll position per `[data-panel]` (cover + acts). `holds()` already listed `[data-stop]` positions (finding / question / reveal), and `onWheel` already stepped through `holds()`. A hard flick could jump past internal stops while wheel advanced one stop at a time.

**Fix (`web_app/src/components/stance/useActs.ts`, snap only):**

- Added cover to snap `holds()` (kind `cover`) so fence/settle/wheel share one list.
- Replaced act-grain `stops()` with `snapPositions()` derived from `holds().map(h => h.pos)` (sorted).
- `fence()` and `settle()` now use `snapPositions()`; anchor tracks the nearest hold, not act top.
- `goToRound()` skips `cover` when resolving round 0 (matches pinned: `kind === 'q' | 'end'`).

**CSS (`web_app/src/styles/stance.css`):**

- `[data-mode='snap'][data-beats]`: acts are `height: auto`, no act-level `scroll-snap-align`.
- `.stance-stop` gets `scroll-snap-align: start` / `scroll-snap-stop: always` so native snap can land on stops.
- Inner `.stance-grid` / `.stance-end-body` no longer forced to single-viewport scroll in challenge snap.

**Unchanged:** Pinned Lenis path; no quiz copy.

**Verify:** Phone width, challenge — one wheel gesture = one hold; swipe fling fences to next hold not next act; `goToStop` + ProgressRail still align.