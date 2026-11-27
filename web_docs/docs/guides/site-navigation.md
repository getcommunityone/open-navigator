---
title: Site navigation
description: The shared header on every page — its links, the place control, the phone menu and per-page titles (#1191).
---

# Site navigation

Every page, home included, renders one header: `web_app/src/components/SiteHeader.tsx`. Change it there and it changes
everywhere. Issue: [#1191](https://github.com/getcommunityone/open-navigator/issues/1191). Why the tabs scroll to home
sections: [Site look and navigation](../development/site-look-and-navigation.md).

## Links

| Link | Goes to | Lit on |
| --- | --- | --- |
| Data Stories | home `#data-stories` | the section in view on home; `/stories*`, `/challenge*` |
| Places | `/jurisdictions` | `/jurisdictions*`, `/jurisdiction/*` |
| Search | home `#search` | the section in view on home; `/search` |
| How It Works | home `#how-it-works` | the section in view on home |

- **Impact** is in the footer's Site links (next to Chat & Contact). It scrolls to the home page's Impact section.
- Every link carries the place in the address (`?state=&city=`), so the destination keeps the reader's scope
  (CLAUDE.md, scope label rule).
- Which link is lit is one pure function, `activeNavKey(pathname, homeSection)` in `web_app/src/utils/navActive.ts`,
  tested in `navActive.test.ts`. The lit link has `aria-current="page"`.

## Place control

The place control sits in the header on desktop and at the top of the phone menu; phones also keep a compact selector in the header row (see below). On a page whose data follows
`?state=&city=`, it names that page's **actual scope**
([#1205](https://github.com/getcommunityone/open-navigator/issues/1205), CLAUDE.md scope label rule). The scope-aware
pages are `/stories*`, `/search`, `/jurisdictions`, `/browse-topics`, `/browse-causes`, `/decisions-map`,
`/policy-questions`, `/data-centers` and `/advocacy-topics` (`SCOPED_ROUTE_PREFIXES`).

| Page state | Control |
| --- | --- |
| `?state=&city=` in the URL | `📍 Tuscaloosa, AL ▾`, which opens the picker |
| No place in the URL, a town saved | `📍 National · Use Tuscaloosa, AL ▾`. **Use** applies the saved town in one click, and ▾ opens the picker |
| No place in the URL, no town saved | `📍 National · Find your town ▾` |

**Use** goes through `usePlacePick`. It writes `?state=&city=`, and the page remounts on the new address, so the label,
the URL and the page's data change together.

On home, which has its own City / State / National level picker, and on pages that don't read `?state=` (settings,
profile, jurisdiction pages and so on), the control names the reader's town instead: the URL place, else the saved
location, else **Find your town**. Nothing is hard-coded. The rule is one pure function, `headerPlaceState(pathname,
search, saved)` in `web_app/src/utils/headerPlace.ts`, tested in `headerPlace.test.ts`.

The picker is `LocationPickerDialog` (`web_app/src/components/LocationPickerDialog.tsx`), the same dialog as the home page's
**Find your town** button. The dialog wraps the real geocoder (`AddressLookup` → `/api/geocode/search`). It closes on
Escape, the ✕ or a tap outside, and gives focus back to the control that opened it.

A pick goes through `usePlacePick()` (`web_app/src/hooks/usePlacePick.ts`):

1. It saves the place (`LocationContext`, so later visits keep it).
2. On the home page it clears any carried `?state=&city=`: home's scope is the saved place. On every other page it writes
   the pick into `?state=&city=` (and drops `page`), so the page's scope label, query and results change together.
3. When the address changed, its navigation carries a pick marker in history state. `Layout` remounts the routed page
   once that navigation has committed, because most pages read their scope from the address once, on mount. In-page
   URL changes carry no marker, so they never remount.
4. It fires `open-navigator:place-picked`; the home page resets its City / State / National level to the new place's.

The dialog traps Tab and locks the page's scroll while open.

## Phone header place selector

Below the 1024px menu breakpoint the header row keeps a place selector on every page, beside the C1 mark and outside the
☰ menu ([#1301](https://github.com/getcommunityone/open-navigator/issues/1301); owner, 27 Nov 2026: *"the location
selector should always be in the header on mobile … the simple pin + ZIP version … a way to quickly toggle national"*).
On a phone narrower than 520px the "Open Navigator" name is hidden so the selector fits; the C1 mark stays.

| State | Selector |
| --- | --- |
| No town saved or in the URL | `📍 [ZIP] Go`: a 5-digit field (numeric keyboard). The ZIP resolves through the same `resolveZipToChoices` as the picker; a ZIP that spans places lists its real choices; an unknown ZIP says so |
| A town, scope-aware page | `[📍 Tuscaloosa, AL \| National]`. The pressed side is the page's scope: the town writes `?state=&city=`, National clears them |
| A town, Home | The same toggle. National sets `?scope=national` (#1285), and the town side removes it |
| A town, a page with no place scope | `📍 Tuscaloosa, AL` only (nothing to toggle) |

One tap switches sides and the saved town is kept, so going back needs no retyping. Going to National remembers the place just left for the rest of the visit (not saved), so a deep link like `/search?state=GA` with no saved town still has a one-tap way back, and the way back is the place the page had, not a different saved town. Tapping the pressed town side opens
the ZIP field to change it (✕ keeps the current place). The toggle replaces #1285's phone-bar "× National"; desktop keeps
"× National" beside its place control. The rules are `phonePlaceState()` and `searchForScope()` in
`web_app/src/utils/headerPlace.ts` (tested in `headerPlacePhone.test.ts`). The component is
`web_app/src/components/HeaderPlacePhone.tsx`. Check it in a browser with `node web_app/e2e/phone-place-header.check.mjs`.

## Phone menu

Below 1024px the links fold into a menu behind the ☰ button.

- A full-width panel under the header, over a dimmed backdrop. The page behind it does not scroll.
- It closes on Escape, a tap on the backdrop, the ✕, or any route change. Escape, the backdrop and the ✕ give focus back
  to the ☰ button; a route change leaves focus to the new page.
- Opening moves focus into the panel, and Tab stays inside the menu. The button has `aria-expanded` and
  `aria-controls="site-mobile-menu"`.
- From the top: the place control, the four links (left-aligned, at least 48px tall), the story sound setting on a
  story, then the account block. Signed out, that is Chat & Contact and full-width Register / Login buttons, one per
  sign-in provider. Signed in, it is the account links.

## Page titles

`useDocumentTitle(page)` (`web_app/src/utils/useDocumentTitle.ts`) sets `document.title` to `"<page> | Open Navigator"`
and puts the default title back when the page unmounts. Home keeps the default title.

| Page | Title |
| --- | --- |
| `/` | `CommunityOne — Open Navigator \| Civic data & policy tracking` |
| `/stories` | `Data stories \| Open Navigator` (or `Data stories · Tuscaloosa, AL \| …` with a place) |
| `/stories/:id` | `<Topic> — Data story \| Open Navigator`, e.g. `Guns — Data story \| Open Navigator` |
| `/search?q=fluoride` | `Search: fluoride \| Open Navigator` |
| `/jurisdictions` | `Places \| Open Navigator` |
| `/jurisdiction/:id/meetings` | `<Jurisdiction name> — Meetings \| Open Navigator` |

The story route takes the topic's name from the story registry or the topic catalog. It does not use the story's
conclusion headline, because that is computed inside the story page.
