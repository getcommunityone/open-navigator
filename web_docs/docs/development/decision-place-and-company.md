---
sidebar_position: 32
title: Decision place and company rules
description: When the question dashboard names a decision's address, a company, or a nearby tracked data center site, and when it stays silent.
---

# Decision place and company rules

Decided November 17, 2026, for [#508](https://github.com/getcommunityone/open-navigator/issues/508), the readable
"View dashboard" modal on Browse Questions.

Each decision row on the dashboard can say **where** (an address), **who** (a company) and which tracked data center
sites are **nearby**. All three are built in dbt, with no LLM, and a row shows nothing rather than a guess
(CLAUDE.md, "No Fabricated Data").

## Where: `decision_place_label`

The place comes from the decision's own reference graph: its `primary_place_id`, resolved in `event_place_geocoded`
within the same analysis. A decision with no primary place uses a non-primary reference only when that's its single
street-level reference. That way an address read out in public comment is never shown as the subject.

A place is shown only when all four checks pass:

1. **It is street-level.** A `street_address` must start with a house number and name a road. An `intersection` or
   `corridor` must name a road (`named_road_regex`: Road, Avenue, Parkway, Highway, I-70 and the like). Jurisdiction-wide
   places, facilities and vague text like "industrial corridor" never pass. This check keeps speech-to-text county
   names such as "Dicab County" (DeKalb), "Brooks County" and "Sum County" off the page.
2. **Its state agrees** with the state of the decision's own government. That government is the `jurisdiction_id` on
   the meeting's `civic_event` (`int_event_decision__jurisdiction`), not a name match.
3. **Its city doesn't contradict that government.** The city is empty, is that government, or (for a county) is a
   place inside it according to `jurisdiction_county_crosswalk`.
4. **Its address positively agrees** (`agreement_basis`):
   - `place_city`: the address's city is the government.
   - `city_in_county`: the city lies inside the county.
   - `address_names_jurisdiction`: one comma-separated part of the address is the government's name.

The warehouse holds no jurisdiction boundary polygons, so there's no "geocode inside the boundary" test. The check
reads the address text alone.

## Who: `decision_company_mention`

A company is named only when a data center decision's own `headline` or `decision_statement` says it. Two lists are
matched:

- **The seed `data_center_operators.csv`** holds real operators and developers with their aliases. A brand that is
  also an ordinary word (Switch, Stack, Compass, Aligned, Vantage, Meta, Oracle, Tract) is listed only in a company form.
  Examples are "Switch, Inc.", "Stack Infrastructure", "Compass Datacenters", "Meta Platforms", "Meta's" and "Oracle
  Cloud". The bare word is never listed.
- **The Epoch AI names on `data_center_site`** are the `owner`, `users` and `project` values. The "(likely)" and
  "(speculative)" tags are removed and lists are split on commas.
  - A project name such as "Hyperion" counts only in its site's state, and it is credited to that site's owner.
  - An Epoch name that is a seed operator or one of its aliases is skipped, so the seed's company-form rule governs it.
    Epoch's bare "Meta" therefore never matches.
  - Names shorter than four characters are skipped.

Matching is **case-sensitive, on a whole word or phrase** (`phrase_regex`). A non-alphanumeric character or the edge
of the text must sit on both sides. So lower-case "switch" or "stack" never match, and "AWS" doesn't match inside
"LAWS". Each row keeps `matched_text`, the exact words matched, and `evidence`, a verbatim excerpt with the match in
`<mark>`. The dashboard shows both. To add a company, add a row to the seed, using only real company names.

## Nearby: `decision_nearby_data_center_site`

This table holds the Epoch AI sites whose governments (`int_data_center_site__jurisdiction`, #445) include the
decision's own government. The dashboard labels each one `Nearby tracked site: <site> (<owner>)`. It means the site
is near that government, and **not** that the decision is about it.

## Tested

The dbt unit tests in `_schema_decision_context.yml` check both rules:

- **Companies:** company forms match, while ordinary words, "LAWS" and an out-of-state project don't.
- **Places:** "Dicab County", a state-contradicting corridor and an Atlanta address on a Spalding decision get no label.
  A Spalding road and a Griffin address do.
