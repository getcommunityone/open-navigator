---
sidebar_position: 7
title: Data freshness checks
description: Which tables Open Navigator checks for staleness, the limits, and how to run the checks.
---

# Data freshness checks

A table that stops updating looks the same as a fresh one until someone checks the dates. In November 2026, transcript
search had not been rebuilt since June, the verified channel list since May, and the homepage scrape had saved no video
links at all, and nothing reported any of it. These checks make staleness visible. They follow principle 5 of
[Context engineering](./context-engineering.md).

## In short

- **Raw and runtime tables** are checked with `dbt source freshness`, from the timestamp each load writes.
- **Tables the site and models read** have `dbt_utils.recency` tests tagged `freshness`.
- **A coverage test** fails when the homepage scrape finds YouTube links on fewer than 5% of city sites.
- The model tests are warnings, so a stale table never stops `dbt build` or blocks unrelated models. The nightly run
  reports them by name (`.claude/commands/nightly-crawl.md`, step 4).

```bash
cd dbt_project
.venv_dbt/bin/dbt source freshness            # raw and runtime tables
.venv_dbt/bin/dbt test --select tag:freshness # served tables and coverage
```

<details>
<summary>What's checked, and the limits</summary>

| Table | Timestamp | Warn after | Fail after |
|---|---|---|---|
| `bronze.bronze_event_youtube` (YouTube catalog) | `last_updated` | 2 days | 7 days |
| `bronze.bronze_event_youtube_transcript` | `last_updated` | 2 days | 7 days |
| `bronze.bronze_events_analysis_ai` | `updated_at` | 7 days | 30 days |
| `bronze.bronze_epoch_data_centers` | `loaded_at` | 8 days | 31 days |
| `intermediate.int_events_channels` (verified channels, written by scripts) | `loaded_at` | 30 days | 90 days |
| `public.event_documents` (transcript search) | newest `created_at` | 7 days | — |
| `public.event_meeting`, `public.event_decision` | newest `extracted_at` | 14 days | — |
| `public.recent_transcribed_meeting` (homepage "What's New") | newest `meeting_date` | 14 days | — |
| `public.jurisdiction_state_aggregate` (stats) | `last_updated` | 7 days | — |
| `public.data_center_site` | newest `last_seen_on` | 14 days | — |
| City homepage scrape coverage (`tests/assert_homepage_scrape_found_links.sql`) | share with a YouTube link | under 5% | — |

The limits match how often each feed should change: the YouTube crawl runs nightly, analysis runs less often because
it's billed, Epoch publishes about weekly, and channels are rediscovered occasionally.

</details>

<details>
<summary>Decisions and why</summary>

- **dbt, not a separate script.** Source freshness and tests are dbt's own tools, run the same way as the rest of the
  pipeline, and they show up in dbt's docs.
- **Warnings for served tables.** In `dbt build`, a failing error-level test skips everything downstream. One stale
  table shouldn't stop fresh data elsewhere from building or publishing.
- **`last_updated` for the YouTube catalog.** The loader doesn't set `loaded_at` on new rows (it hasn't changed since
  June 7, 2026, while 8,494 rows were updated in two days), so `last_updated` is the column that reflects new data.
- **Coverage, not just dates.** The broken homepage scrape kept writing rows with fresh timestamps; only the share of
  rows with links showed it had found nothing.

</details>

<details>
<summary>First run, November 16, 2026</summary>

- Stale: `int_events_channels` (last loaded May 27), `event_documents` (no new transcript since June), `event_meeting`
  and `event_decision` (no new analysis in 14 days).
- Fresh: the YouTube catalog and transcripts, analyses table, Epoch load, stats rollup and data center sites.
- Coverage passed, after the homepage rescan found links on about 23% of city sites. Before it, the share was 0%.

</details>
