---
sidebar_position: 36
title: Ranking agenda items by local concern
description: How Open Navigator measures what residents object to in their own meetings and ranks data center agenda items by it (DC-4.3).
---

# Ranking agenda items by local concern

[DC-4.3](https://github.com/getcommunityone/open-navigator/issues/251) puts the agenda items that touch what an area
actually worries about ahead of routine ones. It is part of the
[Data Center Accountability epic](https://github.com/getcommunityone/open-navigator/issues/236) and builds on
[agenda items](./data-center-agenda-items.md).

## In short

- **Local concern** is what residents and members objected to in that place's own meetings: the objections
  (counter-views) recorded on each decision.
- Each objection is sorted into seven concerns by word match: water, electricity costs, noise, land and property, tax
  breaks, traffic, pollution.
- An area's **dominant concern** is its most-mentioned one, once it has at least 3 mentions.
- On "On the agenda", items that name the dominant concern near the data center mention come first (within upcoming,
  and within earlier meetings) and carry a **Matches local concern** tag.
- With too few recorded objections, the page says so and lists items by date.

<details>
<summary>Where each piece lives</summary>

| Step | Where | What it does |
|---|---|---|
| Word lists | `dbt_project/macros/local_concerns.sql` (`local_concern_patterns`) | One list, used by both models below |
| Area concerns | `area_concern` (public) | One row per area per concern: mention count, all objections, share, rank, `is_dominant`. Areas are jurisdictions, plus one national row |
| Item tags | `data_center_agenda_item.concerns` | The concerns named within about 250 characters of a data center mention |
| API | `GET /api/data-centers/concerns?state=&city=` | The area's concerns and the national ones |
| API | `GET /api/data-centers/agenda-items` | Adds `concerns`, `local_concern`, `matches_local_concern`, and ranks by them |
| Page | `/data-centers`, "On the agenda" | "What residents raise most" line, with the national figure, and the tag on matching items |

</details>

<details>
<summary>Decisions and why</summary>

- **Concern comes from meetings, not polls.** An area's own recorded objections are local and verifiable. Polls are
  national and can't say what one town worries about.
- **General local concern, not only data center objections.** Data center hearings are still rare in most places, so
  the signal is what residents object to about any project; water complaints about a subdivision tell you how a water-
  hungry data center will land there too.
- **The plan's "water ≈ 41% nationally" isn't hard-coded.** No source for that figure turned up, so the national share
  shown is computed from the same records (No Fabricated Data). Polls broadly agree water and electricity costs lead.
- **At least 3 mentions** before a concern can steer the ranking, so one stray comment doesn't reorder an area's feed.
- **Narrow word lists.** "Power" or "zoning" alone are too common to mean a concern; the lists use phrases such as
  "electric bills" and "property values".

</details>
