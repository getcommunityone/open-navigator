---
pr: 1210
branch: fix/1203-all-data-stories-index
title: "fix(stories): /stories lists every data story for the place in scope"
author: johncbowyer
reviewed_at: 2026-11-26
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve
---

# PR Review: /stories lists every data story for the place in scope

## Summary
The owner reported that "All data stories" did not lead to all data stories: `/stories` was still the data-center hub with one card. This PR turns `/stories` into the index of every story. There is one card per story, in the home Browse topics order (Data centers first, guides left out). Each live card carries the shared caption-picker title for the page's `?state=&city=`, the scoped meeting count from the caption facts and a Start link that keeps the place. Topics with no meetings read "Coming soon" with no link. The data-center counts row and Who spoke for and against are kept as a `<details>` on the Data centers card. The reviewer found nothing Critical. Its two Important findings (contrast on coming-soon cards, and a card with no name while its title loads) and two Minor ones are fixed in 88b94ac8. Verdict: approve.

## Scope of Change
- Files changed: 6 (+410 / -152)
- Areas touched: web_app (pages/DataStories.tsx, utils/storyIndex.ts + test, styles/stance.css appended block, one `title` attribute in HomeTopicStrip.tsx), web_docs (guides/data-stories.md, "The hub")
- Commits:
  - 8eea5dad fix(stories): /stories lists every data story, with its title, meetings and Start for the place in scope
  - 0c8f55db Merge remote-tracking branch 'origin/main' into fix/1203-all-data-stories-index (conflict in DataStories.tsx resolved: kept the index and added #1191's `useDocumentTitle`)
  - 88b94ac8 fix(stories): legible coming-soon cards, named cards while titles load, native disclosure marker
- Range reviewed: `5be3e1d5..88b94ac8`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | pass (0c8f55db) |
| Documentation Build | pass (0c8f55db) |
| API Types | pass (0c8f55db) |
| Backend Tests | running at review time (no Python changed) |
| PR conventions | pass |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean.
- Fabricated data: clean. Every figure on a card (meetings, the title's numbers) comes from `GET /api/topics/{slug}/caption-facts` for the exact scope. `factsForScope` drops a response for any other scope, and a missing count is never shown as zero. Numbers in `storyIndex.test.ts` are labelled test stand-ins.
- Personal data: clean. Nothing is stored or logged.
- Destructive data changes: none.

## Strengths
- The order and the live / coming-soon rule reuse `buildTiles`, so the index and the home strip can't drift apart.
- The scope label, the facts query keys, the titles and every Start link all read the same URL-derived scope.
- The data-center record loads only when its detail is opened, so the index stays light.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- ~~`stance.css` `.stories-card.is-soon { opacity: 0.75 }` faded the card's text below contrast.~~ Fixed in 88b94ac8: the card keeps a dashed border and only the title uses `--ink-2`.
- ~~`DataStories.tsx`: while facts load, the `h2` is `visibility:hidden`, so `aria-labelledby` named nothing.~~ Fixed in 88b94ac8: while pending, the article is named by `aria-label={card.title}`.
### 🔵 Nits / suggestions (Minor)
- ~~`.stories-detail summary { display:flex }` removed the disclosure triangle.~~ Fixed: `display: list-item`.
- ~~A live card with no meetings in the place showed only the generic blurb.~~ Fixed: it now reads "No meetings on record in <place>." once the facts answer.
- Before the catalog answers, only the Data centers card shows, and the rest appear afterwards (a layout jump). Kept on purpose, so the page never shows a false "coming soon".

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | yes | #1203 has the four parts; branch `fix/1203-…`; `Closes #1203` |
| Conventional Commits | yes | co-author trailer on each commit |
| No fabricated data | yes | see scans |
| New Python in `packages/` | n/a | |
| dbt for transformations | n/a | |
| Naming / Keys / Calendar years | n/a | |
| Scope label matches filter | yes | "All data stories · <scope>" is driven by `?state=&city=`, as are the queries and links; broaden controls are kept on phones |
| Match evidence on filtered tiles | n/a | not a content filter |
| Docs | yes | `web_docs/docs/guides/data-stories.md` "The hub" rewritten |
| Telemetry and logging | n/a | |
| Tests | yes | `storyIndex.test.ts` covers order, the live / coming-soon split, guides excluded, the registry-question title and scoped or stale meeting counts |
| Shared libraries | n/a | |

## Test Coverage
- `tsc --noEmit` is clean. `npx vitest run` passes (67 files, 616 tests, after the merge). `npm run build` and the docs build pass locally.
- Playwright, at 1440x900 and on iPhone 13, against a local Vite on the local API:
  - The home "all" arrow and the end-of-story "All data stories" link both land on `/stories` ("All data stories · National", 20 live cards).
  - `/?state=AL` → `/stories?state=AL` ("· Alabama"), and every Start link is `?state=AL`.
  - No page errors.

## Verdict
Approve. Nothing is blocking. Merge once the required checks are green on the head commit.
