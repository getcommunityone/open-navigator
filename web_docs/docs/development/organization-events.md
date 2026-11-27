---
title: Upcoming events of nonprofits
description: Where real upcoming events of the nonprofits tied to a topic can lawfully come from, what each option costs and allows, which one we built (the organization's own website, read politely), and how the events reach the Coming up screen (#1347).
---

# Upcoming events of nonprofits

**Issue:** [#1347](https://github.com/getcommunityone/open-navigator/issues/1347) · **Parent:**
[#1344](https://github.com/getcommunityone/open-navigator/issues/1344)

Owner, 27 Nov 2026: "We also need to better integrate nonprofits that are tied to topics and any upcoming events they
may have." The nonprofits come from [How organizations are tied to topics](topic-organizations.md). This page is about
their events. Rule zero is the site's: no made-up events. An event is shown only when a source we may read states its
title and date.

## What the warehouse had

- **No organization events.** `data_center_community_event` lists company-hosted data center town halls found in the
  news; none has a date and none is hosted by a nonprofit.
- **No nonprofit websites.** `mdm_organization.website` is empty for every nonprofit; the IRS Business Master File
  carries no website.

## The options

| Source | Finds events by | Access and cost | Terms on storing and showing | Verdict |
|---|---|---|---|---|
| **The organization's own website** (schema.org `Event` markup, an iCal feed) | The site, found from the 990 e-file's `WebsiteAddressTxt` | Free. Public pages; the 990 XML is a public object on the GivingTuesday data lake | The site's own; we honour robots.txt, identify as `open-navigator`, link back to the event page | **Built** |
| Eventbrite API | Organizer or venue id only. The public event search (`/events/search/`) was shut down on 12 Dec 2019 | Needs an account and a token | API terms page could not be read (403); not relied on | Not used: no discovery by place or by our organizations |
| Meetup API (GraphQL) | Groups | API access is a Meetup Pro feature (paid) | Meetup API License Terms, in addition to the ToS; page could not be read (403) | Not used: paid, terms unverified |
| Mobilize API | Organizations that use Mobilize; `GET /v1/organizations/:id/events` with zipcode and state filters | No key for public events; 15 GET requests a second | The README states no re-use terms or data license | Not used: covers mostly one side of most debates, and no stated terms |
| Facebook events | Pages | Login required | Automated collection forbidden | Never (AGENTS.md: no logins) |

Sources: eventbrite.com/platform/api (the "Search Events - deprecated" section), meetup.com/api/general,
github.com/mobilizeamerica/api, schema.org/Event. Read 27 Nov 2026.

## What we built

1. **Websites.** `python -m ingestion.org_events.websites` takes the nonprofits tied to a curated topic with the
   strongest evidence (named in a meeting, a mission or name naming the topic; `--max-rank 3`), reads `WebsiteAddressTxt`
   from each one's latest 990 e-file XML (anonymous HTTPS, the same objects `ingestion.givingtuesday.efile` reads), and
   lands `bronze.bronze_organization_website` (one row per EIN; re-checked after 180 days). Social profiles, donation
   platforms and "N/A" are not a website.
2. **Events.** `python -m ingestion.org_events.crawl` reads each site's home page and up to three same-site links that
   look like an events page or an iCal feed (`.ics`, `?ical=1`, `/events/`, `/calendar/`), plus a feed an events page
   links. Events come only from schema.org `Event` JSON-LD or iCalendar `VEVENT`s: a title and a start date are
   required, cancelled or postponed ones are dropped, a recurring rule is not expanded (only its stated first date is
   kept), and only events from today to about 13 months ahead are kept. They land in `bronze.bronze_organization_event`.
3. **Manners.** robots.txt is read first on every host (401/403/5xx or unreachable: stay out). The User-Agent says
   `open-navigator`. One request at a time per host, two seconds apart (or the site's `Crawl-delay`). A 403, a 429 or a
   bot check stops that host for the run; nothing retries it with another identity.
4. **dbt.** `stg_org_events__website`, `stg_org_events__event` → mart `organization_event` (PK `organization_event_id`,
   FK `master_org_id` → `mdm_organization`). `topic_upcoming` gains `match_basis = 'hosted_by_org'` rows (kind `event`)
   for future events of a topic's nonprofits tied by a meeting, mission or name, with the host's evidence as
   `matched_text`. The Coming up screen and the home strip label them "Hosted by &lt;org&gt;".

## How many (first run, 27 Nov 2026)

Run for the three test states (Georgia, Virginia, Alabama), nonprofits tied by a meeting, mission or name:

| Step | Count |
|---|---:|
| Nonprofits looked up in their latest 990 e-file | 877 |
| With a website | 449 |
| Sites read (home page plus up to three event links) | 449, 1,123 requests |
| Robots.txt says no | 85 |
| Blocked us (403/429 or a bot check), host left alone | 55 |
| Unreachable or malformed | 5 |
| No event markup or feed | 288 |
| **Sites with upcoming events** | **16** |
| Upcoming events read | 162 |
| **Upcoming events** (`organization_event`, the same event from JSON-LD and iCal kept once) | **157** |

In `topic_upcoming` as `hosted_by_org`: animal shelters 113 (Virginia 76, Georgia 36, Alabama 1), homelessness and
shelters 36 (Virginia 34, Georgia 2), domestic violence 3 (Georgia), traffic safety 5 (Virginia). **None for water
fluoridation in Georgia, data centers in Virginia or guns in Alabama**: none of those nonprofits with a website publishes
event markup or a feed. The four topics with events are the crime and safety topics of #1128, so on `main` they show once
those topics are merged. Most events come from WordPress sites running The Events Calendar (iCal feed and JSON-LD).

## Limits and next steps

- Coverage is low by nature: a small nonprofit rarely publishes structured events. A text page listing events is not
  read (that would be guessing dates from prose).
- Hosts are found from the 990 e-file, so organizations that file the 990-N postcard or a paper return have no website
  here.
- The host's name is the organization master's name for its EIN, which for a chapter under a group exemption can be the
  parent's name.
- Runs are manual for now; a weekly refresh and other states are [#1376](https://github.com/getcommunityone/open-navigator/issues/1376).
