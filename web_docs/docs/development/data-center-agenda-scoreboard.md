---
sidebar_position: 37
title: Data center agenda coverage scoreboard
description: Site-belt and mention-jurisdiction agenda coverage by platform (#632). Regenerated from the warehouse.
---

# Data center agenda coverage scoreboard

Generated **2026-11-20T03:00:33Z** (UTC) for [#632](https://github.com/getcommunityone/open-navigator/issues/632). Design: [data-center-agenda-first-design](./data-center-agenda-first-design.md).

Numbers are warehouse counts only. **No network fetch** in this report; **robots.txt and bot blocks are not bypassed.**

## Snapshot

| Metric | Count |
|---|---:|
| Site-linked jurisdictions | 97 |
| Mention jurisdictions (`data_center_meeting_mention`) | 564 |
| Mention jurisdictions also in #460 survey | 12 |
| Mention jurisdictions **unsurveyed** | 552 |
| DC videos in unsurveyed mention jids | 1775 |
| Agenda docs in site-belt jids | 230 |
| `data_center_agenda_item` rows (national) | 84 |
| Agenda docs with `doc_date` ≥ today (national) | 31 |

Upcoming agendas **do** become rows when ingested (same as past agendas).

## Site-belt classification

| Classification | Governments |
|---|---:|
| `has_agenda` | 2 |
| `blocked` | 29 |
| `unreachable` | 6 |
| `reader_needed` | 18 |
| `no_document_platform` | 42 |

## Per platform

### Site belt

| Platform | Site-belt governments | DC videos in those governments | Media | We read docs today |
|---|---:|---:|---|---|
| `youtube` | 50 | 23 | video | yes |
| `none` | 32 | 28 | — | n/a (video) |
| `granicus` | 9 | 5 | both | no (robots_disallowed on pages) |
| `civicplus_agenda_center` | 8 | 0 | documents | no |
| `civicclerk` | 7 | 0 | documents | no |
| `legistar` | 4 | 6 | documents | yes |
| `civicweb` | 3 | 6 | documents | no |
| `swagit` | 3 | 0 | video | n/a (video) |
| `escribe` | 2 | 0 | documents | no |
| `vimeo` | 2 | 0 | video | n/a (video) |
| `cablecast` | 1 | 0 | video | n/a (video) |
| `facebook_video` | 1 | 0 | video | n/a (video) |
| `primegov` | 1 | 0 | documents | no |
| `suiteone` | 1 | 0 | both | yes |

### Mention jurisdictions (survey overlap only for platform)

Only **12** of **564** mention jurisdictions appear in `bronze_jurisdiction_meeting_source`. The other **552** (about **1775** DC videos) have **no surveyed platform** yet — Stage 2 (#637).

| Platform | Mention jurisdictions (surveyed) | DC videos in those jurisdictions |
|---|---:|---:|
| `youtube` | 7 | 23 |
| `none` | 4 | 28 |
| `legistar` | 2 | 6 |
| `civicweb` | 1 | 6 |
| `granicus` | 1 | 5 |
| *(unsurveyed)* | 552 | 1775 |

Reader priority for the site belt should follow document platforms we do not read yet, weighted by governments **and** DC videos in the tables above.

## Blocked / robots

### Website `blocked` (site belt)

`bronze.bronze_jurisdiction_meeting_source` stores `website_status` but **not** the HTTP status code or reason string. The #460 write-up recorded **28× HTTP 403** and **1× HTTP 429** (Bexar County TX) among blocked governments. Per-government codes were not loaded into bronze — follow-up [#638](https://github.com/getcommunityone/open-navigator/issues/638). **Do not route around these blocks.**

| Government | State | `jurisdiction_id` | Platforms found | Notes |
|---|---|---|---|---|
| Montgomery | AL | `montgomery_0151000` | youtube | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Montgomery County | AL | `montgomery_01101` | youtube | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Goodyear | AZ | `goodyear_0428380` | legistar | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429); survey found readable docs=['legistar'] (vendor/YouTube path) |
| Atlanta | GA | `atlanta_1304000` | granicus, legistar | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429); survey found readable docs=['legistar'] (vendor/YouTube path); portal granicus/atlantaga.granicus.com: robots_disallowed |
| Fayetteville | GA | `fayetteville_1328968` | youtube | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Council Bluffs | IA | `council_bluffs_1916860` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Linn County | IA | `linn_19113` | youtube | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Pottawattamie County | IA | `pottawattamie_19155` | youtube | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Allen County | IN | `allen_18003` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Fort Wayne | IN | `fort_wayne_1825000` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Douglas County | NE | `douglas_31055` | youtube | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Lancaster County | NE | `lancaster_31109` | youtube | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Lincoln | NE | `lincoln_3128000` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Omaha | NE | `omaha_3137000` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Columbus | OH | `columbus_3918000` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Franklin County | OH | `franklin_39049` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| New Albany | OH | `new_albany_3953970` | youtube | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Hillsboro | OR | `hillsboro_4134100` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Trenton | SC | `trenton_4572520` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Memphis | TN | `memphis_4748000` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Shelby County | TN | `shelby_47157` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Bexar County | TX | `bexar_48029` | youtube | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Denton | TX | `denton_4819972` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| San Antonio | TX | `san_antonio_4865000` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Eagle Mountain | UT | `eagle_mountain_4920810` | youtube | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Henrico County | VA | `henrico_51087` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Racine County | WI | `racine_55101` | none | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Cheyenne | WY | `cheyenne_5613900` | youtube | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429) |
| Laramie County | WY | `laramie_56021` | granicus | website_status=blocked; HTTP status not stored in bronze (survey: mostly 403, one 429); portal granicus/laramiecounty.granicus.com: robots_disallowed |

### Platform portals `robots_disallowed`

| `jurisdiction_id` | Platform | Portal | Detail |
|---|---|---|---|
| `atlanta_1304000` | `granicus` | `atlantaga.granicus.com` | robots.txt disallows ViewPublisher.php for all crawlers |
| `dakota_27037` | `granicus` | `dakota.granicus.com` | robots.txt disallows ViewPublisher.php for all crawlers |
| `denton_48121` | `granicus` | `dentoncounty.granicus.com` | robots.txt disallows ViewPublisher.php for all crawlers |
| `laramie_56021` | `granicus` | `laramiecounty.granicus.com` | robots.txt disallows ViewPublisher.php for all crawlers |
| `loudoun_51107` | `granicus` | `loudoun.granicus.com` | robots.txt disallows ViewPublisher.php for all crawlers |
| `manassas_5148952` | `granicus` | `manassascity.granicus.com` | robots.txt disallows ViewPublisher.php for all crawlers |
| `prince_william_51153` | `granicus` | `pwcgov.granicus.com` | robots.txt disallows ViewPublisher.php for all crawlers |
| `washington_41067` | `granicus` | `washco.granicus.com` | robots.txt disallows ViewPublisher.php for all crawlers |

## Per government (site belt)

`meetings_known` = YouTube rows with `event_date` in that jurisdiction’s YouTube min–max date range. `meetings_with_agenda` = those with a same-day agenda in `event_meeting_document`. DC videos = distinct `data_center_meeting_mention.video_id`.

| Government | ST | Class | Website | Platforms | Agenda docs | Meetings w/ agenda | Meetings known | YT date range | DC videos |
|---|---|---|---|---|---:|---:|---:|---|---:|
| Montgomery | AL | `blocked` | blocked | youtube | 0 | 0 | 348 | 2013-09-24 … 2026-11-17 | 1 |
| Montgomery County | AL | `blocked` | blocked | youtube | 0 | 0 | 166 | 2025-02-11 … 2026-11-10 | 0 |
| Goodyear | AZ | `blocked` | blocked | legistar | 0 | 0 | 0 | — | 0 |
| Maricopa County | AZ | `reader_needed` | ok | civicplus_agenda_center, youtube | 0 | 0 | 39 | 2026-09-01 … 2026-12-11 | 0 |
| Atlanta | GA | `blocked` | blocked | granicus, legistar | 0 | 0 | 187 | 2025-01-09 … 2026-08-31 | 5 |
| Fayette County | GA | `no_document_platform` | ok | youtube | 0 | 0 | 55 | 2025-01-28 … 2026-06-25 | 9 |
| Fayetteville | GA | `blocked` | blocked | youtube | 0 | 0 | 23 | 2026-06-30 … 2026-12-15 | 0 |
| Fulton County | GA | `has_agenda` | ok | legistar, youtube | 53 | 12 | 90 | 2026-03-23 … 2026-11-17 | 1 |
| Cedar Rapids | IA | `no_document_platform` | ok | youtube | 0 | 0 | 80 | 2020-04-08 … 2026-05-02 | 0 |
| Council Bluffs | IA | `blocked` | blocked | none | 0 | 0 | 0 | — | 0 |
| Cumming | IA | `no_document_platform` | ok | none | 0 | 0 | 0 | — | 0 |
| Fairfax | IA | `reader_needed` | ok | civicweb, youtube | 0 | 0 | 91 | 2023-06-06 … 2026-11-10 | 6 |
| Linn County | IA | `blocked` | blocked | youtube | 0 | 0 | 37 | 2021-06-14 … 2026-10-06 | 0 |
| Pottawattamie County | IA | `blocked` | blocked | youtube | 0 | 0 | 50 | 2025-12-16 … 2026-11-10 | 0 |
| Warren County | IA | `no_document_platform` | ok | youtube | 0 | 0 | 50 | 2024-11-19 … 2026-12-01 | 0 |
| Allen County | IN | `blocked` | blocked | none | 0 | 0 | 0 | — | 0 |
| Clark County | IN | `unreachable` | unreachable | escribe | 0 | 0 | 0 | — | 0 |
| Fort Wayne | IN | `blocked` | blocked | none | 0 | 0 | 0 | — | 0 |
| Jeffersonville | IN | `no_document_platform` | ok | vimeo, youtube | 0 | 0 | 155 | 2014-09-29 … 2026-11-16 | 0 |
| New Carlisle | IN | `no_document_platform` | missing | none | 0 | 0 | 0 | — | 0 |
| St. Joseph County | IN | `unreachable` | unreachable | none | 0 | 0 | 0 | — | 0 |
| Richland Parish | LA | `no_document_platform` | missing | none | 0 | 0 | 0 | — | 0 |
| Dakota County | MN | `has_agenda` | ok | granicus, legistar, youtube | 177 | 9 | 29 | 2024-08-22 … 2026-11-05 | 0 |
| Rosemount | MN | `reader_needed` | ok | civicclerk, youtube | 0 | 0 | 39 | 2026-03-17 … 2026-11-17 | 0 |
| Madison County | MS | `no_document_platform` | ok | youtube | 0 | 0 | 47 | 2026-04-27 … 2027-01-04 | 0 |
| Ridgeland | MS | `reader_needed` | ok | civicclerk, youtube | 0 | 0 | 34 | 2013-07-05 … 2017-04-26 | 0 |
| Cherokee County | NC | `reader_needed` | ok | civicplus_agenda_center | 0 | 0 | 0 | — | 0 |
| Marble | NC | `no_document_platform` | missing | — | 0 | 0 | 0 | — | 0 |
| Dickey County | ND | `no_document_platform` | ok | none | 0 | 0 | 0 | — | 0 |
| Ellendale | ND | `unreachable` | unreachable | none | 0 | 0 | 0 | — | 0 |
| Douglas County | NE | `blocked` | blocked | youtube | 0 | 0 | 4 | 2024-05-13 … 2025-09-22 | 0 |
| Lancaster County | NE | `blocked` | blocked | youtube | 0 | 0 | 49 | 2026-05-06 … 2026-11-10 | 0 |
| Lincoln | NE | `blocked` | blocked | none | 0 | 0 | 62 | 2025-03-03 … 2026-06-01 | 0 |
| Omaha | NE | `blocked` | blocked | none | 0 | 0 | 433 | 2011-02-08 … 2026-10-20 | 5 |
| Sarpy County | NE | `reader_needed` | ok | civicweb, youtube | 0 | 0 | 34 | 2021-07-26 … 2026-08-27 | 0 |
| Springfield | NE | `no_document_platform` | ok | youtube | 0 | 0 | 0 | — | 0 |
| Cumberland County | NJ | `no_document_platform` | ok | youtube | 0 | 0 | 0 | — | 0 |
| Vineland | NJ | `reader_needed` | ok | civicclerk, youtube | 0 | 0 | 46 | 2025-11-20 … 2026-12-22 | 0 |
| Los Lunas | NM | `reader_needed` | ok | civicplus_agenda_center, youtube | 0 | 0 | 0 | — | 0 |
| Valencia County | NM | `no_document_platform` | ok | none | 0 | 0 | 0 | — | 0 |
| Barker | NY | `no_document_platform` | ok | none | 0 | 0 | 0 | — | 0 |
| Niagara County | NY | `no_document_platform` | ok | cablecast, youtube | 0 | 0 | 36 | 2022-03-02 … 2026-11-12 | 0 |
| Bowling Green | OH | `no_document_platform` | ok | youtube | 0 | 0 | 184 | 2011-11-29 … 2026-11-16 | 2 |
| Columbus | OH | `blocked` | blocked | none | 0 | 0 | 431 | 2012-09-12 … 2026-10-14 | 13 |
| Fairfield County | OH | `no_document_platform` | ok | youtube | 0 | 0 | 48 | 2024-11-15 … 2026-10-16 | 0 |
| Franklin County | OH | `blocked` | blocked | none | 0 | 0 | 0 | — | 0 |
| Lancaster | OH | `reader_needed` | ok | civicplus_agenda_center, youtube | 0 | 0 | 6 | 2026-04-01 … 2026-07-06 | 0 |
| New Albany | OH | `blocked` | blocked | youtube | 0 | 0 | 0 | — | 0 |
| Trumbull County | OH | `no_document_platform` | ok | youtube | 0 | 0 | 58 | 2020-07-27 … 2026-11-12 | 0 |
| Warren | OH | `no_document_platform` | ok | youtube | 0 | 0 | 0 | — | 0 |
| Wood County | OH | `no_document_platform` | ok | none | 0 | 0 | 0 | — | 0 |
| Mayes County | OK | `no_document_platform` | ok | none | 0 | 0 | 0 | — | 0 |
| Muskogee | OK | `no_document_platform` | ok | youtube | 0 | 0 | 49 | 2026-02-10 … 2026-11-16 | 0 |
| Muskogee County | OK | `no_document_platform` | ok | youtube | 0 | 0 | 0 | — | 0 |
| Hillsboro | OR | `blocked` | blocked | none | 0 | 0 | 198 | 2013-06-03 … 2026-10-27 | 4 |
| The Dalles | OR | `no_document_platform` | ok | youtube | 0 | 0 | 30 | 2026-04-30 … 2026-11-10 | 0 |
| Wasco County | OR | `no_document_platform` | ok | youtube | 0 | 0 | 0 | — | 0 |
| Washington County | OR | `reader_needed` | ok | civicweb, granicus, youtube | 0 | 0 | 50 | 2026-08-25 … 2026-11-18 | 0 |
| Berwick | PA | `no_document_platform` | ok | none | 0 | 0 | 0 | — | 0 |
| Columbia County | PA | `no_document_platform` | ok | none | 0 | 0 | 0 | — | 0 |
| Lancaster | PA | `no_document_platform` | ok | youtube | 0 | 0 | 186 | 2019-01-22 … 2025-10-06 | 0 |
| Lancaster County | PA | `reader_needed` | ok | civicplus_agenda_center | 0 | 0 | 0 | — | 0 |
| Edgefield County | SC | `unreachable` | unreachable | none | 0 | 0 | 25 | 2025-01-08 … 2026-11-12 | 0 |
| Trenton | SC | `blocked` | blocked | none | 0 | 0 | 0 | — | 0 |
| Gallatin | TN | `reader_needed` | ok | civicclerk, civicplus_agenda_center, youtube | 0 | 0 | 44 | 2026-07-23 … 2026-11-16 | 0 |
| Memphis | TN | `blocked` | blocked | none | 0 | 0 | 98 | 2025-03-18 … 2026-11-13 | 6 |
| Shelby County | TN | `blocked` | blocked | none | 0 | 0 | 0 | — | 0 |
| Sumner County | TN | `unreachable` | unreachable | none | 0 | 0 | 25 | 2026-10-13 … 2026-11-16 | 0 |
| Abilene | TX | `no_document_platform` | ok | swagit | 0 | 0 | 10 | 2026-09-04 … 2026-11-10 | 0 |
| Armstrong County | TX | `no_document_platform` | ok | none | 0 | 0 | 0 | — | 0 |
| Bell County | TX | `no_document_platform` | ok | vimeo | 0 | 0 | 0 | — | 0 |
| Bexar County | TX | `blocked` | blocked | youtube | 0 | 0 | 38 | 2017-09-10 … 2026-11-09 | 2 |
| Claude | TX | `no_document_platform` | missing | none | 0 | 0 | 0 | — | 0 |
| Denton | TX | `blocked` | blocked | none | 0 | 0 | 0 | — | 0 |
| Denton County | TX | `reader_needed` | ok | civicplus_agenda_center, facebook_video, granicus, youtube | 0 | 0 | 41 | 2026-05-06 … 2026-11-11 | 0 |
| Dickens County | TX | `no_document_platform` | ok | none | 0 | 0 | 0 | — | 0 |
| Ellis County | TX | `no_document_platform` | ok | swagit | 0 | 0 | 0 | — | 0 |
| Midlothian | TX | `no_document_platform` | ok | swagit, youtube | 0 | 0 | 15 | 2017-09-29 … 2021-02-09 | 0 |
| Red Oak | TX | `reader_needed` | ok | civicclerk, youtube | 0 | 0 | 50 | 2025-03-12 … 2026-11-09 | 0 |
| San Antonio | TX | `blocked` | blocked | none | 0 | 0 | 21 | 2026-08-20 … 2026-11-19 | 0 |
| Taylor County | TX | `reader_needed` | ok | civicclerk, civicplus_agenda_center, suiteone | 0 | 0 | 0 | — | 0 |
| Temple | TX | `reader_needed` | ok | granicus, primegov, youtube | 0 | 0 | 42 | 2026-03-10 … 2026-11-05 | 0 |
| Eagle Mountain | UT | `blocked` | blocked | youtube | 0 | 0 | 48 | 2026-07-21 … 2026-11-10 | 0 |
| Utah County | UT | `no_document_platform` | ok | youtube | 0 | 0 | 185 | 2015-08-04 … 2026-11-18 | 2 |
| Chester | VA | `no_document_platform` | missing | — | 0 | 0 | 14 | 2026-10-12 … 2026-11-16 | 0 |
| Chesterfield County | VA | `reader_needed` | ok | civicclerk, youtube | 0 | 0 | 19 | 2026-09-23 … 2026-10-08 | 0 |
| Henrico County | VA | `blocked` | blocked | none | 0 | 0 | 0 | — | 0 |
| Loudoun County | VA | `reader_needed` | ok | escribe, granicus, youtube | 0 | 0 | 43 | 2023-08-14 … 2026-11-02 | 0 |
| Manassas | VA | `no_document_platform` | ok | granicus, youtube | 0 | 0 | 28 | 2025-09-22 … 2026-06-10 | 0 |
| Manassas city | VA | `no_document_platform` | missing | — | 0 | 0 | 0 | — | 0 |
| Prince William County | VA | `no_document_platform` | ok | granicus, youtube | 0 | 0 | 36 | 2026-03-13 … 2026-11-02 | 0 |
| Sandston | VA | `no_document_platform` | missing | — | 0 | 0 | 0 | — | 0 |
| Sterling | VA | `no_document_platform` | missing | — | 0 | 0 | 0 | — | 0 |
| Mount Pleasant | WI | `unreachable` | unreachable | youtube | 0 | 0 | 49 | 2025-05-21 … 2026-11-09 | 0 |
| Racine County | WI | `blocked` | blocked | none | 0 | 0 | 2 | 2020-04-07 … 2020-04-07 | 0 |
| Cheyenne | WY | `blocked` | blocked | youtube | 0 | 0 | 49 | 2026-01-13 … 2026-11-16 | 0 |
| Laramie County | WY | `blocked` | blocked | granicus | 0 | 0 | 0 | — | 0 |

## How to regenerate

```bash
python -m scrapers.discovery.data_center_agenda_scoreboard \
  --out web_docs/docs/development/data-center-agenda-scoreboard.md
```

