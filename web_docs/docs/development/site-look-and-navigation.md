---
sidebar_position: 38
title: Site look and navigation
description: Why every main tab scrolls to a section of the home page, and the one type system, teal and primary button the whole site uses (#975).
---

# Site look and navigation

[#975](https://github.com/getcommunityone/open-navigator/issues/975). The owner found the home page and the main tabs
inconsistent (25 Nov 2026). Measured in a browser, they were three different sites:

| Surface | Headings | Body | Primary button |
| --- | --- | --- | --- |
| Home | Playfair Display | Inter (its Source Sans 3 rule never matched) | teal `#0d9488` pill |
| Search | Inter | Inter | dark slate square (Tailwind `primary`) |
| Data Stories | Geist | Geist / Geist Mono | teal `#0f766e` square |

## Decision: every main tab is a home section

The header's main tabs (**Search**, **Data Stories**, **How It Works**, **Impact**) each scroll to a section of the home
page. A detail page opens only from an action inside its section.

| Tab | Home section | Detail pages it opens |
| --- | --- | --- |
| Search | `#search` (the hero search) | `/search` from a search, a trending question or a browse pill |
| Data Stories | `#data-stories` (the story card, its real counts) | `/stories/data-centers`, the challenge, `/stories` (All data stories) |
| How It Works | `#how-it-works` | the steps' own links |
| Impact | `#impact` | its links |

- **The place travels with the tab.** On a scoped page (`?state=&city=`), a tab goes to `/?state=…&city=…#section`. The
  whole home page takes that place (its scope label, the hero search, the tiles and the Data stories section) ahead of
  the saved location, without overwriting it. Picking a new place on the home page clears the carried one.
- **On the home page**, the tab for the section crossing the middle of the screen is highlighted (scroll-spy). Between
  sections none is.
- **On a detail page**, the tab it belongs to stays highlighted: `/search` → Search; `/stories*` and `/challenge*` →
  Data Stories. Clicking it goes back to its home section.
- **Arriving with a hash** (`/#data-stories`): the scroll settles again while the sections above load their data, and
  stops as soon as the reader scrolls, clicks, presses a key or navigates.
- **The home Data stories section follows the home page's place** (`?state=&city=`). Its label, its counts and its links
  all carry that place (CLAUDE.md, scope label rule).
- **Its counts are real.** They come from the same endpoints and `storyStats` as the hub, and the section says so while
  they load or when they can't.

Why: one place to start from, and the home page is that place. The tabs read as a table of contents for it, so the
reader always knows where a detail page came from.

## Decision: one type system, one teal, one primary button

- **Faces**, loaded once in `web_app/index.html`:
  - **Playfair Display** for display headings: every `h1`, every `h2` except small ones (`text-xs` / `text-sm` /
    `text-base`, where a high-contrast serif reads poorly), the story's sentence heading, screen headlines and card
    titles;
  - **Source Sans 3** for body text and controls;
  - **IBM Plex Mono** for small labels.

  They are set in `index.css` (`--font-display`, `--font-body`, `--font-label`), in Tailwind (`font-sans`,
  `font-display`, `font-mono`) and in the folio tokens the stories use (`--font-display`, `--font-sans`,
  `--font-mono`). Geist is no longer loaded.
- **Teal:** `#0f766e`, the logo's. It is Tailwind `primary-500` and `primary-600`, the home page's `TEAL`, and the
  stories' primary. `primary-500` sits under white text in the scope toggles, so it uses this darker teal (5.5:1, WCAG
  AA) rather than `#0d9488` (3.75:1). The `primary` palette was a dark slate; every app page that uses `primary-*` now
  takes the brand teal.
- **Primary action:** a bold teal pill. The home CTAs, the search button and the stories' **Start the story** and
  **Next** all use it. Folio squares every other corner on purpose; the primary action is the one exception (not the
  floating bar's answer choices, which share a row).
- **Width:** the hub lines up with the header's centred 1180px column. The story itself stays full-bleed because it is
  a scroller.

Change a face, the teal or the primary button here first, then in those three token places.
