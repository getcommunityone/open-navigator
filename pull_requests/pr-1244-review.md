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

DataStory's screen machine moved into `useStoryScreens`. A read-only reviewer compared it line by line with
`origin/main` and found no behaviour change. It then took on #1243's additions (re-aimed jumps, the swipe, the cover
mark) and one fix of its own, both described below. The browser checks pass at three devices on three topics.

The title names the selected place from 5 meetings where its public spoke ("Alabama mostly opposes data centers."). Its
topic control lists every live story on both story pages.

Verdict: approve-with-nits. The read-only reviewer's Important findings are fixed. The nits left are pre-existing
evidence gaps on a few tiles, plus the convergence with #1243.

## Scope of Change
- Files changed: 18 (+1720 / -582, excluding this review file)
- Areas touched: web_app, web_docs
- Commits:
  - be65a9d4 feat(stories): the title names the selected place from 5 meetings, and its topic control lists every live story
  - 113a143a feat(stories): topic stories go screen by screen like the Data Center Story, with swipe
  - 013cc20d feat(stories): topic screen headlines are short statements without counts; shared swipe hook
  - cc234b45 feat(stories): topic stories get one fixed Next, a Close (x) and no Next story button
  - merges of `origin/main` (#1240, #1248, #1235, #1243, #1250, #1247, #1254, #1257, #1259, #1263) and the bot review commits. The #1243 merge
    took its shared `StoryNextButton` / `StoryClose` / `ScopeBar` / `StoryBottomBar` over this branch's own versions,
    and folded its DataStory machine changes into `useStoryScreens`.
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

Found while testing the later additions, verified and fixed in be65a9d4:
- `useStoryScreens`: the cover observer measured its offset once at mount. When the title grew after load (a longer
  conclusion on a phone), a reader settled on screen 1 still read as "on the cover", so the fixed Next started the story
  again. This reproduced on Pixel 7 at `/stories/guns?state=OH`, where the step-through got stuck on the Overview. The
  settled hold now sets `onCover`. This also guards the Data Center Story, and story-flow passes there.
- `TopicStory`: the screens array was memoised on the availability string, so a screen's data turning from loading to
  ready re-ran the landing effect. It now memoises on the screen ids, as DataStory does with `keepKey`.

### 🔵 Nits / suggestions (Minor)
- **Fixed:** the Companies context counted named companies but the list showed every row. The list now shows `named`
  only.
- **Fixed:** a `?city=` deep link was narrowed to its state silently. It now shows the same "drawn by state" note.
- **Open (pre-existing):** a decision tile without a `description`, or a passage row without an `excerpt`, has no match
  evidence (CLAUDE.md, "Show the Match Evidence"). This was true of the old page too; it is more visible one screen at a
  time.
- **Resolved:** the Close and Next components are now the shared #1243 pair, the same on both stories.
- **Resolved:** titles are the short conclusion after #1243. With the new lower tier
  (`LEAN_MIN_MEETINGS` = 5) they name the selected place. Vitest covers the tier boundaries: majority, split, under 5,
  and "hates" at the floor.
- **Open (wording):** a title whose words don't name the topic shows it in brackets ("Ohio mostly favors gun limits (gun
  control ▾)."), so the topic stays a control. It reads plainly; the owner may prefer another spot.

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
| Docs | ✅ | `guides/data-stories.md` section, `development/topic-story-screens.md`, and a dated decision in `development/story-captions.md` (owner's words) |
| Telemetry and logging | n/a | No new fetch paths |
| Tests | ✅ | `topicStoryScreens.test.ts`, `useSwipeNav.test.ts`; e2e `story-next.check.mjs` |
| Shared libraries | n/a | |

## Test Coverage
- Unit: `planTopicScreens` / `droppedNote` (keeps, drops, absent, error), `swipeDirection`, the `pickCaption` lower
  tier, `withTopicBlank` and `storyTopicOptions`.
- Local: `npx tsc --noEmit` clean; `npx vitest run` 78 files, 730 passed; `npm run build` and the docs
  build pass.
- Browser (after the final merge): `node e2e/story-next.check.mjs` passes on all 9 step-throughs and 4 title checks.
  The title checks run at Pixel 7 and 1440×900 on `/stories/data-centers?state=AL` ("Alabama mostly opposes data
  centers.") and `/stories/guns?state=OH` ("Ohio mostly favors gun limits (gun control)."). Each confirms the place word
  is the place control, the 20 live stories are listed, and a switch keeps `?state=` and opens the Overview.
  `node e2e/story-flow.check.mjs` passes on the Data Center Story.
- Step-throughs: `node e2e/story-next.check.mjs` passes on all 9 runs (Pixel 7, iPhone 13 and 1440×900 on
  `/stories/guns`, `/stories/pickleball?state=CA` and `/stories/water-fluoridation`). Each run steps every screen with
  Next, a segment and a swipe. It checks that each step lands, Next and Close keep their spots, and no Next story button
  shows.
- `story-nav.check.mjs` passes on the Data Center Story. It flakes under load on main as well (#1249).
- Not covered: Escape-to-close and reduced motion have no automated or manual check in this PR. Reduced motion runs
  through the shared `useStoryScreens` path, which is unchanged from DataStory.

## Verdict
approve-with-nits. Nothing blocking: merge once the required checks are green on the head commit.
