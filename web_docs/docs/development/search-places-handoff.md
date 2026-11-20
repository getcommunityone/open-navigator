---
sidebar_position: 35
title: Search ↔ Places handoff
description: Banner and empty-state links from unified search Jurisdictions to the Places browser — never an automatic redirect. Jurisdiction hit URL fix is a separate bug.
---

# Search ↔ Places handoff

The Places page (`/jurisdictions`) is the right browser for cities, counties,
states, and school boards. Unified search (`/search`) already has a
**Jurisdictions** result type and tab, but people do not reliably find Places
from search.

This design adds **user-chosen** links from search into Places. There is no
automatic redirect.

Issue: [#646](https://github.com/getcommunityone/open-navigator/issues/646).

## In short

- **Banner** when the Jurisdictions tab is selected, or when Advanced →
  Jurisdictions is checked: **“Browse all places →”** links to `/jurisdictions`,
  carrying `q`, `state`, and `jurisdiction_levels` when set.
- **Empty state** when the Jurisdictions leg has **0 hits** and `q` is
  **non-empty**: name the query in the message and link to Places with the same
  `q`, `state`, and levels. Keep any “place-like” heuristic simple; the wording
  must still make sense if the guess is wrong (invite to browse Places — do not
  claim “we detected a city”).
- **Always a link the person chooses** — never navigate away from `/search`
  without a click.
- **Do not** add a separate “Places” entry to the result-type filter list. That
  list only filters search legs. The handoff is banner / empty-state CTA only.

## Where each piece lives

| Piece | Where | What it does |
|---|---|---|
| Places browser | `web_app/src/pages/JurisdictionsSearch.tsx` | Level pills, map, chips; unchanged as the place browser |
| Unified search | `web_app/src/pages/UnifiedSearch.tsx` | Banner + empty-state CTA |
| Link helper | e.g. `web_app/src/lib/placesBrowseUrl.ts` | Build `/jurisdictions?q=&state=&jurisdiction_levels=` |

## Contract

### `placesBrowseUrl`

Inputs: `q?: string`, `state?: string`, `jurisdiction_levels?: string` (comma list,
same vocabulary as the API: `city`, `county`, `state`, `school_district`, …).

Output: path `/jurisdictions` plus only the params that are non-empty. Does not
invent a city or level. Scope on Places must match these params (site-wide
scope-label rule).

### Banner

Show when either:

1. The active results tab is **Jurisdictions**, or  
2. Advanced filters have **Jurisdictions** checked (even if another tab is
   active — keep the banner discoverable while that type is in the filter set).

Copy: **Browse all places →**. Target: `placesBrowseUrl(...)`.

### Empty state

Show on the Jurisdictions tab (or jurisdictions section) when:

- `type_totals.jurisdictions === 0` (or the jurisdictions result list is empty
  after a completed search), and  
- `q` is non-empty (trimmed).

Message **names the query**, e.g. `No places matched “{q}” in search. Browse
Places for “{q}” →`, linking with the same carried params.

### Explicit non-goals (this issue)

- Multi-select place checkboxes that OR-filter meetings/decisions.
- Adding “Places” as a result-type checkbox.
- Auto-redirect from `/search` to `/jurisdictions` or a place detail page.
- Embedding the Places map inside unified search.
- **Changing jurisdiction search hit URLs** — that is a separate bug (below).

## Scope labels

Whatever `state` / levels Places receives from the handoff must appear in the
Places scope UI the same way a user who typed those filters would see them
(`CLAUDE.md` — scope label matches the active filter).

---

## Related bug (not this issue): jurisdiction hit URLs

Tracked separately: [#647](https://github.com/getcommunityone/open-navigator/issues/647).

| | |
|---|---|
| **Current URL** (from `search_jurisdictions_pg`) | `/jurisdictions/{geoid}` (or `/jurisdictions/{name}` if geoid missing) |
| **SPA routes today** | `/jurisdictions` → Places browser only; `/jurisdiction/:jurisdictionId/meetings` → place meetings (Places chips / map) |
| **Redirect from old URL?** | **No.** `App.tsx` has no `/jurisdictions/:geoid` route and no `Navigate` alias to `/jurisdiction/…/meetings`. |
| **Target URL** | `/jurisdiction/{geoid}/meetings` |
| **Tests covering current URL** | **None found** (no pytest/frontend assertion on this `url` string). |

Do not fold #647 into #646 implementation unless both are explicitly scoped in one PR later; keep the handoff shippable without waiting on the URL fix, and vice versa.
EOF
