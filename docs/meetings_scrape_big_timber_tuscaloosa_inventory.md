# Local meetings scrape inventory (Big Timber, MT · Tuscaloosa, AL)

Snapshot of `data/cache/scraped_meetings` folders for side-by-side QA. Paths are relative to the repo root unless noted.

## Jurisdiction IDs and website URLs (discovery / overrides)

Sources in the warehouse row dump: `naco`, `nces_directory`, `uscm`, `league`, `override`. Where both a base URL and an `override` exist, the **override** URL is the one typically used for crawl entry (board / meetings / HTTPS).

| jurisdiction_id | NCES / other key | Type | Name | Host / entry URL (effective) |
| ----------------- | ---------------- | ---- | ---- | ------------------------------ |
| `county_30097` | naco `30097` | county | Sweet Grass County, MT | [sweetgrasscountygov.com](http://sweetgrasscountygov.com/) (naco) |
| `county_01125` | naco `01125` | county | Tuscaloosa County, AL | [www.tuscco.com](https://www.tuscco.com/) (override; naco lists `http://www.tuscco.com`) |
| `municipality_3006475` | — | municipality | Big Timber city, MT | [cityofbigtimber.com](https://cityofbigtimber.com/) (override) |
| `municipality_0177256` | uscm (AL, tuscaloosa) | municipality | Tuscaloosa, AL | [www.tuscaloosa.com](https://www.tuscaloosa.com/) (league; uscm `http://www.tuscaloosa.com`) |
| `school_district_0103390` | NCES `0103390` | school_district | Tuscaloosa County School District, AL | District: [www.tcss.net](https://www.tcss.net); board hub: [tcss.net/board-of-education/](https://www.tcss.net/board-of-education/) (override); meetings listing: [simbli…S=2092](https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx?S=2092) (override) |
| `school_district_0103360` | NCES `0103360` | school_district | Tuscaloosa City School District, AL | District: [www.tuscaloosacityschools.com](https://www.tuscaloosacityschools.com); board: [tuscaloosacityschools.com/…/board-of-education](https://www.tuscaloosacityschools.com/about-us/board-of-education) (override); meetings listing: [simbli…S=2088](https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx?S=2088) (override) |
| *(no `school_district_*` in row)* | NCES `3000079` | school_district | Sweet Grass, MT | [www.co.sweetgrass.mt.us](https://www.co.sweetgrass.mt.us) (nces_directory) |
| *(no `school_district_*` in row)* | NCES `3025560` | school_district | Sweet Grass County H S, MT | [www.sgchs.com](https://www.sgchs.com) (nces_directory) |

Warehouse source id for the Tuscaloosa city row: `uscm|AL|tuscaloosa`.

| Location | Entity | Folder | Crawl status |
| -------- | ------ | ------ | ------------ |
| Big Timber | County (Sweet Grass County; Big Timber is the seat) | `data/cache/scraped_meetings/MT/county/county_30097` | Complete manifest — `_manifest.json` present, scraped_at 2026-05-13T02:08:53Z, errors `[]`. WordPress; many HTML pages + PDFs under year subdirs. |
| Big Timber | School district (LEA 3003800 — county superintendent / schools path on sgcountymt.gov) | `data/cache/scraped_meetings/MT/school/school_district_3003800` | Complete manifest — `_manifest.json` present, scraped_at 2026-05-13T02:39:09Z, errors `[]`. Agendas/minutes PDFs (e.g. under `2026/`). |
| Big Timber | City of Big Timber (place GEOID 3006475) | `data/cache/scraped_meetings/MT/municipality/municipality_3006475` | Incomplete — no `_manifest.json`. Only `_sitemaps/` (inventory + raw XML) and a few `_crawl_html/` pages; crawl did not finish to a written manifest. |
| Tuscaloosa | **Tuscaloosa County** (Census county GEOID **01125**; commission site) | `data/cache/scraped_meetings/AL/county/county_01125` | Complete manifest — `_manifest.json` present, scraped_at **2026-05-11T19:23:18Z**, errors `[]`. WordPress; county commission meeting **HTML** posts in crawl slice; `pdfs` empty in manifest (PDFs may appear on linked hosts or in a future run). |
| Tuscaloosa | City of Tuscaloosa (place GEOID 0177256) | `data/cache/scraped_meetings/AL/municipality/municipality_0177256` | Complete manifest — scraped_at 2026-05-12T00:32:30Z, errors `[]`. YouTube channel + Vimeo noted; `pdfs` `[]` in manifest. |
| Tuscaloosa | Tuscaloosa City Schools (LEA 0103360) | `data/cache/scraped_meetings/AL/school/school_district_0103360` | Manifest present but degraded — scraped_at 2026-05-12T02:01:09Z; `errors` include many Cloudflare captcha blocks on board pages and some PDF URLs returned non-HTML. |

**Why Tuscaloosa County looked “missing”:** it is not the same entity as the **city** or **city school district**. It lives under `AL/county/county_01125`, not under `municipality_` or `school_district_0103360`. For a full “Tuscaloosa area” picture, include **county** + **municipality** + relevant **school** districts (e.g. TCSS is `school_district_0103390`).
