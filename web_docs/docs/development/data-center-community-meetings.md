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
     from the page's `<article>` that say a meeting word or a project name are kept;
   - **local news RSS/Atom feeds** (#549, `--source rss`) listed in the seed `local_news_feeds.csv`: outlet,
     state, feed URL, and the date and result of its robots.txt check. Only enabled feeds whose robots.txt
     allowed the feed path are read, and robots.txt is checked again live. A `{term}` feed URL is an outlet's own
     topic feed (`https://abc3340.com/topic/{term}.rss`), expanded per tracked company name and project place;
     topic feeds reach back months, where a section feed holds only the last few weeks. An item is kept when its
     title or summary says "data center" or names a tracked project; its article page is read (robots-checked,
     at most `--max-pages` per feed) and only whole sentences that say a meeting word, "data center", a tracked
     name or a project's place are kept. Refresh the robots columns with
     `python -m ingestion.data_centers.news_feeds --check-robots`;
   - **optional keyed APIs** (#549): NewsAPI.org (`NEWSAPI_KEY`), The Guardian Open Platform
     (`GUARDIAN_API_KEY`) and the Brave Search API (`BRAVE_SEARCH_API_KEY`, for announcement pages on city,
     county and company sites). Each is skipped quietly when its key is unset; keys are never printed and are
     scrubbed from any logged error. No search engine's result pages are scraped.
   GDELT is opt-in (`--source gdelt`): it answered only HTTP 429 for hours (#542).
2. `python -m ingestion.data_centers.video_search` (#549) searches the **YouTube Data API** (`search.list`, the
   `YOUTUBE_API_KEY` channel discovery uses) for every tracked project and company: `"<project>" town hall`,
   `"<company>" community meeting <city or county> <state>`, `"<company>" data center <city>`, since the project
   was announced or the last 18 months. Hits land in the same bronze table (source `youtube_search`) with video
   URL, channel, title, date, full description and the query. At most `--budget` searches (80, i.e. 8,000 of the
   10,000 free daily units) per Pacific quota day, logged in `bronze.bronze_data_center_video_search_log`; a
   query searched within `--refresh-days` is skipped, so the run resumes across days. `--fetch-captions` hands
   confirmed meeting recordings to the existing caption client (VPN guard, cookies) and
   `upsert_bronze_transcript`, into `bronze.bronze_event_youtube_transcript`.
3. dbt: `stg_data_center_news_item` → `int_data_center_news_item__match` (host company, project, government,
   meeting kind, stated date, video link; no LLM) → `data_center_community_event` (one row per event,
   deduplicated across articles) and `data_center_community_event_source` (every article, verbatim).
4. `python -m ingestion.data_centers.recording_candidates` searches YouTube for confirmed events with a date and
   a place, through the VPN guard (`scrapers.youtube.vpn_guard.require_vpn`); results land as candidates in
   `data_center_community_event_recording`, never attached to the event.
5. `GET /api/data-centers/community-events?state=&city=&project_id=` and `GET /api/data-centers/projects` feed the
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
  spacing. americansentiment.com and prophecygov.com forbid competitors' use and are never fetched
  ([Proprietary competitors](../data-sources/citations.md#proprietary-competitors)).
- **Timeline stages are read, not guessed.** On a project's timeline a decision is "Planning" or "Council vote"
  only when its own text says so (zoning, rezoning, site plan; voted, approved, ordinance); otherwise it is a
  "Government meeting". An undated item is never given a date.
- **Local feeds, not a search engine (#549).** Google News RSS is disallowed by its robots.txt, and search engines'
  result pages are never scraped. A feed that answers HTTP 429 or puts robots.txt behind a bot challenge is
  recorded in the seed as not allowed or disabled, with the reason, and is not retried around the block.
- **A video is coverage or the meeting (#549).** A YouTube video from a TV or radio news channel (a call sign such
  as WBRC, a network name, or "News" in the channel name) is `source_role = 'news_coverage'`: it reports the
  meeting and is listed as a source, never as its recording. Any other video that itself names the host, the
  project and a meeting word is `recording` and becomes the event's `recording_url`. A video's meeting word must
  be in its title: descriptions of news roundups mention "town halls" in passing. "Townhall" counts as "town hall".
