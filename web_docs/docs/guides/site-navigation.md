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

`📍 Tuscaloosa, AL ▾` in the header on desktop, and at the top of the phone menu. It reads **Find your town** when no
place is set. Nothing is hard-coded: the label is the place in the address (`?state=&city=`) when there is one, else the
reader's saved location (`LocationContext`), else nothing.

It opens `LocationPickerDialog` (`web_app/src/components/LocationPickerDialog.tsx`), the same dialog as the home page's
**Find your town** button. The dialog wraps the real geocoder (`AddressLookup` → `/api/geocode/search`). It closes on
Escape, the ✕ or a tap outside, and gives focus back to the control that opened it.

A pick goes through `usePlacePick()` (`web_app/src/hooks/usePlacePick.ts`):

1. It saves the place (`LocationContext`, so later visits keep it).
2. On the home page it clears any carried `?state=&city=`: home's scope is the saved place. On every other page it writes
   the pick into `?state=&city=` (and drops `page`), so the page's scope label, query and results change together.
3. It fires `open-navigator:place-picked`. `Layout` remounts the routed page on it, because most pages read their scope
   from the address once, on mount. The home page resets its City / State / National level to the new place's.

## Phone menu

Below 960px the links fold into a menu behind the ☰ button.

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
