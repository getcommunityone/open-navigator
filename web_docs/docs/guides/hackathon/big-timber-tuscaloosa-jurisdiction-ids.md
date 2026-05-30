---
displayed_sidebar: developersSidebar
description: Bronze jurisdiction_id values (state, county, municipality, school district) for Big Timber, MT and Tuscaloosa, AL hackathon pilots, with discovery websites and links to scraped-meetings cache folders.
---

# Hackathon reference: Big Timber, MT & Tuscaloosa, AL jurisdiction IDs

Open Navigator **`jurisdiction_id`** values follow the prefixed bronze convention (see migration `013_add_jurisdiction_id_prefix.sql`):

| Type | Pattern | Example |
| ---- | ------- | ------- |
| State | `{USPS}` | `MT`, `AL` |
| County | `c-{USPS}-{county_geoid}` | `c-MT-30097` |
| Municipality (place) | `m-{USPS}-{place_geoid}` | `m-MT-3006475` |
| School district | `s-{USPS}-{lea_geoid}` | `s-AL-0103360` |

Scrape artifacts live under **`data/cache/scraped_meetings/{USPS}/{type}/...`** in a local clone (cache is typically gitignored). Links below point at the **[open-navigator](https://github.com/getcommunityone/open-navigator)** repo tree so you can copy paths or open them after generating data locally.

---

## Big Timber, Montana

| Jurisdiction type | `jurisdiction_id` | Census / NCES GEOID | Website (discovery / override) | Scraped meetings folder (repo path) |
| ----------------- | ----------------- | ------------------- | -------------------------------- | ------------------------------------- |
| State | `MT` | State FIPS `30` | — | [`data/cache/scraped_meetings/MT`](https://github.com/getcommunityone/open-navigator/tree/main/data/cache/scraped_meetings/MT) |
| County (Sweet Grass) | `c-MT-30097` | County `30097` | [sweetgrasscountygov.com](http://sweetgrasscountygov.com/) (NACO) | [`.../MT/county/county_30097`](https://github.com/getcommunityone/open-navigator/tree/main/data/cache/scraped_meetings/MT/county/county_30097) |
| City (Big Timber) | `m-MT-3006475` | Place `3006475` | [cityofbigtimber.com](https://cityofbigtimber.com/) (override) | [`.../MT/municipality/municipality_3006475`](https://github.com/getcommunityone/open-navigator/tree/main/data/cache/scraped_meetings/MT/municipality/municipality_3006475) |
| Schools (Sweet Grass County / LEA 3003800) | `s-MT-3003800` | District `3003800` | — | [`.../MT/school/school_district_3003800`](https://github.com/getcommunityone/open-navigator/tree/main/data/cache/scraped_meetings/MT/school/school_district_3003800) |

**Sweet Grass area, other NCES LEAs (not this `3003800` folder):** NCES directory seed rows include [www.co.sweetgrass.mt.us](https://www.co.sweetgrass.mt.us) (LEA `3000079`, “Sweet Grass” district) and [www.sgchs.com](https://www.sgchs.com) (LEA `3025560`, Sweet Grass County HS). The hackathon meetings cache path above uses LEA **`3003800`**; see the [offline inventory](https://github.com/getcommunityone/open-navigator/blob/main/docs/meetings_scrape_big_timber_tuscaloosa_inventory.md) for crawl context.

---

## Tuscaloosa, Alabama

| Jurisdiction type | `jurisdiction_id` | Census / NCES GEOID | Website (discovery / override) | Scraped meetings folder (repo path) |
| ----------------- | ----------------- | ------------------- | -------------------------------- | ------------------------------------- |
| State | `AL` | State FIPS `01` | — | [`data/cache/scraped_meetings/AL`](https://github.com/getcommunityone/open-navigator/tree/main/data/cache/scraped_meetings/AL) |
| County (Tuscaloosa) | `c-AL-01125` | County `01125` | [www.tuscco.com](https://www.tuscco.com/) (override; NACO lists `http://www.tuscco.com`) | [`.../AL/county/county_01125`](https://github.com/getcommunityone/open-navigator/tree/main/data/cache/scraped_meetings/AL/county/county_01125) |
| City (Tuscaloosa) | `m-AL-0177256` | Place `0177256` | [www.tuscaloosa.com](https://www.tuscaloosa.com/) (League of Cities override; USCM seed `http://www.tuscaloosa.com`) | [`.../AL/municipality/municipality_0177256`](https://github.com/getcommunityone/open-navigator/tree/main/data/cache/scraped_meetings/AL/municipality/municipality_0177256) |
| Schools — **Tuscaloosa City** | `s-AL-0103360` | LEA `0103360` | District [tuscaloosacityschools.com](https://www.tuscaloosacityschools.com); board […/board-of-education](https://www.tuscaloosacityschools.com/about-us/board-of-education); meetings [Simbli S=2088](https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx?S=2088) (overrides) | [`.../AL/school/school_district_0103360`](https://github.com/getcommunityone/open-navigator/tree/main/data/cache/scraped_meetings/AL/school/school_district_0103360) |
| Schools — **Tuscaloosa County (TCSS)** | `s-AL-0103390` | LEA `0103390` | District [tcss.net](https://www.tcss.net); board […/board-of-education](https://www.tcss.net/board-of-education/); meetings [Simbli S=2092](https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx?S=2092) (overrides) | [`.../AL/school/school_district_0103390`](https://github.com/getcommunityone/open-navigator/tree/main/data/cache/scraped_meetings/AL/school/school_district_0103390) |

The county commission crawl is **`county_01125`**, not the city folder—“Tuscaloosa County” and “City of Tuscaloosa” are separate jurisdictions. Warehouse source id for the city website row: `uscm` + `AL` + `tuscaloosa` (joined with `|` in the database).

**Cache folder names** use the legacy suffix form (`county_01125`, `municipality_0177256`, …) under `data/cache/scraped_meetings/…`; **`jurisdiction_id`** in bronze uses the prefixed form (`c-AL-01125`, `m-AL-0177256`, …).

---

## Related repo notes

- Offline inventory / QA snapshot: [`docs/meetings_scrape_big_timber_tuscaloosa_inventory.md`](https://github.com/getcommunityone/open-navigator/blob/main/docs/meetings_scrape_big_timber_tuscaloosa_inventory.md)
