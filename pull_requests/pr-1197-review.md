---
pr: 1197
branch: fix/1191-site-navigation
title: "fix(web): site navigation — phone menu, header place control, Places link, per-page titles"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: frontend-specialist subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: fix(web): site navigation — phone menu, header place control, Places link, per-page titles

## Summary
This PR rebuilds the shared `SiteHeader` for every page:
- **Phone menu:** a real menu with a backdrop, scroll lock, Escape and route-change close, focus management and `aria-expanded`/`aria-controls`.
- **Place control:** a header control opens a shared `LocationPickerDialog`, extracted from `HomeV9`.
- **Places link:** added to the header. Impact moves to the footer, and active-link state now comes from a tested pure function.
- **Page titles:** each main page sets its own `document.title`.
- **Home 404:** the console 404 on home is gone, because coming-soon topic tiles no longer request caption facts.

The read-only reviewer found two real bugs in the first commit, both fixed in the follow-up commit:
- a race between the place-pick navigation and the page remount;
- a home level-picker regression.

It also raised a missing focus trap on the picker, now fixed. The remaining nits don't block. Playwright on desktop and iPhone 13 confirms the behaviour end to end.

## Scope of Change
- Files changed: 22 (about +700 / -250, excluding generated files)
- Areas touched: web_app, web_docs, pull_requests
- Commits: 2e4f78a8 fix(web): site navigation — phone menu, header place control, Places link, per-page titles (#1191); 57e7b1e4 merge origin/main; 366608db bot auto-review; follow-up fix commit with this review
- Range reviewed: `fbecec6f..HEAD`

## CI Status
| Check | Status |
|---|---|
| Frontend Build | success on 57e7b1e4 |
| Documentation Build | success on 57e7b1e4 |
| Backend Tests | success on 57e7b1e4 |
| API Types | success on 57e7b1e4 |
| PR conventions | success |

The follow-up commit is re-checked before merge.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean.
- **Fabricated data:** clean.
  - No place is hard-coded. The control reads "Find your town" when nothing is set.
  - Titles use real names: the registry topic, the catalog topic, or the API's `jurisdiction_name`. They fall back to "Meetings" rather than inventing a name.
  - Coming-soon tiles keep their static blurb; no caption is invented.
- **Personal data:** clean.
  - The picked place is saved in `localStorage` (the existing `LocationContext` behaviour) and put in the URL as `state`/`city` only.
  - Nothing new is logged or stored server-side.
- **Destructive data changes:** none.

## Strengths
- One header for every page. The `sh-*` class rename stops HomeV9's stale `.v9 .v9-nav` rules from restyling the header on home, which was the cause of the home-only centring.
- `activeNavKey`, `headerPlace`/`searchAfterPick` and `documentTitle` are pure and unit-tested.
- The picker logic now lives in one place (`usePlacePick`), so home and header picks behave the same.
- The 404 fix is at the source: `/api/topics` in prod has no curated `bike-lanes` topic, so the API's 404 is correct. The client simply stops asking for tiles that aren't live.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
Both are fixed in the follow-up commit.

1. **Page remount could beat the URL commit.**
   - Where: `hooks/usePlacePick.ts` and `components/Layout.tsx`.
   - Problem: the first version remounted the routed page on a window event fired by `setTimeout(0)`. React Router wraps navigations in `startTransition`, so the default-priority key bump could render first, and the page would remount with the old `?state=&city=`.
   - Verified by reading react-router 7's `startTransition` use.
   - Fix: the pick's navigation now carries a marker in history state, and `Layout` bumps the Outlet key in an effect keyed on that marker. The remount therefore follows the committed URL, and only when the address actually changed. This also addresses the old "remount on every pick" nit.
   - Re-verified with Playwright: after a pick on `/search?q=fluoride`, the page shows `Tuscaloosa, AL` scope with `?state=AL&city=Tuscaloosa`.
2. **Home level picker didn't follow a pick.**
   - Where: `pages/HomeV9.tsx`.
   - Problem: `levelPicked` was reset only by the delayed event, after the `[locCity, locState]` effect had already skipped. A reader on National stayed on National after picking a town.
   - Fix: the event is now dispatched synchronously, and the listener also bumps a `pickTick` state that is in the effect's deps. The level always re-derives for the new place, whatever order the renders land in.

### 🔵 Nits / suggestions (Minor)
1. **Header label vs page scope on unscoped pages** (`SiteHeader.tsx`, the place control).
   - With a saved place and no URL place, the control names the saved town while, for example, `/stories/guns` shows national data.
   - Kept on purpose. The control is the reader's town picker, labelled `Your town: … Change` (aria-label and tooltip). It is not the page's scope label: each scoped page keeps its own label (CLAUDE.md canonical pattern). Header links carry only the scope already in the URL, so no page claims a filter it didn't apply.
2. **Picker focus trap and scroll lock** (`LocationPickerDialog.tsx`). Fixed in the follow-up commit: Tab is trapped in the dialog and body scroll is locked while it is open.
3. **Phone menu modality** (`SiteHeader.tsx`). The panel is `role="dialog"` with the ☰/✕ toggle outside it, and the manual Tab trap includes the toggle. That is acceptable for a disclosure-style menu and not changed.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | #1191 has Problem / Done when / Contract / Read first; branch `fix/1191-site-navigation`; `Closes #1191` |
| Conventional Commits | ✅ | co-author trailer present |
| No fabricated data | ✅ | scan above |
| New Python in `packages/` | n/a | no Python |
| dbt for transformations | n/a | |
| Naming | n/a | |
| Keys | n/a | |
| Calendar years | n/a | |
| Scope label matches filter | ✅ | scope stays in `?state=&city=`; a pick rewrites it and remounts the page so label + data move together; header links carry the URL scope |
| Match evidence on filtered tiles | n/a | |
| Docs | ✅ | new `guides/site-navigation.md`; `development/site-look-and-navigation.md` updated |
| Telemetry and logging | n/a | no new API work |
| Tests | ✅ | `navActive.test.ts`, `useDocumentTitle.test.ts`, `headerPlace.test.ts` |
| Shared libraries | n/a | |

## Test Coverage
Checks run locally:
- `npx tsc --noEmit`: clean.
- `npx vitest run`: 66 files, 608 tests pass.
- `npm run build` and the docs build: pass.

The unit tests cover the active-link rule, the title helper and hook, and the place label and URL-after-pick logic. The menu and dialog behaviour is covered by the Playwright run (desktop 1440x900 and iPhone 13) rather than unit tests, because the app has no DOM test environment. That run covered:
- titles and active links on `/`, `/stories`, `/search?q=fluoride`, `/jurisdictions`, `/stories/guns`, `/stories/data-centers` and a jurisdiction meetings page;
- no horizontal scroll at 1440px, 980px or on iPhone, and no API 404s;
- the phone menu: open state, scroll lock, focus, 48px left-aligned items, a full-width login button, and closing on Escape, backdrop tap and route change;
- the picker opening from both the header and the menu, with focus returning on close;
- a pick updating the URL, the label and the page scope.

## Verdict
**approve-with-nits.** The two Important findings are fixed and re-verified, and nothing blocks merge once CI on the follow-up commit is green.
