---
sidebar_position: 35
title: Data center items on agendas
description: How Open Navigator finds data center items on meeting agendas so residents hear about them before the vote (DC-4.2).
---

# Data center items on agendas

[DC-4.2](https://github.com/getcommunityone/open-navigator/issues/250) surfaces data center items on meeting agendas,
upcoming meetings first, so residents can attend the meeting where a site is decided. It is part of the
[Data Center Accountability epic](https://github.com/getcommunityone/open-navigator/issues/236).

## In short

- Agendas are posted before the meeting, so an agenda with a future date is an item residents can still act on.
- An agenda is kept when its text mentions a data center ("data center", "data centre", "hyperscale", "server farm").
- Each item quotes the agenda with the matched words highlighted, and is tagged **Zoning or utility item** when a
  zoning, land-use, tax-incentive or utility word appears within about 250 characters of the mention.
- When the agenda names a [tracked site](./data-center-sites.md) in the same state, the item links to it.
- Coverage follows the agendas whose text we've extracted (today mostly Tuscaloosa, from SuiteOne). More cities come
  with the meeting adapters ([CORE-3.2](https://github.com/getcommunityone/open-navigator/issues/243)).

<details>
<summary>Where each piece lives</summary>

| Step | Where | What it does |
|---|---|---|
| Mart | `data_center_agenda_item` (public) | One row per agenda that mentions a data center. PK `data_center_agenda_item_id`; FKs to `event_meeting_document`, `jurisdictions`, `data_center_site`. `evidence` is a `ts_headline` excerpt with `<mark>` around the matched words |
| API | `GET /api/data-centers/agenda-items?state=&city=&when=upcoming\|past\|all` | Upcoming first (soonest first), then past (newest first). `is_upcoming` is worked out from today, so a table built last week can't call a past meeting upcoming |
| Page | `/data-centers?state=&city=`, "On the agenda" | "Coming up" and "Earlier meetings", each with the meeting, date, quote, tags and agenda link |

</details>

<details>
<summary>Decisions and why</summary>

- **Word match, not AI.** A plain text match is cheap, runs in dbt on every build, and its evidence is the agenda's own
  words. A false positive (a staff report that only mentions data centers) is visible as such from the quote, and the
  zoning-or-utility tag is what marks the items that are likely decisions.
- **The 250-character window** is a PostgreSQL limit (a regex repeat count can't exceed 255). It is close enough to
  "the same agenda item" for typical agendas.
- **No quote, no item.** A document whose text doesn't produce a highlighted excerpt is left out, per the site-wide
  match-evidence rule.
- **Site links need the site's name in the same state**, and names shorter than 6 characters are skipped, so a
  common word can't create a link.

</details>
