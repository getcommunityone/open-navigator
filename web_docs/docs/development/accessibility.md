---
title: Accessibility
description: The keyboard and screen-reader patterns the web app uses (skip link, focus ring, roving tabindex, keyboard maps, story screens, reduced motion) and how to run the automated WCAG 2.2 AA checks.
---

# Accessibility

The web app targets **WCAG 2.2 AA**. Every page can be used with the keyboard alone, and a screen reader hears
what changes. This page covers the patterns the app uses and how to run the checks that keep them working (#1146).

## Site-wide

- **Skip link.** `SkipLink` (`web_app/src/components/SkipLink.tsx`) is the first tab stop on every page. It
  stays off screen until it has focus, then moves focus to the page's `<main id="main-content">`. `Layout` and
  `HomeV9` each render one `<main>`. Pages inside `Layout` must not add a second one; use a `<div>`.
- **Focus ring.** `index.css` gives every interactive element a 2px teal `:focus-visible` outline. The rule is
  wrapped in `:where()`, so its specificity is zero and a component's own focus style still wins. Don't remove an
  outline unless you replace it with something just as visible.
- **No positive `tabindex`.** Only `0` (in the tab order) and `-1` (focusable from code) are allowed.
- **Icon-only controls have a name.** Give the button an `aria-label` and put `aria-hidden` on the icon. When a
  control also shows text, its `aria-label` must include that text (for example `"Tuscaloosa, location level"`),
  or leave the label off.
- **Contrast.** Text is at least 4.5:1 against its background. The old light greys (`#8a958f`, `#a8a29e`) and the
  bright accents (`#0d9488`, `#059669`, `#ea580c`, `#2563eb`) fail as text colours. Use `#5f6b66`, `#78716c`,
  `#0f766e`, `#047857`, `#c2410c` and `#1d4ed8` instead. A lens pill darkens its accent for its text with
  `color-mix(in srgb, <accent> 70%, #000)`.
- **Target size.** Small controls, like pager dots and the save bookmark, sit in a 24 x 24px button. The visible
  dot is an inner `aria-hidden` span.
- **Reduced motion.** With `prefers-reduced-motion: reduce`, `index.css` cuts animations and transitions to
  nothing and turns off smooth scrolling. Scripted scrolls check the same setting (for example `behavior()` in
  `HomeTopicStrip`).

## Browse Topics strip (home)

The strip follows the WAI-ARIA toolbar pattern, with a **roving tabindex**:

- Only one tile has `tabindex="0"`: the selected topic, or else the first. Tab enters the strip on that tile, and
  the next Tab leaves it.
- ←/→ move between tiles, wrapping at the ends, and Home/End jump to the first and last. The focused tile scrolls
  into the carousel's view.
- Enter or Space picks a tile. A guide tile is a link, and Space follows it too.
- A "Coming soon" tile with nothing behind it is `role="button" aria-disabled="true"`, so it's announced as
  unavailable but the arrow keys still reach it.
- The previous and next arrows and the pager dots have labels. A hidden hint (`#home-topics-keys`) tells screen
  readers which keys to use.

## Story maps

`useMapKeyboard` (`web_app/src/hooks/useMapKeyboard.tsx`) gives each box or dot map (`StoryStatesMap`,
`StoryDotMap`, `StoryCountyMap`) the same behaviour:

- The map's `<svg>` is **one tab stop** (`role="group"`, `aria-roledescription="map"`). Focusing it selects the
  page's scoped state, or the first area.
- The ←/→ arrow keys move between areas from west to east (↑/↓ still scroll the page) (`westToEast`). Each move shows the area's quote card, as
  hovering does, and announces it through a polite live region, for example "Alabama: 12 meetings; …".
- Enter or Space opens that area's story, where the map has one. Escape hides the card. Moving focus off the map
  and its card hides the card too.
- Every map still has its **"Show data table"** disclosure, which lists the same numbers as plain table rows.

## Story screens

When the arrow keys page between screens in a data story (`DataStory`, `onSettled`), focus moves to the new
screen's heading, given `tabindex="-1"`. A screen reader then reads where you are. Tab goes on to that screen's
controls (Back, then Next in `ScreenNav`), and ←/→ keep paging, because a heading isn't a form control. The
floating Next (`FloatingNext`) is `aria-hidden` and out of the tab order, because it repeats the screen's own
Next button.

## Running the checks

Two kinds of automated check live in `web_app/e2e/a11y.e2e.ts`, run with Playwright (`web_app/playwright.config.ts`):

- **axe** (`@axe-core/playwright`) runs on `/`, `/stories/data-centers`, `/stories/guns` and `/search?q=fluoride`
  with the WCAG 2.0, 2.1 and 2.2 A/AA rules plus best practice. A check fails on any **serious** or **critical**
  violation.
- **Keyboard walks**: the skip link is the first tab stop, Tab plus the arrow keys pick Guns in the topic strip,
  the home map opens a state story from the keyboard, and the story screens page with the arrow keys and move
  focus to the heading.

The checks run against a dev server that's already up. They aren't part of CI yet, because they need the
warehouse API behind the dev server.

```bash
cd web_app
npx vite --port 5199 --strictPort &                 # or use the usual dev server on 5173
A11Y_BASE_URL=http://localhost:5199 npx playwright test --trace off
# Optional: A11Y_REPORT=/tmp/axe.json writes every violation (any impact) with example nodes;
# A11Y_EXAMPLES=200 includes more example nodes per rule.
```

`VITE_API_PROXY` points a second dev server at a different API, for example
`VITE_API_PROXY=http://localhost:8002 npx vite --port 5199`. The default is `http://localhost:8001`.

Test files end in `.e2e.ts`, so `npm test` (vitest) doesn't pick them up.
