---
sidebar_position: 36
title: Upcoming data center hearings
description: How research leads on upcoming data center hearings become hearings the site shows, only after the government's own page confirms the date and the item.
---

# Upcoming data center hearings

[#955](https://github.com/getcommunityone/open-navigator/issues/955). Many local governments hold data center hearings,
moratorium votes and study sessions that our agenda crawl doesn't reach yet (see
[Data center items on agendas](./data-center-agenda-items.md)). Research lists and trackers name them, but they make
mistakes: wrong bodies, wrong dates, meetings that moved. The site shows a hearing only after the **government's own
page** confirms it.

## In short

- A **lead** is a claimed meeting: jurisdiction, state, body, date, topic, and where the claim came from.
- A lead with an **official government URL** is fetched. It becomes a **verified hearing** only if that page states
  the claimed date **together with** a data center word:
  - **Web page:** the word is within about 500 characters of the date, in the same section. Topic pages always say
    "data center" somewhere, so a date elsewhere on the page (a sidebar calendar, another deadline) is not enough.
  - **PDF agenda:** the agenda is the meeting itself, so the date and the item anywhere in it are enough.
- Only verified hearings are published: `data_center_hearing_verified` is the only one of the two tables in `public`
  and Neon. They appear under **Hearings coming up** on `/data-centers`. Each card quotes the official page with the
  matched words highlighted, links to it, and is marked **Tentative** when the page calls the date tentative, expected
  or not final. The body's name comes from the lead; a curated lead's topic is shown labelled "From the research
  lead". A tracker's own topic or summary text is never shown.
- Every other lead keeps a status that says what is missing. Nothing is shown on a tracker's or a research tool's
  word alone.

## Statuses

| `status` | Meaning |
| --- | --- |
| `verified` | The official page states the claimed date together with a data center word (see above) |
| `date_not_with_item` | A web page states the date, but not near a data center word |
| `date_not_found` | The page names the data center item but not the claimed date (the meeting may have moved) |
| `no_data_center_mention` | The page doesn't say a data center word |
| `fetch_failed` | Fetched, but nothing read: robots.txt or the never-fetch list said no, an HTTP error, a bot check, or a scanned PDF with no text layer |
| `not_fetched` | Official URL, not fetched yet |
| `unsourced` | No official URL: only a tracker, a news report, or nothing |

The date can be written out with a capital ("December 1", "DEC. 1st") or numeric ("12/01/2026", "12-1-26",
"2026-12-01"). Lowercase prose like "may 3" doesn't count. A written date followed by a different year ("December 1,
2025") doesn't count, but no year at all is fine, because agendas often omit it. A dbt unit test covers each of these
rules (`dc_hearing_verification_rules`).

**Evidence** is the date's own passage on the official page (250 characters each side), with whole data center phrases
marked. A side cut mid-text is trimmed to a whole word; a side that reached the edge of the page is kept whole, so the
date itself is never trimmed away. When that passage doesn't say the words, the nearest data center passage of the same
section (or of the agenda) follows after " … ". Both are verbatim.

## Where each piece lives

| Step | Where | What it does |
| --- | --- | --- |
| Leads (curated) | seed `data_center_hearing_lead` | One row per claimed meeting: date, place, body, topic, `source_kind` (`official`, `tracker`, `news`, `none`), `source_url` with tracking parameters removed, `lead_from` |
| Leads (trackers) | `python -m ingestion.data_centers.load_hearing_tracker_leads` → `bronze_data_center_hearing_tracker_lead` → `stg_data_center_hearing_tracker_lead` | The CC BY 4.0 files of Data Center Fights (`data.json` meetings, minus user-added ones) and Siting Radar (upcoming CSV), one request each; only each tracker's latest file counts. The place comes from the record's own words, and a record naming no local place is left out. A lead is `official` only when its URL's host is `.gov`, a locality `.us` name (`ci.x.mn.us`), or a government's own subdomain of an agenda platform (`x.legistar.com`, `x.api.civicclerk.com`, …). A city site on `.com` or `.org` stays a lead, because anyone can register a name like `cityofx.com` |
| All leads | `int_data_center_hearing_lead` | Every curated and tracker lead. Leads naming the same meeting share a `meeting_key` (state, place, county or not, date), and `lead_rank` orders them: a seed lead with an official URL, then a tracker lead with one, then the rest |
| Fetch | `python -m ingestion.data_centers.fetch_hearing_sources` | Fetches every official URL a lead cites, duplicates included, so a blocked seed URL can't hide a tracker's readable agenda (leads from the last week on; `--all`, or `--lead`, for older ones). It identifies itself, honours robots.txt and the `BLOCKED_HOSTS` never-fetch list, spaces requests per host, and turns PDF agendas into text with PyMuPDF. Writes `bronze.bronze_data_center_hearing_source`. It writes only to the local or dev warehouse (`--database-url` or `NEON_DATABASE_URL_DEV`), never to production |
| Verify | mart `data_center_hearing` (gold only) | One row per meeting, from the best of its leads (a verified one first, then `lead_rank`), with `status`, `evidence`, `tentative` and `checked_at`. PK `data_center_hearing_id` (the lead id). FK `jurisdiction_id` → `jurisdictions` when exactly one city, town or county in the state has the name, otherwise null |
| Serve | mart `data_center_hearing_verified` (served in `public`, copied to Neon) | Verified rows only, with the columns a reader needs. PK and FK to `data_center_hearing` and `jurisdictions` |
| API | `GET /api/data-centers/hearings?state=&city=&when=upcoming\|past\|all` | Verified rows only, upcoming soonest first. `available: false` with null counts when the table isn't loaded |
| Page | `/data-centers?state=&city=`, "Hearings coming up" | Shown only when there is a verified upcoming hearing in the scope; a **Tentative** badge when the page says so |

## Refreshing

Agendas are posted 3 to 7 days before a meeting, so a lead that is `date_not_found` or `fetch_failed` today can verify
next week. Re-run the fetch, then the mart:

```bash
python -m ingestion.data_centers.load_hearing_tracker_leads   # at most daily
./scripts/dbt.sh run --select stg_data_center_hearing_tracker_lead int_data_center_hearing_lead
python -m ingestion.data_centers.fetch_hearing_sources
./scripts/dbt.sh run --select data_center_hearing data_center_hearing_verified
```

The bronze tables both loaders write are created empty by the `ensure_data_center_hearing_tables` on-run-start
macro, so the marts build in a fresh warehouse before any loader has run (every lead then reads `not_fetched`).

To add leads, add rows to `dbt_project/seeds/data_center_hearing_lead.csv`, then run
`./scripts/dbt.sh seed --select data_center_hearing_lead`. Keep the body's wording as the source gives it, mark one
that looks wrong "(as listed)", and use the government's own URL as `source_url`. Tracker pages are leads, not sources.

## First load (25 Nov 2026)

There were 54 leads from the owner's two research lists: 11 official, 23 from trackers, 1 news, and 19 unsourced. Five
are verified:

| Date | Place | What the official page says |
| --- | --- | --- |
| Nov 30 | Harpersville, AL | the fourth informational session of the town's moratorium study |
| Dec 1 | Deer Park, TX | a joint public hearing "for December 1, 2026 … to amend the zoning ordinance as it relates to data centers" |
| Dec 1 | Lebanon Township, NJ | the Planning Board agenda, with "Revised Data Center Ordinance" on it |
| Dec 8 | Pima County, AZ | the ordinance "tentatively scheduled for the Board of Supervisors December 8, 2026 meeting" (**Tentative**) |
| Dec 15 | Savannah, GA | the Metropolitan Planning Commission public hearing on December 15, with the second draft "expected in early December" (**Tentative**) |

The others show the guard rails working:
- **Robots.txt:** Wichita and Larimer County disallow automated fetching of those pages, so they weren't fetched.
- **Refused:** Forward Pinellas answered 403.
- **No text:** Brownfield, ME's agenda is a scanned PDF with no text layer.
- **Not together:** Cochise County's page states December 9, but its nearest "data center" is more than 500 characters
  away, so it is `date_not_with_item`.
- **No mention:** Shawnee County's page doesn't mention a data center.

## Tracker leads (25 Nov 2026)

Which trackers may feed leads, and on what terms, is in
[Data center source review](./data-center-source-review.md)
([#956](https://github.com/getcommunityone/open-navigator/issues/956)). Two do, under CC BY 4.0: Data Center Fights (176
meetings, none user-added on this date) and Siting Radar (14 items, 12 of them data centers). A served row from a
tracker lead credits it in `source_name` ("Government page cited by Data Center Fights …, CC BY 4.0"). The tracker's
own topic or summary is never served.

Trackers add 128 leads that name a local place. Most cite news reports or notice registries, so they stay leads. Sixteen
cite a government host, and 7 of those were upcoming or from the last week:
- **Verified (2):**
  - Whitley County, IN, Nov 18: Plan Commission, "Data Center regulations - Public Hearing";
  - Calvert County, MD, Nov 18: Planning Commission hearing on "Revisions to Data Center Use".
- **No mention (2):** Starbase, TX and Elbert County, CO pages don't say a data center word.
- **Date not found (1):** Dorr Township, MI's packet doesn't state Dec 15.
- **Fetch failed (2):** Banks Township, MI's packet is scanned; Raleigh disallows its news page in robots.txt.

Kings Mountain, NC's moratorium hearing (Feb 23, 2027) is on the city's own site, but that site is `cityofkm.com`. A
`.com` host doesn't count as official, so it stays a lead until it is added to the seed by hand with that URL.

With all leads together, `data_center_hearing` holds 169 meetings, 7 of them verified.
