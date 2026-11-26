---
title: Officials' public contact details
description: How an official's public email and office status are added from their government's own page, with the source and the date checked.
---

# Officials' public contact details

Issue: [#1062](https://github.com/getcommunityone/open-navigator/issues/1062), part of the
[people and claims epic](https://github.com/getcommunityone/open-navigator/issues/1061). Added 2026-11-26.

## The rule

An official's email is added only when their government's own page publishes it, as a mailto link or written out. The
seed `official_contact_override` stores the address verbatim, the page it came from (`source_url`) and the date it was
checked (`verified_on`). An address is never built from a pattern such as first initial and last name. A page with no
address leaves the official's email null.

The same seed corrects office status when the government's page says so. It sets `is_current = false` for someone no
longer in office, with the page as the source.

`contact_official` matches a seed row on full name, state and jurisdiction, so a same-named official elsewhere in the
state isn't touched. The address and its source flow into `person_government` (`email`, `email_source_url`).

## Where it shows

The email stays in the private warehouse (`gold`) and is used to verify an official who claims their profile (#1062).
The public serving copy redacts email and phone to null, as before, so the site never lists them.

## Tuscaloosa pilot

| Official | Email | Source |
|---|---|---|
| Joseph Eatmon, Sr. (District 1) | from the district page | `tuscaloosa.com/citycouncil/district-1` |
| Raevan Howard (District 2) | from the district page | `tuscaloosa.com/citycouncil/district-2` |
| Richard Henry (District 3) | from the district page | `tuscaloosa.com/citycouncil/district-3` |
| Lee Busby (District 4) | from the district page | `tuscaloosa.com/citycouncil/district-4` |
| John Faile (District 6) | from the district page | `tuscaloosa.com/citycouncil/district-6` |
| Cassius Lanier (District 7) | from the district page | `tuscaloosa.com/citycouncil/district-7` |
| Kip Tyner (District 5) | none; marked no longer in office | the council page lists District 5 as vacant and carries "In Memory of Councilor Kip Tyner" |

Mayor Walt Maddox's email already came from the source feed. The city's council pages don't list one.

```bash
cd dbt_project
dbt seed --select official_contact_override
dbt build --select contact_official person_government
```

## Office terms and history

Issue: [#1068](https://github.com/getcommunityone/open-navigator/issues/1068). `contact_official` and
`person_government` describe who holds office now. `person_government_term` keeps who held which seat, when, and why
they left. Each row says where it came from:

| `term_source` | From | Dates |
|---|---|---|
| `seed` | `official_term`: a term stated on the government's own page, with `source_url` and `verified_on` | to the day when the page gives one (`start_date`, `end_date`), otherwise the year (`start_year`, `end_year`) |
| `openstates` | OpenStates membership dates (legislators) | `start_date`, `end_date`; an ended membership's reason is `unknown` |
| `roster_snapshot` | `officials_roster_snapshot`, a dbt snapshot of the local roster taken on each build | `first_seen_on` and `last_seen_on`: when **we saw** that version, not when the term began or ended |

`end_reason` is one of `term_ended`, `resigned`, `died`, `removed` or `unknown`. It is `died` only when an official
source says so. For example, the City of Tuscaloosa's memorial page says Councilor Kip Tyner "passed away on Friday,
September 18, 2026, while serving his second term as Tuscaloosa City Council President and his seventh as the
District 5 City Councilor". First elected in 1997, so his District 5 term reads 1997 to 2026-09-18, died.

The snapshot starts with the first build that includes it, so roster history only accumulates from then on. Earlier
terms come only from official pages (the seed) or OpenStates.

```bash
cd dbt_project
dbt seed --select official_term
dbt snapshot --select officials_roster_snapshot   # on every build, so changes are caught
dbt build --select person_government_term
```
