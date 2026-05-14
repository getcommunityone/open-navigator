# Local meetings scrape inventory (Big Timber, MT · Tuscaloosa, AL)

Snapshot of `data/cache/scraped_meetings` folders for side-by-side QA. Paths are relative to the repo root unless noted.

| Location | Entity | Folder | Crawl status |
| -------- | ------ | ------ | ------------ |
| Big Timber | County (Sweet Grass County; Big Timber is the seat) | `data/cache/scraped_meetings/MT/county/county_30097` | Complete manifest — `_manifest.json` present, scraped_at 2026-05-13T02:08:53Z, errors `[]`. WordPress; many HTML pages + PDFs under year subdirs. |
| Big Timber | School district (LEA 3003800 — county superintendent / schools path on sgcountymt.gov) | `data/cache/scraped_meetings/MT/school/school_district_3003800` | Complete manifest — `_manifest.json` present, scraped_at 2026-05-13T02:39:09Z, errors `[]`. Agendas/minutes PDFs (e.g. under `2026/`). |
| Big Timber | City of Big Timber (place GEOID 3006475) | `data/cache/scraped_meetings/MT/municipality/municipality_3006475` | Incomplete — no `_manifest.json`. Only `_sitemaps/` (inventory + raw XML) and a few `_crawl_html/` pages; crawl did not finish to a written manifest. |
| Tuscaloosa | **Tuscaloosa County** (Census county GEOID **01125**; commission site) | `data/cache/scraped_meetings/AL/county/county_01125` | Complete manifest — `_manifest.json` present, scraped_at **2026-05-11T19:23:18Z**, errors `[]`. WordPress; county commission meeting **HTML** posts in crawl slice; `pdfs` empty in manifest (PDFs may appear on linked hosts or in a future run). |
| Tuscaloosa | City of Tuscaloosa (place GEOID 0177256) | `data/cache/scraped_meetings/AL/municipality/municipality_0177256` | Complete manifest — scraped_at 2026-05-12T00:32:30Z, errors `[]`. YouTube channel + Vimeo noted; `pdfs` `[]` in manifest. |
| Tuscaloosa | Tuscaloosa City Schools (LEA 0103360) | `data/cache/scraped_meetings/AL/school/school_district_0103360` | Manifest present but degraded — scraped_at 2026-05-12T02:01:09Z; `errors` include many Cloudflare captcha blocks on board pages and some PDF URLs returned non-HTML. |

**Why Tuscaloosa County looked “missing”:** it is not the same entity as the **city** or **city school district**. It lives under `AL/county/county_01125`, not under `municipality_` or `school_district_0103360`. For a full “Tuscaloosa area” picture, include **county** + **municipality** + relevant **school** districts (e.g. TCSS is `school_district_0103390`).
