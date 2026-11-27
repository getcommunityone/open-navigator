---
pr: 1244
branch: feat/1224-topic-story-screens
title: "feat(stories): topic stories go screen by screen like the Data Center Story, with swipe"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: subagent (frontend-specialist, read-only) and coordinator; the automated rubric review (#648) is folded in
verdict: approve-with-nits
---

# PR Review: feat(stories): topic stories go screen by screen like the Data Center Story, with swipe

## Summary

Every topic story (`/stories/<slug>`) is now told screen by screen on the Data Center Story's machinery. The page has a
cover, then these screens: Overview, Over time, Who spoke, Companies, What was said, Decisions and Recap. A screen with no
data for the place drops, and the cover names it. The owner's 2026-11-27 layout is applied: one green Next fixed at the
bottom right (Done on the last screen), Close (×) at the top right, and no Next story button, crumb or "Showing:" row.
Back is inline on wide screens and in the phone bar. Swipe and keys also move between screens.

DataStory's screen machine moved into `useStoryScreens` unchanged. A read-only reviewer compared it line by line with
`origin/main` and found no behaviour change. The browser checks pass at three devices on three topics.

Verdict: approve-with-nits. The read-only reviewer's Important findings are fixed. The nits left are pre-existing
evidence gaps on a few tiles, plus the convergence with #1243.

## Scope of Change
- Files changed: 18 (+1720 / -582, excluding this review file)
- Areas touched: web_app, web_docs
- Commits:
  - 113a143a feat(stories): topic stories go screen by screen like the Data Center Story, with swipe
  - 013cc20d feat(stories): topic screen headlines are short statements without counts; shared swipe hook
  - cc234b45 feat(stories): topic stories get one fixed Next, a Close (x) and no Next story button
  - merges of `origin/main` (d04f6244 #1240, 182be05c #1248) and the bot review commits
- Range reviewed: `merge-base(origin/main)..HEAD`

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success (run 45953143211, on c6700648) |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| Docker Build Test | skipped (no Docker files) |
| PR conventions | failed once: another session overwrote this PR's description with #1248's ("Closes #1237"). The description is restored ("Closes #1224"); re-run on the next push. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean.
- **Fabricated data:** clean. Every number comes from an API response: `caption-facts` (meetings, the AI-reading counts),
  `/topics/{id}/meetings` `total`, `/search` `type_totals.decisions`, the companies list, and `positionVerdict` over
  those counts. Loading and failed states say so and show no figure. An empty screen drops instead of showing zeros.
- **Personal data:** clean. Nothing is stored or logged. Quotes are the existing transcript excerpts.
- **Destructive data changes:** none. No warehouse or data files are touched.

## Strengths
- One screen machine for both stories (`useStoryScreens`) and one screen frame (`StoryScreenFrame`). The topic story
  is a configuration (`planTopicScreens`), not a copy of the machine.
- An honest drop rule with its reason on the cover. The limits that remain (no county view, no unit matrix, state grain)
  are stated on the page and in the design note.
- The scope label, URL and queries move together. City input degrades to its state with a note.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
Both found by the read-only reviewer, verified and fixed in cc234b45:
- `TopicStory.tsx`: the Who spoke headline's loading and empty text said "AI reading", against the owner's
  no-"AI reading"-in-headlines rule. It now reads "Loading who spoke…" and "No position of the public is on record for
  these meetings yet."
- `TopicStory.tsx`: the `aria-live` region re-announced each screen's loading placeholder and then its final headline.
  It now announces "<word>, N of M" once per screen change.

### 🔵 Nits / suggestions (Minor)
- **Fixed:** the Companies context counted named companies but the list showed every row. The list now shows `named`
  only.
- **Fixed:** a `?city=` deep link was narrowed to its state silently. It now shows the same "drawn by state" note.
- **Open (pre-existing):** a decision tile without a `description`, or a passage row without an `excerpt`, has no match
  evidence (CLAUDE.md, "Show the Match Evidence"). This was true of the old page too; it is more visible one screen at a
  time.
- **Open (convergence):** `StoryNextButton` and `StoryClose` are topic-story components built to the owner's
  2026-11-27 spec. #1243 is building the Data Center Story's pair. When both land they should share one component.
- **Open:** the header title still carries counts and "(AI reading)", from `pickCaption`. #1243 rewrites `pickCaption`
  to the short conclusion for every story, including the topic stories.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `feat/1224-topic-story-screens`; `Closes #1224`; the issue has all four parts. Follow-up flake filed as #1249 |
| Conventional Commits | ✅ | All commits typed and scoped, with the co-author trailer |
| No fabricated data | ✅ | See scans |
| New Python in `packages/` | n/a | No Python |
| dbt for transformations | n/a | |
| Naming | n/a | |
| Keys | n/a | |
| Calendar years | n/a | |
| Scope label matches filter | ✅ | `?state=` drives the label, queries and links; city degrades to its state with a note (#1186) |
| Match evidence on filtered tiles | ⚠️ | Passages and decisions render the server's `<mark>` snippets through `highlightSnippet`; rows missing a snippet are a pre-existing gap |
| Docs | ✅ | `guides/data-stories.md` section plus `development/topic-story-screens.md` |
| Telemetry and logging | n/a | No new fetch paths |
| Tests | ✅ | `topicStoryScreens.test.ts`, `useSwipeNav.test.ts`; e2e `story-next.check.mjs` |
| Shared libraries | n/a | |

## Test Coverage
- Unit: `planTopicScreens` / `droppedNote` (keeps, drops, absent, error) and `swipeDirection`.
- Local: `npx tsc --noEmit` clean; `npx vitest run` 77 files, 707 passed / 1 skipped; `npm run build` and the docs
  build pass.
- Browser: `node e2e/story-next.check.mjs` passes on all 9 runs (Pixel 7, iPhone 13 and 1440×900 on
  `/stories/guns`, `/stories/pickleball?state=CA` and `/stories/water-fluoridation`). Each run steps every screen with
  Next, a segment and a swipe. It checks that each step lands, Next and Close keep their spots, and no Next story button
  shows.
- `story-nav.check.mjs` passes on the Data Center Story. It flakes under load on main as well (#1249).
- Not covered: Escape-to-close and reduced motion have no automated or manual check in this PR. Reduced motion runs
  through the shared `useStoryScreens` path, which is unchanged from DataStory.

## Verdict
approve-with-nits. Nothing blocking: merge once the required checks are green on the head commit.
