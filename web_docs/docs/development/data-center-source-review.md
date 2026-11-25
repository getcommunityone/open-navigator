---
sidebar_position: 37
title: Data center source review
description: Which data center hearing trackers and facility inventories we may use, and how, from their own terms, licenses and robots.txt as checked on 25 Nov 2026.
---

# Data center source review

[#956](https://github.com/getcommunityone/open-navigator/issues/956) (hearing trackers) and
[#958](https://github.com/getcommunityone/open-navigator/issues/958) (facility inventories). The owner's research turned up
national trackers of data center hearings and inventories of facilities. Before any of them goes into the pipeline, this
page records what each one allows, from its own pages. All were checked on **25 Nov 2026**.

Everything was read politely: each robots.txt was fetched directly, pages were read one at a time, and nothing was
logged into, paid for or worked around. Where a site blocked automated reading, that is recorded instead of the content.
The citations, with BibTeX, are in [Data and citations](../data-sources/citations.md#data-center-hearing-trackers-and-facility-inventories).

## The rules we apply

- **Lead source (CC BY 4.0):** a tracker's records may tell us where to look. A hearing is shown only after the
  government's own page confirms it ([Upcoming data center hearings](./data-center-hearings.md)). We credit the tracker
  and don't republish its text.
- **Importable:** the data's license allows reuse, there is a free download, and we keep the attribution it asks for.
- **Ask first:** readable, but no reuse license is granted (or none is stated). Nothing is imported until the publisher
  agrees.
- **Reference only:** named and linked. Sites whose terms forbid scraping, bulk copying or competing use go on
  `BLOCKED_HOSTS` (`packages/ingestion/src/ingestion/data_centers/community_events.py`), so they are never fetched, and
  news items linking there are dropped.

## Hearing trackers

| Tracker | Operator | Terms / license (their words) | robots.txt (`*`) | Verdict |
| --- | --- | --- | --- | --- |
| [Data Center Fights](https://datacenterfights.com/) | "the Data Center Fights team" (no entity named; ad-supported) | "our compiled data and original text may be reused under the Creative Commons Attribution 4.0 license" (terms, Nov 22, 2026) | `Allow: /` | **Lead source.** `/data.json`: 176 meetings, each with a `source` URL and a `source_type` (researched / unconfirmed / user-added) |
| [Siting Radar](https://sitingradar.com/pending?sector=data_center) | not named (commercial; trial and paid plans) | "The CSV is published under CC BY 4.0 … credit Siting Radar and link to this page." Terms are a draft: "Do not resell raw alert data, overload the API" | allows `/`; disallows `/api/`, `/app`, `/auth/`, `/billing/`, `/u/` | **Lead source**, via `/data/siting-radar-upcoming.csv` (`source_url`, `census_geoid`) and `/feed.xml` only. OH, MI, NY, NC, GA, IN and VA |
| [PA Data Center Ordinance Tracker](https://padatacenterordinances.org/coming-up) | David Olson (individual, Adams County PA) | CC BY 4.0, "for any purpose, including … commercial products"; not allowed: "Copying the site with automated tools in a way that slows or burdens it" | allows `/`; disallows query-string variants of tool pages | **Lead source**, via the For Reporters CSV downloads, not crawling |
| [NC GovWatch](https://ncgovwatch.com/) | not stated | no terms page; the API page says "No key, no account" and asks for an identifying User-Agent; summaries "are produced by a language model" | disallows `/api/`, `/export.csv`, `/compare` | **Ask first.** The open API conflicts with robots.txt, and there is no license |
| [Data Centers Atlas](https://datacentersatlas.com/hearings/) | Shaun Wilson Designs (Louisville) | "No new reuse license is granted here." | `Allow: /` | **Ask first** |
| [GridWatch USA, The Docket](https://gridwatchtheusa.com/docket/) | GridWatch the USA (advocacy publisher, Georgia) | "You may quote brief excerpts with credit … Any other reproduction requires our permission." Offers free extracts on request | disallows `/evidence/` and shop paths | **Ask first** (extracts on request) |
| [GovMeet](https://govmeet.us/) | Patton Gaming Ltd (UK company 17572870) | "You may not: copy the service or its data wholesale by automated means; resell or redistribute our data, alerts or pages without our written agreement" | disallows `/api/`, `/csv`, `/rss`, `/search?` and others | **Reference only**; added to `BLOCKED_HOSTS` |

## Facility inventories

| Inventory | Publisher | Terms / license (their words) | Access | Verdict |
| --- | --- | --- | --- | --- |
| [Public Evidence Project](https://publicevidence.org) | independent civic research initiative | "Open data · CC BY 4.0"; keep permit ids and official document URLs; credit it and Compute Atlas upstream | free CSV, GeoJSON and JSON at `/data/national-data-center-public-records.*` (robots.txt disallows `/api/`) | **Importable.** Every record has a government `source_url` |
| [US Data Center Registry](https://suedatacenters.org/data-centers/data) | Theory Road LLC (SueDataCenters.org) | "The data is CC BY 4.0"; credit Compute Atlas for the base and SueDataCenters.org for joins, corrections and additions | free `/data-centers.csv` and `.json` (v1.35.1, Nov 5, 2026) | **Importable.** No primary source URL per record (only `source_count`), so rows are registry records, not verified facts |
| [Compute Atlas](https://www.compute-atlas.com) | Compute Atlas LLC (Edward Kubiak) | "free to use, including commercially, under a CC BY 4.0 license, with attribution"; don't imply endorsement | facility pages free; the bulk CSV/JSON is paid ("not a licence fee"); Zenodo files restricted | **Licensed CC BY, but the bulk file is paid.** Used through the two derivatives above |
| [US Data Centers by State](https://github.com/greencalculus/us-data-centers-by-state) | greencalculus (GitHub) | LICENSE: CC BY 4.0; cite `CITATION.cff` and each figure's original publisher | free `us-data-centers.csv` / `.json` | **Importable as state aggregates**, each figure credited to its original publisher |
| [DCMap.us](https://dcmap.us) | Rahil Banthia (personal project) | quote statistics with attribution; no bulk copying or scraping; no "standalone database or competing directory"; "Just don't copy the whole dataset" | free aggregate Agent API only; robots.txt disallows `/api/` and `/data/` | **Reference only**; `BLOCKED_HOSTS` |
| [Cleanview](https://cleanview.co/data-centers) | commercial | license for "internal business purposes"; may not "redistribute the Licensed Content" or "build … a product or dataset that competes with Cleanview" | samples and a paid, keyed API | **Reference only**; `BLOCKED_HOSTS` |
| [Pew Research Center](https://www.pewresearch.org/chart/top-states-data-centers/) | nonprofit | third-party content may not be republished "as a stand-alone file"; no "spidering, 'scraping,' or harvesting"; the chart's source is Data Center Map | chart and CSV button (top 15 states) | **Reference only**: cite Pew and Data Center Map |
| [Data Center Record](https://datacenterrecord.org) | Colton Digital Consulting LLC | rows CC BY-NC 4.0; "Commercial, enterprise, financial or AI training use needs a commercial data license" | bulk files only with that license | **Reference only / ask** |
| [Geolocity](https://geolocity.com/data-centers) | Blind Spot Intelligence LLC | §10: no copying "in bulk", no republishing "as a dataset", no scraping "to extract it in bulk" | pages only | **Reference only**; `BLOCKED_HOSTS`. Follow its links to the agency records instead |
| [ZoningLabs](https://zoninglabs.com/data-centers) | commercial | may not "Scrape or harvest data … Copy, reproduce, or distribute content without permission … Use our content for commercial purposes without license" | static GeoJSON reachable, but the terms govern | **Reference only**; `BLOCKED_HOSTS` |
| [Data Center Map](https://www.datacentermap.com) | commercial (Denmark) | from a search snippet only (the site returned HTTP 429 to us): data "may only be used internally … and may never be redistributed" | paid datasets | **Reference only**; `BLOCKED_HOSTS` |
| [ITAMG](https://www.itamg.com/data-center-locations/) | commercial | not read: the site returned a bot check (HTTP 403) | unknown | **Ask first** |

## What happens next

- **Lead feeds (#956), done:** Data Center Fights and Siting Radar feed leads into `data_center_hearing` through
  `python -m ingestion.data_centers.load_hearing_tracker_leads` (one request per file), each credited in `source_name`.
  Their own text (topics, summaries) is not shown, and Data Center Fights' user-added records are not used.
  Only the government page a record cites can verify a hearing; see
  [Upcoming data center hearings](./data-center-hearings.md#tracker-leads-25-nov-2026). The PA tracker's CSV downloads
  list ordinances, not meetings, and its meeting list is a web page its terms ask us not to crawl, so it feeds no
  leads. Its ordinance data could feed an ordinance view later.
- **Imports (#958), planned:** Public Evidence Project and the US Data Center Registry are to be imported (bronze, then
  staging), with their attribution, and linked to existing `data_center_site` rows only where name and place agree, never
  merged on a guess. The greencalculus repo would land as state aggregates.
- **Ask first:** NC GovWatch, Data Centers Atlas, GridWatch and ITAMG get a permission request from the owner before
  any use. Record the answer here.
- **Re-check** a source's terms before changing how we use it. Terms change, and these were read on 25 Nov 2026.
