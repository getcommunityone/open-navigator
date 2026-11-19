---
title: Tuscaloosa YouTube catalog gap (Jul–Oct 2026)
sidebar_label: Tuscaloosa catalog gap
---

# Tuscaloosa YouTube catalog gap (Jul–Oct 2026)

Issue: [#562](https://github.com/getcommunityone/open-navigator/issues/562).

## Cause

The City of Tuscaloosa channel (`UC74dczS0B3MhDhUHp2ZGRPA`) **did post** through July–October 2026. A live YouTube Data API listing of the uploads playlist for 2026-06-23 through 2026-11-15 returned **102** videos; **100** were missing from `bronze.bronze_event_youtube` on 2026-11-19. Month counts on YouTube included Jul 22, Aug 24, Sep 20, Oct 26.

The gap was **discovery not scanning this channel** during that window (not “the channel went quiet”). Other jurisdictions continued to receive transcripts in the same months.

## Fix path

1. Catalog backfill via Data API (no youtube.com HTML):  
   `python -m scrapers.youtube.backfill_channel_from_api --channel-id UC74dczS0B3MhDhUHp2ZGRPA ...`
2. Transcripts still need the VPN-guarded scraper path (`load_youtube_for_jurisdiction` with Surfshark up).
3. `channel_type` aliases (`municipality` / `unknown`) normalize to `municipal` at write time and via a one-shot bronze update.
4. dbt singular test `assert_government_channel_catalog_freshness_45d` flags government channels with no catalog video for 45+ days.
