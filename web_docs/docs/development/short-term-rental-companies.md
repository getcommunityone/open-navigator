---
title: Short-term rental platform companies
description: How Airbnb, Expedia Group (Vrbo) and Booking Holdings are tracked as organizations and linked to the meetings and decisions that name them.
---

# Short-term rental platform companies

Issue: [#1015](https://github.com/getcommunityone/open-navigator/issues/1015). Added 2026-11-25. Part of the
[short-term rentals story](./topic-stories.md).

## What is tracked

| Company | Brands matched | Match terms | Source (company's own page) |
|---|---|---|---|
| Airbnb | Airbnb | `airbnb` | news.airbnb.com/about-us |
| Expedia Group | Vrbo, HomeAway | `vrbo`, `homeaway` | expediagroup.com/en-us/about-us ("We brought HomeAway and Vrbo into the fold…") |
| Booking Holdings | Booking.com | `booking.com` | bookingholdings.com/brands/booking ("Part of Booking Holdings Inc.…") |

The list is the seed `short_term_rental_companies`. Every row has its website, source URL and a verbatim excerpt.
Add a company only when its own page says what it is.

## How they become organizations

They take the same MDM path as the data center companies:
`stg_short_term_rental_companies__org` → `int_organizations__unioned` → `int_organizations__clustered` →
`mdm_organization`. Each one lands as a national `company` (org_subtype `short_term_rental`).

The satellite `mdm_organization_short_term_rental` has one row per `master_org_id` (PK and FK to `mdm_organization`)
and holds the aliases, match terms, website and source.

**Airbnb.org is not Airbnb.** The organization master already holds "Airbnb Org Inc", the Airbnb.org charity. Its name
normalizes to `airbnb org`, not `airbnb`, so it stays its own organization and is never linked as the company.

## Where they are named

`short_term_rental_company_mention` has one row per (company, meeting video) whose transcript names the company,
and one row per (company, decision) whose record names it (`mention_kind`). Matching uses English full-text on the
match terms, the same `to_tsvector` as transcript and decision search. `evidence` is a verbatim `ts_headline` with
the terms in `<mark>`.

Keys:

- PK `mention_id`.
- FK `master_org_id` → the satellite.
- `event_decision_id` → `event_decision`, asserted by a relationships test because `event_decision` is partitioned.

A brand-name match is a mention, not a claim about the company's role. "Airbnb" in a transcript often means a rental
listed there.

## Where it shows

- `GET /api/short-term-rentals/companies?state=` returns each company's meeting and decision counts and its newest
  mention.
- The short-term rentals story has a **Companies named** row with those counts, a link to search for the brand, and
  the newest quote.

Both tables are on the public serving list and the prod copy's allow-list.
