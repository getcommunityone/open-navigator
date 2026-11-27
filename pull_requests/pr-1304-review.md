---
pr: 1304
issue: 1301
verdict: approve-with-nits
---

# PR Review: feat(web_app): phone header location selector, pin + ZIP with a one-tap National toggle

## Summary
On phones, the header row now always holds the place selector: a pin + ZIP field, or a `[📍 town | National]` toggle
that switches in one tap each way. It builds on #1297's `?scope=national` and replaces that PR's phone-bar "× National".
A read-only reviewer (frontend-specialist subagent, against this rubric, `AGENTS.md` and `CLAUDE.md`) found three
should-fix issues and five nits. All three should-fix issues and four of the nits are fixed in the follow-up commit.
Verdict: approve-with-nits.

## Scope of Change
`components/HeaderPlacePhone.tsx` (new) and its test, `components/SiteHeader.tsx`, `utils/headerPlace.ts` and
`utils/headerPlacePhone.test.ts`, `e2e/phone-place-header.check.mjs` (new), `e2e/place-scope.check.mjs` (selector
widened), and the site-navigation docs.

## CI Status
| Check | Status |
|---|---|
| vitest | 795/795 passed |
| tsc --noEmit | clean |
| e2e/phone-place-header.check.mjs (iPhone 13 + iPhone SE, production API) | 11/11 ok |
| e2e/place-scope.check.mjs | Not runnable here (map shapes don't load in the sandbox); its header step was run by hand and passes |
| GitHub required checks | pending at the time of writing |

## Scans (secrets, fabricated data, personal data, destructive data changes)
No secrets, no fabricated data and no data changes. Privacy: the ZIP is looked up and not stored beyond the existing
saved location. The "way back" place is kept only in memory for the visit.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- ~~A deep link with nothing saved was a dead end after National.~~ **Fixed:** the place just left is kept for the visit
  and is the way back. There is a new unit test and an e2e step.
- ~~Focus was lost when changing the ZIP, and `editing` persisted across routes.~~ **Fixed:** the field takes focus, and
  the edit state resets on route change.
- ~~The Go and ✕ buttons were 32px.~~ **Fixed:** the buttons are 40px and the toggle and ZIP pill are 44px tall.
### 🔵 Nits / suggestions (Minor)
- ~~The active town's action was named only in `title`.~~ Fixed: its `aria-label` is "Tuscaloosa, AL, change ZIP".
- ~~A URL place different from the saved town came back as the saved town.~~ Fixed by the same "way back" place.
- ~~Stale `.sh-national-phone` CSS.~~ Removed.
- ~~Fit at 360px was unverified.~~ Checked: there is no sideways scroll at 320px, and town labels are shorter below 380px.

## Repo-Rule Compliance
| Rule | Status | Note |
|---|---|---|
| Issue first, four parts | ✅ | #1301 |
| Branch / `Closes #` | ✅ | `feat/1301-mobile-location-header` |
| Scope label matches filter | ✅ | The pressed side always equals the page's URL scope |
| Filters via URL | ✅ | `?state=&city=`, `?scope=national` |
| Docs with the change | ✅ | guides/site-navigation.md, development/site-look-and-navigation.md |
| Privacy | ✅ | Nothing new stored |

## Verdict
approve-with-nits.
