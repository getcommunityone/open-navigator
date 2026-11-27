---
pr: 1322
verdict: approve
---
# PR 1322 review

Scope: removes the story top-bar sound button, adds a Settings switch (default off, localStorage in try/catch), shares the existing change event with the site menu.

- Contract: matches issue #1319 (key `stance.sound`, testid `settings-story-sound`).
- Privacy: no data collected or sent; device-local boolean.
- Tests: stanceSound tests updated for the new default; tsc clean; Playwright at 1440 and Pixel 7 confirmed the button is gone and the switch toggles.
- Minimal edits to DataStory.tsx; no touch to useStoryScreens, useSwipeNav, StoryCountyMap, SiteHeader, useStoryScope or storyCaption.
- Nit (non-blocking): behaviour change, wide screens previously defaulted to on.

Nothing blocking.
