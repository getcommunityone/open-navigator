---
pr: 1334
branch: feat/1331-segmented-place-toggle
title: "feat(web_app): one segmented place/National toggle in the header on desktop and phone"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: claude-code
head_sha: deb5eeb456e5f3a73f8696b333e67b6d03965dc0
verdict: approve-with-nits
---

# PR Review: one segmented place/National toggle (#1331)

## Summary

Shared `PlaceScopeToggle` replaces the desktop chip and "x National" button and the phone toggle. URL behaviour
(`?scope=national` on home, drop `?state=&city=` on scoped pages) is unchanged; the label is the active scope.

## Findings

- No blocking findings. tsc clean; vitest passes; both e2e checks pass at desktop and phone widths; header fits 360px.
- Nit: the phone ZIP field is gone; "Find your town" and the active town half open the shared picker instead (the request asked for this).
- Nit: the mobile menu still carries its own place rows (`sh-mplace`); left as is.
- No fabricated data, no privacy impact.
