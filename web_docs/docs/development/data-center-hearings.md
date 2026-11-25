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
- A lead with an **official government URL** is fetched. It becomes a **verified hearing** only if that page says a
  data center word and states the claimed date.
- Only verified hearings are served. They appear under **Hearings coming up** on `/data-centers`, each quoting the
  official page with the matched words highlighted and linking to it.
- Every other lead keeps a status that says what is missing. Nothing is shown on a tracker's or a research tool's
  word alone.

## Statuses

| `status` | Meaning |
| --- | --- |
| `verified` | The official page says a data center word and states the claimed date |
| `date_not_found` | The page names the data center item but not the claimed date (the meeting may have moved) |
| `no_data_center_mention` | The page doesn't say a data center word |
| `fetch_failed` | Fetched, but nothing read: robots.txt or the never-fetch list said no, an HTTP error, a bot check, or a scanned PDF with no text layer |
| `not_fetched` | Official URL, not fetched yet |
| `unsourced` | No official URL: only a tracker, a news report, or nothing |

The date can be written out ("December 1", "Dec. 1st") or numeric ("12/01/2026", "12-1-26", "2026-12-01"). The year
isn't required, because agendas often omit it.

**Evidence** is the passage around the date on the official page, with any data center words marked. That's the text
that shows the page announces this meeting. If the date stands alone on its line, as on PDF agendas, the page's data
center passage follows it.

## Where each piece lives

| Step | Where | What it does |
| --- | --- | --- |
| Leads | seed `data_center_hearing_lead` | One row per claimed meeting: date, place, body, topic, `source_kind` (`official`, `tracker`, `news`, `none`), `source_url` with tracking parameters removed, `lead_from` |
| Fetch | `python -m ingestion.data_centers.fetch_hearing_sources` | Fetches each official URL once. It identifies itself, honours robots.txt and the `BLOCKED_HOSTS` never-fetch list, spaces requests per host, and turns PDF agendas into text with PyMuPDF. Writes `bronze.bronze_data_center_hearing_source`. It writes only to the local or dev warehouse (`--database-url` or `NEON_DATABASE_URL_DEV`), never to production |
| Verify | mart `data_center_hearing` (gold, served in `public`, copied to Neon) | One row per lead, with `status`, `evidence` and `checked_at`. PK `data_center_hearing_id` (the lead id). FK `jurisdiction_id` → `jurisdictions` when exactly one city, town or county in the state has the name, otherwise null |
| API | `GET /api/data-centers/hearings?state=&city=&when=upcoming\|past\|all` | Verified rows only, upcoming soonest first. `available: false` with null counts when the table isn't loaded |
| Page | `/data-centers?state=&city=`, "Hearings coming up" | Shown only when there is a verified upcoming hearing in the scope |

## Refreshing

Agendas are posted 3 to 7 days before a meeting, so a lead that is `date_not_found` or `fetch_failed` today can verify
next week. Re-run the fetch, then the mart:

```bash
python -m ingestion.data_centers.fetch_hearing_sources
./scripts/dbt.sh run --select data_center_hearing
```

To add leads, add rows to `dbt_project/seeds/data_center_hearing_lead.csv`, then run
`./scripts/dbt.sh seed --select data_center_hearing_lead`. Keep the body's wording as the source gives it, mark one
that looks wrong "(as listed)", and use the government's own URL as `source_url`. Tracker pages are leads, not sources.

## First load (25 Nov 2026)

There are 54 leads from the owner's two research lists: 11 official, 23 from trackers, 1 news, and 19 unsourced. Six
are verified:

| Date | Place | What the official page says |
| --- | --- | --- |
| Nov 30 | Harpersville, AL | the fourth informational session of the town's moratorium study |
| Dec 1 | Deer Park, TX | a joint public hearing "for December 1, 2026 … to amend the zoning ordinance as it relates to data centers" |
| Dec 1 | Lebanon Township, NJ | the Planning Board agenda, with "Revised Data Center Ordinance" on it |
| Dec 8 | Pima County, AZ | the ordinance "tentatively scheduled for the Board of Supervisors December 8, 2026 meeting" |
| Dec 9 | Cochise County, AZ | the Planning and Zoning Commission hearing SU26-22 on December 9 |
| Dec 15 | Savannah, GA | the Metropolitan Planning Commission public hearing on December 15 |

The four that failed show the guard rails working:
- **Robots.txt:** Wichita and Larimer County disallow automated fetching of those pages, so they weren't fetched.
- **Refused:** Forward Pinellas answered 403.
- **No text:** Brownfield, ME's agenda is a scanned PDF with no text layer.

Shawnee County's page doesn't mention a data center.

Which trackers may feed leads, and on what terms, is being recorded in
[#956](https://github.com/getcommunityone/open-navigator/issues/956) (hearing trackers) and
[#958](https://github.com/getcommunityone/open-navigator/issues/958) (facility inventories).
