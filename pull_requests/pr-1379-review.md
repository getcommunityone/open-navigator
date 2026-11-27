---
pr: 1379
branch: fix/1378-remove-places-nav
title: "fix(web): remove Places from the top menu"
author: cursor-agent
reviewed_at: 2026-11-27
reviewer: coordinator
verdict: approve
---

## Scans

- Secrets / fabricated data / personal data / destructive: none

## Findings

None.

## Notes

Places removed from `navItems` (desktop + mobile). Route kept. `navActive` tests updated.

## Local checks

- `vitest run src/utils/navActive.test.ts` → 4 passed

