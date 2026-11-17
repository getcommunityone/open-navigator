---
sidebar_position: 32
title: Data center meeting sources
description: Where the governments around each US data center publish their meetings, from the survey run on November 16, 2026.
---

# Data center meeting sources

Most towns near a US data center have no meetings in our data. This survey asks where those governments publish
their meetings, so we know which readers to build. Logged in [#460](https://github.com/getcommunityone/open-navigator/issues/460).

All numbers below come from one run on November 16, 2026:

```bash
python -m scrapers.discovery.survey_meeting_sources --data-center-sites --apply --youtube-search 40
```

The results are in `bronze.bronze_jurisdiction_meeting_source` (local warehouse) and in the report files under
`data/cache/data_center_survey/`.

## How it works

1. For each US site in `public.data_center_site`, it reads the city from the address. It matches the city in
   `intermediate.int_jurisdictions` and the county through `public.jurisdiction_county_crosswalk`.
2. It picks the government's website from `intermediate.int_jurisdiction_websites`.
3. It reads the homepage and up to 10 pages on the same site about agendas, meetings, minutes, video or the council.
4. It records every meeting platform those pages link to, embed or load scripts from.
5. For sites it can't read, it checks the vendors' own hosts (for example `<name>.legistar.com`). It can also run a
   capped YouTube channel search.

### We don't get around bot protection

If a site answers 403, 429 or a challenge page, the survey records it as **blocked** and leaves it alone. There is no
browser fallback, no second user agent and no other network route for a blocked page. The only retry happens
outside the VPN, and only for a connection failure like DNS or a timeout. A browser is used only when a page loads
fine but builds its links with JavaScript. In this run no page needed it.

A vendor page or YouTube channel counts only when it names the government and its state. A YouTube channel title
must be the government's name and nothing else, apart from the state and words like "TV" or "Government". That
rule keeps out channels like a county's Humane Society or a city's animal shelter.

## Who was surveyed

- **62** US data center sites.
- **92** governments: 44 cities and towns, 48 counties.
- The city matched for 51 sites.
- 6 sites are in census-designated places with no city government: Sandston (3 sites), Chester and Sterling in
  Virginia, and Marble in North Carolina. Only their county is surveyed.
- 5 sites have a city we couldn't match: Afton TX, Bristow VA, Pryor OK, Toney AL and Holly Ridge LA. For 4 of them
  the county came from the ZIP code instead. Toney AL has no ZIP in its address, so it has no county either.
- Manassas VA is an independent city, so the city and the "county" are one government. It is counted once.

## Website status

| Status | Governments |
|---|---|
| ok | 54 |
| blocked | 29 |
| unreachable | 6 |
| missing | 3 |

- **Blocked:** 28 answered 403 and 1 answered 429 (Bexar County TX).
- **Unreachable:** 2 sites have a TLS certificate for the wrong host (Mount Pleasant WI, Clark County IN). 3 closed
  the connection (Sumner County TN, Edgefield County SC, Ellendale ND). 1 listed site returns 404 (St. Joseph
  County IN).
- **Missing:** we have no website for New Carlisle IN or Claude TX. Richland Parish LA's only website on file is
  another county's (see [#461](https://github.com/getcommunityone/open-navigator/issues/461)), so we didn't use it.

## Meeting sources found

130 sources across 60 governments. Counted once per government:

| Platform | Governments | Media | We read it today |
|---|---|---|---|
| YouTube | 50 | video | yes |
| Granicus | 9 | video and documents | no |
| CivicPlus Agenda Center | 8 | documents | no |
| CivicClerk | 7 | documents | no |
| Legistar | 4 | documents | yes |
| CivicWeb | 3 | documents | no |
| Swagit | 3 | video | no |
| Vimeo | 2 | video | no |
| eScribe | 2 | documents | no |
| PrimeGov | 1 | documents | no |
| Cablecast | 1 | video | no |
| Facebook video | 1 | video | no |
| SuiteOne | 1 | video and documents | yes |

None were found for BoxCast, Municode Meetings, IQM2, BoardDocs or Zoom recordings.

- 56 governments have at least one video source. 4 have documents only.
- 112 sources came from the governments' own pages. 13 came from the YouTube search and 5 from vendor hosts.
- A YouTube link on a city page is not always a meeting channel. Some are a single promo video. Check before you
  build a catalog from it.

### Found without touching a blocked site

14 of the 29 blocked governments still have a source:

- **Vendor hosts:** Atlanta GA (`atlantaga.legistar.com`, `atlantaga.granicus.com`), Goodyear AZ
  (`goodyear.legistar.com`) and Laramie County WY (`laramiecounty.granicus.com`). Clark County IN, whose site is
  unreachable, has `pub-clarkcounty.escribemeetings.com`.
- **YouTube search:** Bexar County TX, Linn County IA, Pottawattamie County IA, New Albany OH, Eagle Mountain UT,
  Cheyenne WY, Montgomery AL, Montgomery County AL, Lancaster County NE, Douglas County NE and Fayetteville GA.
  Mount Pleasant WI and Cumberland County NJ also got a channel this way.

### YouTube search

The run checked 40 governments with no video source. 35 searches were answered. 5 were refused with HTTP 429
because the key had hit its daily quota: Berwick PA, Columbia County PA, Cumming IA, Claude TX and Richland Parish
LA. Search results are cached in `data/cache/data_center_survey/youtube_search_cache.json`, so a rerun only spends
quota on new searches.

## Governments with no source found (32)

- **Blocked (15):** San Antonio TX, Henrico County VA, Racine County WI, Columbus OH, Franklin County OH, Denton TX,
  Memphis TN, Shelby County TN, Lincoln NE, Trenton SC, Hillsboro OR, Council Bluffs IA, Omaha NE, Fort Wayne IN,
  Allen County IN.
- **Site read, nothing found (10):** Dickens County TX, Berwick PA, Columbia County PA, Barker NY, Wood County OH,
  Cumming IA, Valencia County NM, Dickey County ND, Mayes County OK, Armstrong County TX.
- **Unreachable (4):** Sumner County TN, St. Joseph County IN, Edgefield County SC, Ellendale ND.
- **Missing website (3):** New Carlisle IN, Claude TX, Richland Parish LA.

## All 29 blocked governments

San Antonio TX, Bexar County TX, Henrico County VA, Racine County WI, Linn County IA, Columbus OH, Franklin County
OH, Denton TX, New Albany OH, Eagle Mountain UT, Memphis TN, Shelby County TN, Cheyenne WY, Laramie County WY,
Goodyear AZ, Montgomery AL, Montgomery County AL, Atlanta GA, Lincoln NE, Lancaster County NE, Trenton SC, Hillsboro
OR, Council Bluffs IA, Pottawattamie County IA, Omaha NE, Douglas County NE, Fort Wayne IN, Allen County IN,
Fayetteville GA.

The owner decides how to get these. Options: ask the government, file a public records request, or use an RSS or
calendar feed the government publishes.

## Readers to build

Ranked by how many of these governments use a platform we don't read yet:

1. **Granicus** (9 governments): video and agendas, often on one page.
2. **CivicPlus Agenda Center** (8): agendas and minutes.
3. **CivicClerk** (7): agendas and minutes.
4. **CivicWeb** and **Swagit** (3 each).

YouTube is the biggest source (50 governments), and we already read it. Many of those channels may not be in our
catalog yet. Comparing them with the catalog is a follow-up.

## Rerun

```bash
# dry run: prints the table and writes the report, no database writes
python -m scrapers.discovery.survey_meeting_sources --data-center-sites
# one government
python -m scrapers.discovery.survey_meeting_sources --jurisdiction-id abilene_4801000
```

`--apply` replaces the rows of each government in the run. A government with nothing found gets one row with
`platform = 'none'`, so its website status stays on record.
