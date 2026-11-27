---
pr: 1173
branch: feat/1146-keyboard-a11y
title: "feat(a11y): keyboard navigation and screen-reader support, WCAG 2.2 AA (#1146)"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: feat(a11y): keyboard navigation and screen-reader support, WCAG 2.2 AA (#1146)

## Summary
The PR adds keyboard and screen-reader support across the app shell, the home Browse Topics strip, the three story
maps and the story screens:

- a skip link and one `<main>` per page;
- a site-wide `:focus-visible` ring and reduced-motion CSS;
- a roving tabindex on the topic strip;
- a shared `useMapKeyboard` hook that makes each map one tab stop and announces each area through a live region;
- heading focus when the story screens page.

It also fixes the axe contrast, accessible-name and target-size findings on `/`, `/stories/data-centers`,
`/stories/guns` and `/search`, and adds a Playwright + axe suite with four keyboard walks. The reviewer found two
Important issues in `useMapKeyboard`; both are fixed in this PR and covered by a unit test. The Minor items went to
follow-up #1177. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 29 (about +700 / -95, excluding `package-lock.json`)
- Areas touched: web_app, web_docs
- Commits:
  - 2fa96f46 feat(a11y): skip link, focus ring, roving tabindex on topics, keyboard maps, story heading focus (#1146)
  - b294157d fix(a11y): WCAG 2.2 AA contrast, names and target sizes on home, stories and search; accessibility docs (#1146)
  - the review-fix commit: map keys (Enter/Space always consumed; Up/Down left to the page), `nextMapKey` tests, this review
- Range reviewed: `merge-base(origin/main)..HEAD`

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success (5b4b12da) |
| Documentation Build (Docusaurus) | success (5b4b12da) |
| Backend Tests (Python) | success (5b4b12da) |
| API Types (OpenAPI -> TypeScript) | success (5b4b12da) |
| PR conventions | success |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean. No keys, tokens or credentialed URLs in the added lines.
- Fabricated data in a served path: clean. The changes are colours, ARIA attributes and keyboard handlers. The live
  region and data-table text read real counts from the API.
- Personal data / privacy: clean. Nothing is stored or logged.
- Destructive or bulky data changes: clean. The lockfile adds only `@axe-core/playwright` and `axe-core` (dev).

## Strengths
- One hook (`useMapKeyboard`) gives all three maps the same keyboard behaviour. It works with `useScreenKeys`
  through `defaultPrevented`, so arrow keys on a map don't also page the story.
- The focus ring rule uses `:where()`, so its specificity is zero and existing component focus styles still win.
- Story screens focus the new heading, which announces it without trapping focus.
- The checks are reproducible, and `A11Y_REPORT` lists every violation with example nodes.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
Both were found by the reviewer, verified in the code, and **fixed in this PR**:
1. **`useMapKeyboard.tsx` handled Enter and Space only when `onActivate` was set.**
   - Effect: on `StoryCountyMap`, which has no story to open, Enter fell through to `useScreenKeys` and paged the
     story away.
   - Fix: Enter and Space are now always consumed while an area is shown.
2. **`nextMapKey` consumed ArrowUp and ArrowDown**, which blocked keyboard scrolling while a map had focus.
   - Fix: only ←/→ and Home/End move within the map; ↑/↓ are left to the page.
   - `useMapKeyboard.test.ts` covers this.

### 🔵 Nits / suggestions (Minor)
These moved to #1177:
- The stage's `onMouseLeave` clears the keyboard position while the map still has focus.
- A mouse click on a map seeds the first area's card through `onFocus`.
- `/home-original` has no `<main>`, so the skip link has nothing to move to.
- The e2e suite needs a live API and isn't in CI.
- Moderate and minor axe findings remain:
  - `aria-allowed-role` and `landmark-unique` on the data-centers story;
  - `heading-order` and `page-has-heading-one` on home.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | `feat/1146-keyboard-a11y`; the PR body says `Closes #1146`; the issue has all four parts |
| Conventional Commits | Yes | Co-author trailer on each agent commit |
| No fabricated data | Yes | Scan clean |
| New Python in `packages/` | N/A | No Python |
| dbt for transformations | N/A | |
| Naming / Keys / Calendar years | N/A | |
| Scope label matches filter | Yes | Untouched. The search-level button's name now includes the place label it shows |
| Match evidence on filtered tiles | N/A | |
| Docs | Yes | New `web_docs/docs/development/accessibility.md`, kebab-case, with frontmatter |
| Telemetry and logging | N/A | |
| Tests | Yes | Playwright + axe suite (8 tests) and a `nextMapKey`/`westToEast` unit test |
| Shared libraries | N/A | |

## Test Coverage
Run locally on the merged branch:
- `npx playwright test --trace off` against a dev server on :5199, proxied to the :8001 API: 8 passed. The four axe
  pages have 0 serious or critical violations. After the review fix, the keyboard walks were re-run: 4 passed.
- `npx vitest run`: all passing (561 tests before the new test file, plus its 4).
- `npx tsc --noEmit` is clean, and `npm run build` succeeds for both web_app and web_docs.

Not covered in CI: the e2e suite, which needs a live API (#1177).

## Verdict
approve-with-nits. Both Important findings are fixed in this PR, and the Minor ones are tracked in #1177.
