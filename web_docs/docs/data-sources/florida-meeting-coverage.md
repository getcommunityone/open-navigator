---
title: Florida meeting coverage inventory
---

# Florida meeting coverage inventory (#1425)

The 67 counties and the 150 most populous cities in Florida, with where each publishes meetings, whether we hold them, and whether the site's terms allowed collection. Generated from `public.jurisdictions`, `bronze.bronze_jurisdiction_meeting_source` (the #460 survey, run for FL on 2026-11-27), `intermediate.int_jurisdiction_homepage_youtube_channels`, `bronze.bronze_event_youtube` and `public.recorded_meeting_year`.

Columns: **Ch** homepage-linked YouTube channels; **Vid** videos in `bronze_event_youtube` (**2024+** of them); **Tr** with a caption transcript; **Rec** recorded meetings in `recorded_meeting_year`; **DC** data center sites in the county or city (`data_center_site`); **Platforms** meeting platforms the site links to; **Terms** result of the polite survey. Blocked sites are never worked around.


## How FL is collected (all free, polite, local warehouse only)

1. **Survey** (`python -m scrapers.discovery.survey_meeting_sources --jurisdiction-id <id> ... --apply`): reads each government's own website (robots.txt honoured, open-navigator user agent, 2 at a time) and records every meeting platform it links to in `bronze.bronze_jurisdiction_meeting_source`. 217 governments surveyed: 120 sites read, 38 blocked (403 or a challenge page: left alone), 8 unreachable, 51 with no website on record. Platforms found: YouTube 78 governments, Granicus 25, Legistar 23, CivicClerk 18, CivicPlus Agenda Center 11, IQM2 11, Vimeo 6, Swagit 5, CivicWeb 5, eScribe 4, PrimeGov 4.
2. **Platform portals** (`python -m scrapers.platforms.run --data-center --state-code FL --since 2024-01-01 --apply`): Legistar Web API (public) is read; **Granicus is not**, because its `robots.txt` disallows `ViewPublisher.php` for all crawlers (24 portals `robots_disallowed`, 2 `blocked`). Those governments are listed as "link only" unless they also publish on YouTube.
3. **YouTube catalog and captions** (`STATES` in `packages/scrapers/scripts/youtube_run_priority_states_last_n.sh` now includes FL): `load_youtube_events_to_postgres --max-videos 80 --days 1060 --skip-transcripts`, then `backfill_jurisdiction_transcripts --newest 80 --delay 10` through the VPN guard with cookies, no proxy. Governments with data center sites go first, then by population. School boards are not expanded (resident names, AGENTS.md privacy rules); the 31 school-board channels already held stay as they are.
4. **Free linking** after transcripts land: `dbt build --select int_data_center_transcript__passage data_center_meeting_mention topic_transcript_link meeting_cause_link recorded_meeting_year`, then `python -m ingestion.meetings.comment_segments`, then `dbt build --select meeting_comment data_center_comment data_center_comment_place`. No Gemini or other paid analysis runs.

Pace: one caption fetch takes about 27 seconds with the 10 second delay and the probe, and YouTube throttles by IP address, so the fetch is not parallelised. About 100 transcripts an hour is the measured rate; the 162 non-school FL governments hold roughly 5,000 to 8,000 videos from 2024 to 2026, so the full backfill takes about 2 to 3 days of continuous running. It resumes where it stopped (already-captioned videos are skipped).

## Not collectable (terms)

- Granicus portals: robots.txt disallows the publisher pages for every crawler (24 FL portals).
- Websites that answered 403 or a challenge page: recorded as blocked, never retried or worked around (38 governments, marked `blocked` below).
- Governments with no website on record (51) and unreachable sites (8) have no source until one is found.

## Counties

| Government | Pop. | Ch | Vid | 2024+ | Tr | Rec | DC | Platforms | Terms |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| Miami-Dade County | 2688237 | 0 | 44 | 44 | 44 | 26 | 18 | youtube | robots.txt honoured; read |
| Broward County | 1940907 | 0 | 0 | 0 | 0 | 0 | 4 | none found | blocked (403/challenge): not scraped, link only |
| Palm Beach County | 1494805 | 0 | 0 | 0 | 0 | 0 | 6 | youtube | robots.txt honoured; read |
| Hillsborough County | 1468560 | 0 | 64 | 64 | 64 | 62 | 7 | legistar, youtube | robots.txt honoured; read |
| Orange County | 1427403 | 0 | 0 | 0 | 0 | 0 | 5 | none found | site unreachable |
| Duval County | 995708 | 0 | 52 | 52 | 38 | 38 | 7 | none found | robots.txt honoured; read |
| Pinellas County | 959918 | 0 | 0 | 0 | 0 | 0 | 1 | granicus, legistar, youtube | robots.txt honoured; read |
| Lee County | 772902 | 0 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Polk County | 736229 | 0 | 0 | 0 | 0 | 0 | 4 | granicus, iqm2, legistar | blocked (403/challenge): not scraped, link only |
| Brevard County | 610723 | 0 | 0 | 0 | 0 | 0 | 1 | iqm2 | blocked (403/challenge): not scraped, link only |
| Pasco County | 569211 | 0 | 0 | 0 | 0 | 0 | 0 | youtube | robots.txt honoured; read |
| Volusia County | 558520 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Seminole County | 471321 | 0 | 0 | 0 | 0 | 0 | 0 | legistar, youtube | robots.txt honoured; read |
| Sarasota County | 439392 | 0 | 0 | 0 | 0 | 0 | 1 | none found | robots.txt honoured; read |
| Manatee County | 405069 | 0 | 0 | 0 | 0 | 0 | 0 | youtube | robots.txt honoured; read |
| Osceola County | 393745 | 0 | 0 | 0 | 0 | 0 | 2 | none found | blocked (403/challenge): not scraped, link only |
| Lake County | 386829 | 0 | 0 | 0 | 0 | 0 | 0 | youtube | robots.txt honoured; read |
| Collier County | 380221 | 0 | 7 | 0 | 7 | 7 | 1 | youtube | robots.txt honoured; read |
| Marion County | 378225 | 0 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| St. Lucie County | 334682 | 0 | 0 | 0 | 0 | 0 | 3 | none found | blocked (403/challenge): not scraped, link only |
| Escambia County | 321296 | 0 | 0 | 0 | 0 | 0 | 1 | civicclerk, youtube | robots.txt honoured; read |
| Leon County | 294128 | 0 | 0 | 0 | 0 | 0 | 2 | none found | blocked (403/challenge): not scraped, link only |
| Alachua County | 279729 | 0 | 0 | 0 | 0 | 0 | 1 | none found | site unreachable |
| St. Johns County | 278722 | 0 | 0 | 0 | 0 | 0 | 0 | swagit, youtube | robots.txt honoured; read |
| Clay County | 219650 | 0 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Okaloosa County | 212021 | 0 | 0 | 0 | 0 | 0 | 0 | iqm2, youtube | robots.txt honoured; read |
| Hernando County | 196621 | 0 | 0 | 0 | 0 | 0 | 0 | iqm2, legistar, youtube | robots.txt honoured; read |
| Charlotte County | 189900 | 0 | 0 | 0 | 0 | 0 | 0 | civicclerk, granicus, youtube | robots.txt honoured; read |
| Santa Rosa County | 188994 | 0 | 0 | 0 | 0 | 0 | 0 | civicclerk, youtube | robots.txt honoured; read |
| Bay County | 181055 | 0 | 0 | 0 | 0 | 0 | 0 | swagit | robots.txt honoured; read |
| Indian River County | 160986 | 0 | 0 | 0 | 0 | 0 | 0 | cablecast, civicclerk, youtube | robots.txt honoured; read |
| Martin County | 159399 | 0 | 0 | 0 | 0 | 0 | 1 | granicus, legistar, youtube | robots.txt honoured; read |
| Citrus County | 155173 | 0 | 0 | 0 | 0 | 0 | 1 | civicclerk, youtube | robots.txt honoured; read |
| Sumter County | 131832 | 0 | 0 | 0 | 0 | 0 | 0 | civicclerk, youtube | robots.txt honoured; read |
| Flagler County | 117515 | 0 | 0 | 0 | 0 | 0 | 1 | none found | robots.txt honoured; read |
| Highlands County | 102339 | 0 | 0 | 0 | 0 | 0 | 0 | civicclerk, granicus, youtube | robots.txt honoured; read |
| Nassau County | 91538 | 0 | 0 | 0 | 0 | 0 | 1 | novusagenda, primegov, youtube | robots.txt honoured; read |
| Monroe County | 82044 | 0 | 0 | 0 | 0 | 0 | 0 | granicus, iqm2, youtube | robots.txt honoured; read |
| Walton County | 76618 | 0 | 0 | 0 | 0 | 0 | 0 | civicweb, youtube | robots.txt honoured; read |
| Putnam County | 73604 | 0 | 0 | 0 | 0 | 0 | 0 | youtube | robots.txt honoured; read |
| Columbia County | 69832 | 0 | 0 | 0 | 0 | 0 | 0 | none found | site unreachable |
| Jackson County | 47704 | 0 | 0 | 0 | 0 | 0 | 0 | civicclerk, youtube | robots.txt honoured; read |
| Suwannee County | 43881 | 0 | 0 | 0 | 0 | 0 | 0 | civicclerk, youtube | robots.txt honoured; read |
| Gadsden County | 43746 | 0 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Levy County | 43268 | 0 | 0 | 0 | 0 | 0 | 0 | municode_meetings | robots.txt honoured; read |
| Hendry County | 39902 | 0 | 0 | 0 | 0 | 0 | 0 | civicweb, youtube | robots.txt honoured; read |
| Okeechobee County | 39870 | 0 | 0 | 0 | 0 | 0 | 1 | iqm2 | blocked (403/challenge): not scraped, link only |
| DeSoto County | 34258 | 0 | 0 | 0 | 0 | 0 | 1 | legistar | robots.txt honoured; read |
| Wakulla County | 33732 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Baker County | 27969 | 0 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Bradford County | 27816 | 0 | 0 | 0 | 0 | 0 | 0 | youtube | robots.txt honoured; read |
| Hardee County | 25528 | 0 | 0 | 0 | 0 | 0 | 0 | granicus, iqm2, youtube | robots.txt honoured; read |
| Washington County | 25014 | 0 | 0 | 0 | 0 | 0 | 0 | youtube | robots.txt honoured; read |
| Taylor County | 21421 | 0 | 0 | 0 | 0 | 0 | 0 | facebook_video, youtube | robots.txt honoured; read |
| Holmes County | 19529 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Gilchrist County | 18070 | 0 | 0 | 0 | 0 | 0 | 0 | youtube | robots.txt honoured; read |
| Madison County | 17986 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Dixie County | 16737 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Union County | 15524 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Gulf County | 15002 | 0 | 0 | 0 | 0 | 0 | 0 | youtube | robots.txt honoured; read |
| Jefferson County | 14458 | 0 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Calhoun County | 13753 | 0 | 0 | 0 | 0 | 0 | 0 | youtube | robots.txt honoured; read |
| Hamilton County | 13492 | 0 | 0 | 0 | 0 | 0 | 0 | none found | site unreachable |
| Franklin County | 12276 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Glades County | 12179 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Lafayette County | 8107 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Liberty County | 7704 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |

## Cities (150 largest)

| Government | Pop. | Ch | Vid | 2024+ | Tr | Rec | DC | Platforms | Terms |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| Jacksonville | 950203 | 0 | 0 | 0 | 0 | 0 | 7 | legistar, youtube | robots.txt honoured; read |
| Miami | 443665 | 0 | 54 | 54 | 17 | 6 | 9 | granicus, iqm2, legistar | blocked (403/challenge): not scraped, link only |
| Tampa | 388768 | 4 | 94 | 94 | 10 | 24 | 7 | youtube | robots.txt honoured; read |
| Orlando | 307738 | 4 | 235 | 24 | 14 | 218 | 4 | escribe, granicus, youtube | robots.txt honoured; read |
| St. Petersburg | 259343 | 0 | 0 | 0 | 0 | 0 | 0 | youtube | robots.txt honoured; read |
| Hialeah | 222996 | 0 | 27 | 27 | 10 | 11 | 0 | none found | site unreachable |
| Port St. Lucie | 210520 | 1 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Cape Coral | 198912 | 1 | 0 | 0 | 0 | 0 | 0 | escribe, novusagenda, vimeo, youtube | robots.txt honoured; read |
| Tallahassee | 198259 | 0 | 60 | 56 | 20 | 22 | 2 | granicus, youtube | robots.txt honoured; read |
| Fort Lauderdale | 182673 | 1 | 0 | 0 | 0 | 0 | 2 | legistar | blocked (403/challenge): not scraped, link only |
| Pembroke Pines | 170472 | 0 | 0 | 0 | 0 | 0 | 0 | civicplus_agenda_center, granicus, legistar, youtube | robots.txt honoured; read |
| Hollywood | 152764 | 2 | 0 | 0 | 0 | 0 | 0 | legistar, youtube | robots.txt honoured; read |
| Gainesville | 142414 | 0 | 0 | 0 | 0 | 0 | 1 | legistar | blocked (403/challenge): not scraped, link only |
| Miramar | 135158 | 2 | 0 | 0 | 0 | 0 | 0 | legistar | blocked (403/challenge): not scraped, link only |
| Coral Springs | 133801 | 1 | 0 | 0 | 0 | 0 | 0 | iqm2 | blocked (403/challenge): not scraped, link only |
| Lehigh Acres | 124440 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Palm Bay | 121513 | 0 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| West Palm Beach | 117588 | 0 | 47 | 47 | 10 | 10 | 1 | none found | blocked (403/challenge): not scraped, link only |
| Clearwater | 116984 | 2 | 30 | 30 | 20 | 20 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Spring Hill | 116882 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Brandon | 114923 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Lakeland | 114404 | 3 | 0 | 0 | 0 | 0 | 2 | vimeo | robots.txt honoured; read |
| Pompano Beach | 111790 | 0 | 0 | 0 | 0 | 0 | 1 | granicus, legistar, youtube | robots.txt honoured; read |
| Miami Gardens | 111618 | 1 | 0 | 0 | 0 | 0 | 1 | civicweb, youtube | robots.txt honoured; read |
| Davie | 105821 | 2 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Riverview | 102467 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Boca Raton | 97980 | 1 | 0 | 0 | 0 | 0 | 4 | granicus | robots.txt honoured; read |
| Sunrise | 96510 | 2 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Deltona | 94373 | 1 | 0 | 0 | 0 | 0 | 0 | cablecast, legistar | robots.txt honoured; read |
| Plantation | 93130 | 0 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Alafaya | 91531 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Palm Coast | 91082 | 1 | 0 | 0 | 0 | 0 | 1 | youtube | robots.txt honoured; read |
| Town 'n' Country | 89456 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Fort Myers | 88699 | 1 | 0 | 0 | 0 | 0 | 0 | civicplus_agenda_center, granicus, vimeo, youtube | robots.txt honoured; read |
| Deerfield Beach | 86455 | 0 | 0 | 0 | 0 | 0 | 0 | youtube | robots.txt honoured; read |
| Melbourne | 84982 | 0 | 0 | 0 | 0 | 0 | 1 | none found | blocked (403/challenge): not scraped, link only |
| Pine Hills | 83221 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Largo | 82541 | 2 | 0 | 0 | 0 | 0 | 0 | civicweb, youtube | robots.txt honoured; read |
| Miami Beach | 82400 | 1 | 0 | 0 | 0 | 0 | 0 | primegov, swagit, vimeo, youtube | robots.txt honoured; read |
| Boynton Beach | 80068 | 0 | 0 | 0 | 0 | 0 | 0 | granicus, youtube | robots.txt honoured; read |
| Homestead | 79996 | 3 | 0 | 0 | 0 | 0 | 1 | youtube | robots.txt honoured; read |
| The Villages | 79108 | 0 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Kissimmee | 78478 | 0 | 0 | 0 | 0 | 0 | 0 | none found | site unreachable |
| Kendall | 78402 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| North Port | 76975 | 1 | 0 | 0 | 0 | 0 | 1 | none found | blocked (403/challenge): not scraped, link only |
| Doral | 74891 | 2 | 0 | 0 | 0 | 0 | 3 | none found | blocked (403/challenge): not scraped, link only |
| Lauderhill | 73987 | 1 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Daytona Beach | 73329 | 2 | 0 | 0 | 0 | 0 | 0 | civicweb, youtube | robots.txt honoured; read |
| Tamarac | 71578 | 2 | 0 | 0 | 0 | 0 | 0 | youtube | robots.txt honoured; read |
| Poinciana | 69311 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Wesley Chapel | 68814 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Weston | 68029 | 0 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Delray Beach | 66646 | 1 | 0 | 0 | 0 | 0 | 0 | legistar | blocked (403/challenge): not scraped, link only |
| Port Charlotte | 63913 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Ocala | 63504 | 1 | 0 | 0 | 0 | 0 | 0 | iqm2, legistar | blocked (403/challenge): not scraped, link only |
| Port Orange | 62849 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Palm Harbor | 61589 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Wellington | 61373 | 0 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Sanford | 61272 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Jupiter | 60926 | 1 | 0 | 0 | 0 | 0 | 0 | civicclerk, youtube | robots.txt honoured; read |
| North Miami | 59854 | 1 | 0 | 0 | 0 | 0 | 0 | civicplus_agenda_center, vimeo, youtube | robots.txt honoured; read |
| St. Cloud | 59851 | 1 | 0 | 0 | 0 | 0 | 0 | youtube | robots.txt honoured; read |
| The Hammocks | 59843 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Palm Beach Gardens | 59088 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Horizon West | 58595 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Margate | 58396 | 0 | 0 | 0 | 0 | 0 | 0 | legistar | robots.txt honoured; read |
| Coconut Creek | 57574 | 0 | 0 | 0 | 0 | 0 | 0 | granicus, legistar, youtube | robots.txt honoured; read |
| Fountainebleau | 57066 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Four Corners | 56537 | 1 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Bradenton | 55795 | 0 | 0 | 0 | 0 | 0 | 0 | granicus, youtube | robots.txt honoured; read |
| Sarasota | 55508 | 2 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Apopka | 55056 | 0 | 0 | 0 | 0 | 0 | 0 | civicclerk, municode_meetings, youtube | robots.txt honoured; read |
| Pensacola | 54059 | 2 | 0 | 0 | 0 | 0 | 1 | none found | robots.txt honoured; read |
| Bonita Springs | 53945 | 1 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Westchester | 53765 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Pinellas Park | 53352 | 1 | 0 | 0 | 0 | 0 | 1 | youtube | robots.txt honoured; read |
| Tamiami | 52851 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Kendale Lakes | 52661 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Country Club | 50975 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Winter Haven | 50778 | 1 | 0 | 0 | 0 | 0 | 0 | granicus, youtube | robots.txt honoured; read |
| Coral Gables | 49696 | 0 | 0 | 0 | 0 | 0 | 0 | legistar | site unreachable |
| University | 49148 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Titusville | 48595 | 2 | 247 | 11 | 20 | 242 | 0 | civicclerk, youtube | robots.txt honoured; read |
| Ocoee | 47290 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Fort Pierce | 47153 | 0 | 0 | 0 | 0 | 0 | 3 | youtube | robots.txt honoured; read |
| Winter Garden | 46518 | 1 | 0 | 0 | 0 | 0 | 0 | civicplus_agenda_center | robots.txt honoured; read |
| Altamonte Springs | 45772 | 0 | 0 | 0 | 0 | 0 | 0 | civicplus_agenda_center | robots.txt honoured; read |
| Cutler Bay | 44738 | 0 | 0 | 0 | 0 | 0 | 0 | escribe, legistar, youtube | robots.txt honoured; read |
| North Lauderdale | 44635 | 0 | 0 | 0 | 0 | 0 | 0 | granicus | robots.txt honoured; read |
| Oakland Park | 44056 | 1 | 0 | 0 | 0 | 0 | 0 | granicus | robots.txt honoured; read |
| Greenacres | 43651 | 1 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| North Miami Beach | 43269 | 0 | 0 | 0 | 0 | 0 | 0 | civicplus_agenda_center, youtube | robots.txt honoured; read |
| Clermont | 43266 | 2 | 0 | 0 | 0 | 0 | 0 | civicclerk, youtube | robots.txt honoured; read |
| University | 43207 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Ormond Beach | 43127 | 1 | 0 | 0 | 0 | 0 | 0 | civicclerk, youtube | robots.txt honoured; read |
| North Fort Myers | 42492 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Meadow Woods | 42207 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Lake Worth Beach | 42188 | 1 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Hallandale Beach | 41102 | 0 | 0 | 0 | 0 | 0 | 0 | granicus, legistar | robots.txt honoured; read |
| Land O' Lakes | 40843 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| The Acreage | 40160 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Plant City | 39655 | 4 | 0 | 0 | 0 | 0 | 0 | youtube | robots.txt honoured; read |
| Aventura | 39621 | 3 | 0 | 0 | 0 | 0 | 0 | civicplus_agenda_center, youtube | robots.txt honoured; read |
| Oviedo | 39552 | 1 | 0 | 0 | 0 | 0 | 0 | primegov, youtube | robots.txt honoured; read |
| Royal Palm Beach | 38874 | 0 | 0 | 0 | 0 | 0 | 0 | civicplus_agenda_center, youtube | robots.txt honoured; read |
| Navarre | 38829 | 1 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Valrico | 38594 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| DeLand | 38392 | 2 | 0 | 0 | 0 | 0 | 0 | civicclerk, iqm2, youtube | robots.txt honoured; read |
| Winter Springs | 38205 | 1 | 0 | 0 | 0 | 0 | 0 | granicus, youtube | robots.txt honoured; read |
| Princeton | 37954 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Riviera Beach | 37668 | 1 | 97 | 60 | 10 | 40 | 0 | granicus | robots.txt honoured; read |
| Richmond West | 36964 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Estero | 36685 | 0 | 0 | 0 | 0 | 0 | 0 | none found | site unreachable |
| Carrollwood | 36148 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Dunedin | 36089 | 1 | 0 | 0 | 0 | 0 | 0 | none found | blocked (403/challenge): not scraped, link only |
| Egypt Lake-Leto | 36000 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Lauderdale Lakes | 35914 | 0 | 0 | 0 | 0 | 0 | 0 | primegov, swagit, youtube | robots.txt honoured; read |
| South Miami Heights | 35705 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Kendall West | 35606 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Fruit Cove | 35333 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Parkland | 34832 | 0 | 0 | 0 | 0 | 0 | 0 | swagit | robots.txt honoured; read |
| Lakewood Ranch | 34346 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Merritt Island | 34300 | 0 | 0 | 0 | 0 | 0 | 0 | none found | robots.txt honoured; read |
| Panama City | 34254 | 1 | 0 | 0 | 0 | 0 | 0 | civicplus_agenda_center | robots.txt honoured; read |
| Cooper City | 34046 | 3 | 0 | 0 | 0 | 0 | 0 | municode_meetings | robots.txt honoured; read |
| East Lake | 33629 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| West Little River | 33465 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Buenaventura Lakes | 33284 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Ferry Pass | 32447 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Dania Beach | 31700 | 0 | 0 | 0 | 0 | 0 | 0 | civicclerk, youtube | robots.txt honoured; read |
| Lake Magdalene | 31546 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Lakeside | 30973 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Miami Lakes | 30621 | 0 | 0 | 0 | 0 | 0 | 0 | escribe, vimeo, youtube | robots.txt honoured; read |
| New Smyrna Beach | 30449 | 0 | 0 | 0 | 0 | 0 | 0 | granicus | robots.txt honoured; read |
| Winter Park | 29985 | 0 | 0 | 0 | 0 | 0 | 0 | granicus | blocked (403/challenge): not scraped, link only |
| Vero Beach South | 29965 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Fleming Island | 29810 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Golden Gate | 29400 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Sun City Center | 29290 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Oakleaf Plantation | 29265 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| East Lake-Orient Park | 29243 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Casselberry | 29092 | 0 | 0 | 0 | 0 | 0 | 0 | civicclerk | robots.txt honoured; read |
| Haines City | 28922 | 1 | 0 | 0 | 0 | 0 | 1 | none found | robots.txt honoured; read |
| Ruskin | 28878 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Rockledge | 27808 | 0 | 0 | 0 | 0 | 0 | 0 | civicplus_agenda_center | robots.txt honoured; read |
| Immokalee | 27753 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Crestview | 27427 | 0 | 0 | 0 | 0 | 0 | 0 | civicplus_agenda_center, youtube | robots.txt honoured; read |
| Citrus Park | 27260 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
| Leesburg | 27226 | 0 | 0 | 0 | 0 | 0 | 0 | civicclerk, youtube | robots.txt honoured; read |
| Leisure City | 27033 | 0 | 0 | 0 | 0 | 0 | 0 | none found | missing |
