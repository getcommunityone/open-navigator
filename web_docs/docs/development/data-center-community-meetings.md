---
sidebar_position: 37
title: Company-hosted data center meetings
description: How Open Navigator finds town halls and open houses that data center companies hold, from news and company press releases (#532).
---

# Company-hosted data center meetings

[#532](https://github.com/getcommunityone/open-navigator/issues/532) finds the town halls, open houses and
information sessions that data center developers hold about their projects. They aren't government records,
so no meeting crawl finds them; local news and the companies' own press releases do. Part of epic
[#530](https://github.com/getcommunityone/open-navigator/issues/530).

## Pipeline

1. `python -m ingestion.data_centers.community_events` lands items in `bronze.bronze_data_center_news_item`
   (URL, title, publisher, date, verbatim snippet) from:
   - the **GDELT DOC 2.0 API**: one query per meeting word (`"data center" "town hall"`, ...) and one per
     curated project name; at most one request every 6 seconds, backing off on HTTP 429;
   - **Google News RSS**, only when `news.google.com/robots.txt` allows the feed path for our User-Agent
     (it doesn't today, so the source is skipped and the run says so);
   - the **press-release feeds** in `mdm_organization_data_center.press_feed_url`. A release that names a
     meeting word, "data center" or one of the company's projects has its page read, and only whole sentences
     from the page's `<article>` that say a meeting word or a project name are kept.
2. dbt: `stg_data_center_news_item` → `int_data_center_news_item__match` (host company, project, government,
   meeting kind, stated date, video link; no LLM) → `data_center_community_event` (one row per event,
   deduplicated across articles) and `data_center_community_event_source` (every article, verbatim).
3. `python -m ingestion.data_centers.recording_candidates` searches YouTube for confirmed events with a date and
   a place, through the VPN guard (`scrapers.youtube.vpn_guard.require_vpn`); results land as candidates in
   `data_center_community_event_recording`, never attached to the event.
4. `GET /api/data-centers/community-events?state=&city=&project_id=` and `GET /api/data-centers/projects` feed the
   "Company meetings" and "Projects" sections of `/data-centers`.

## Decisions

- **Hosted by a company, never a government meeting.** Every event has `host_type = 'company'` and the page
  labels each card "company meeting, not a government meeting".
- **Confirmed or unconfirmed.** An item is an event only when its own text says "data center", names a meeting
  word, names the host company and resolves a tracked project. One that misses the host or project stays
  `unconfirmed`: kept for review, counted on the page, not shown as an event.
- **Dates only as stated.** `event_date` comes from the text after the first meeting word, in the same sentence
  ("town hall ... October 7, 2026"; or "Oct. 7" with the year of publication, `event_date_basis =
  'stated_month_day'`). A press release's dateline or an earlier date is never the meeting date, and an impossible
  date ("February 30") is dropped.
- **Polite fetching.** A descriptive User-Agent with no personal details, robots.txt checked per host, per-host
  spacing. americansentiment.com and prophecygov.com forbid competitors' use and are never fetched.
- **Timeline stages are read, not guessed.** On a project's timeline a decision is "Planning" or "Council vote"
  only when its own text says so (zoning, rezoning, site plan; voted, approved, ordinance); otherwise it is a
  "Government meeting". An undated item is never given a date.
