---
sidebar_position: 34
title: Data center sites
description: Where Open Navigator's data center sites come from (Epoch AI, CC BY 4.0), how status is worked out, and why a dropped site stays visible (DC-4.1).
---

# Data center sites

[DC-4.1](https://github.com/getcommunityone/open-navigator/issues/249) shows the data center sites in a state with
their status and source. It is part of the
[Data Center Accountability epic](https://github.com/getcommunityone/open-navigator/issues/236).

## In short

- **Sources**, both CC BY 4.0 and credited on every row (`source`, `source_name`, `source_url`, `attribution`) and on
  each card:
  - [Epoch AI, AI data centers](https://epoch.ai/data/data-centers): the largest AI data centers, with street addresses.
    Epoch includes planned sites only once they are under construction and likely to finish.
  - [US Data Center Registry](https://suedatacenters.org/data-centers/data) (SueDataCenters.org, base data from
    [Compute Atlas](https://www.compute-atlas.com)), since [#958](https://github.com/getcommunityone/open-navigator/issues/958):
    about 2,300 US data centers with city, county, approximate coordinates and the registry's own status. Its crypto
    mines are left out. It gives no primary source per record, only a source count, so these rows are registry records,
    credited as such.
- **One site, one row.** A registry record joins an Epoch site only when, in the same state, their names are equal once
  normalised ("Google Cedar Rapids Data Center Campus" = "Google Cedar Rapids") and the pairing is one-to-one. Anything
  else is its own site; a close-but-unequal name never merges. In a trial, a looser rule paired "Google New Albany" with
  fifteen different New Albany facilities. `data_center_site_source` keeps every source record of a site, with its own
  URL.
- **Status:**
  - Epoch: worked out from its dated rows (planned, under construction, or operating).
  - Registry: its own word, mapped (operational → operating; proposed and permitted → planned; cancelled →
    **cancelled**), with the word kept in `source_status`. "Cancelled" appears only where the registry publishes it.
- **A site its source stops listing stays visible** as "No longer listed by the source", with its last-seen date and
  last known status.
- **Matching by name stays on Epoch sites for now.** Projects, agenda items, meeting mentions and the governments near a
  site read `source = 'epoch'` only, so 2,300 more names can't produce false matches or fan out decisions. Widening
  them is [#979](https://github.com/getcommunityone/open-navigator/issues/979).

First load (25 Nov 2026):
- Registry: 2,535 records, of which 2,307 are data centers. 24 joined an Epoch site and 2,283 became their own sites.
- `data_center_site`: 2,379 sites. Epoch has 76 operating and 20 under construction. The registry adds 1,086
  operating, 254 under construction, 796 planned and 147 cancelled.
- Every downstream count that reads sites was unchanged by the import.

<details>
<summary>Where each piece lives</summary>

| Step | Where | What it does |
|---|---|---|
| Load | `.venv/bin/python -m ingestion.data_centers.epoch_sites [--no-download] [--file-dir DIR] [--dry-run] [--dsn URL]` | Writes to the local warehouse unless `--dsn` says otherwise; Neon URLs in the environment are ignored (#441). Downloads `data_centers.csv` and `data_center_timelines.csv` to `data/cache/epoch/` and lands each row as JSONB in bronze. Stops with the headers it found if Epoch renames `Name`, `Data center` or `Date` |
| Bronze | `bronze.bronze_epoch_data_centers`, `bronze.bronze_epoch_data_center_timelines` | One row per CSV row per downloaded file. PK `(file_sha256, row_number)`, so reloading the same file adds nothing |
| Staging | `stg_epoch_data_center`, `stg_epoch_data_center_timeline` | Latest record per site, with first/last seen and `is_listed`; dated rows typed with guarded casts |
| Mart | `data_center_site` (public) | One row per site. PK `data_center_site_id`. Status, last known status, power, source and licence |
| API | `GET /api/data-centers/sites?state=&status=&limit=` | The state's sites and counts by status. `city_applied` is always false |
| Page | `/data-centers?state=&city=`, "Sites" | Status in plain words. Dropped sites are dashed and labeled. With a city filter, the page says the list covers the whole state |

</details>

<details>
<summary>How status is worked out</summary>

Epoch's timeline file has one row per site per date, with free-text construction status, buildings operational and
IT power. For each site:

1. The latest row on or before today has buildings operational → **operating**. If that count is blank but the row
   reports IT power above zero, it also counts as operating.
2. A row on or before today, but nothing operational → **under construction**.
3. Only future-dated rows → **planned**.
4. No dated rows → no status ("Status not published").

If the newest download doesn't list the site, the status becomes **no longer listed**, and the result above is kept as
`last_known_status`.

</details>

<details>
<summary>Decisions and why</summary>

- **Epoch AI, not the Brockovich map.** The map's built and under-construction layers come from open data like
  Epoch's, but its proposed and community-reported entries are its own, mostly from residents. Its terms require
  written permission and forbid scraping, so those stay out until the project agrees.
- **State from the address.** Epoch gives a street address, not a jurisdiction. A US address ending in a state code or
  state name gives `state_code`; anything else stays null rather than guessed. There is no city field, so a city
  filter can't narrow sites, and the page says so instead of showing a city label over state data.
- **Old snapshots are kept** in bronze. That's how a site that leaves Epoch's list is noticed and kept.
- **Confidence tags become words.** Epoch marks names `#likely` or `#speculative`; the page shows "(likely)" and
  "(speculative)" so a guess never reads as fact.
- **Proposed sites before the vote** will come from meeting records (agenda items on data center rezonings), which is
  [DC-4.2](https://github.com/getcommunityone/open-navigator/issues/250).

</details>
