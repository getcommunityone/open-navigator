---
pr: 978
branch: fix/975-tabs-sections-one-look
title: "fix(web_app): main tabs scroll to home sections; one type system and button site-wide"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: general-purpose subagent (read-only, two passes) and coordinator (third round)
head_sha: see branch head
verdict: approve-with-nits
---

# PR Review: main tabs scroll to home sections; one type system and button site-wide

## Summary

Closes #975.
- **Tabs:** every header tab scrolls to a home section (`#search`, the new `#data-stories`, `#how-it-works`,
  `#impact`), and the detail pages open from actions there.
- **Type:** one system site-wide (Playfair Display, Source Sans 3, IBM Plex Mono).
- **Colour and buttons:** the brand teal is Tailwind `primary`, and one teal pill is the primary button.

Decision page: `web_docs/docs/development/site-look-and-navigation.md`.

Two independent passes said **request-changes**. Every Blocking and Should-fix finding is fixed: the second pass
confirmed the first round, and the coordinator verified the third round in a browser.

## Findings and their fixes

### 🔴 Blocking (fixed)
1. **The Data Stories tab dropped `?state=&city=`.** Fixed: tabs carry the place (`/?state=…&city=…#section`).
2. **The heading rule beat component classes.** Its specificity was (0,3,1) after the second round. Fixed:
   `:where(…)` keeps it at zero, so `.sh-title`, `.stance-dialog-title` and utilities win again.

### 🟡 Should fix (fixed)
- **Contrast:** `primary-500` (white text in scope toggles) is `#0f766e`, which gives 5.5:1 (AA).
- **Settle scroll:** it stops on pointer, hash and history changes too.
- **Scroll-spy:** it clears between sections.
- **Floating answer buttons:** they keep their shape (no pill).
- **Small h2s:** they keep the body face.
- **Carried place:** it moves the whole home page. HomeV9 reads the URL place ahead of the saved location without
  overwriting it, and picking a place clears it. In the browser, from `/stories?state=TX&city=Austin` the scope chip
  reads "📍 Austin" and the section reads "Austin, Texas".
- **Tab on home with an encoded city:** it compares the place by value and always scrolls. In the browser,
  `/?state=CA&city=Los%20Angeles` lands How It Works at 72px with the URL unchanged.

### 🔵 Nits (open)
- `primary-500` and `primary-600` are now the same teal, so `bg-primary-500 hover:bg-primary-600` has no hover change.
- The home Data stories counts load on every home visit (3 calls), even off-screen.
- `@fontsource-variable/geist` is now unused in `package.json`.

## Scans
- Secrets, personal data, destructive changes: none.
- Fabricated data: none. The home counts come from the hub's endpoints, with loading and unavailable states.

## Tests
- `tsc` is clean; vitest 380; eslint has no new warnings; `vite build` OK.
- Browser:
  - Every tab lands on its section.
  - Fonts are consistent on home, search, hub and story.
  - The hub aligns with the header at x = 134.
  - At 375px, no horizontal scroll.

## Verdict

**approve-with-nits**: merge when the required checks are green.
