---
title: Browse Topics catalog and its empty states
sidebar_label: Browse Topics catalog
description: Where the Browse Topics catalog comes from, the curated default topics, and what the page shows when the catalog is empty or cannot be loaded.
---

# Browse Topics catalog and its empty states

Browse Topics (`/browse-topics`) and the **Topic** filter read one list: `GET /api/topics`, which serves
`public.civicsearch_topic`. That table is the CivicSearch taxonomy plus the hand-curated topics in the
`curated_topics` seed (`topic_id` from 100000 up).

## Curated default topics

| Topic | `query_id` | Matches transcripts that say |
| --- | --- | --- |
| Data centers | `data-centers` | data center, data centre, hyperscale, server farm |
| Water fluoridation | `water-fluoridation` | fluoridation, fluoride |
| Short-term rentals | `short-term-rentals` | short-term rental, vacation rental, Airbnb, Vrbo |
| Flock and license plate readers | `license-plate-readers` | license plate reader, license plate camera, Flock Safety, Flock camera, ALPR |
| Guns | `guns` | firearm(s), gun violence, gun show, shooting range, gun range, gunshot(s), gunfire, ShotSpotter, concealed carry, ghost gun, assault weapon, gun store or shop, gun safety, gun owners ([#1051](https://github.com/getcommunityone/open-navigator/issues/1051)) |
| Pickleball | `pickleball` | pickleball, pickle ball, pickleball court(s), pickleball players ([#1054](https://github.com/getcommunityone/open-navigator/issues/1054)) |

A curated topic appears on the site after `dbt seed` and a build of `civicsearch_topic` and the models downstream of
it (`dbt ls --select civicsearch_topic+`), followed by the usual publish. Search's "Try searching for" suggestions are
data centers, short-term rentals, Flock cameras and license plate readers.

Guns uses only phrases, never the bare word "gun", so "nail gun", "radar gun" and "begun" don't tag a meeting. One
phrase is enough to tag a meeting, as for every curated topic. Some tags are incidental: a "firearms instructor" named
while a new officer is introduced, for example. The quoted passage on each result shows which kind it is. The first
local build tagged 7,684 transcripts in 50 states. On the home page, Guns is a **Coming soon** card, like Flock, and so is Pickleball.

Two guide topics are also on the strip as **Coming soon**: **Starting a nonprofit** ([#1078](https://github.com/getcommunityone/open-navigator/issues/1078)) and **Insurance shopping** ([#1079](https://github.com/getcommunityone/open-navigator/issues/1079)). They aren't meeting topics, so they have no keywords, counts or companies until their guide or data lands.

## What the page shows

| Situation | API | Browse Topics |
| --- | --- | --- |
| Topics load | `200` with the list | pills, "More topics", a working Topic filter |
| The query fails | `503 {"detail": "Topics are unavailable right now."}` | "Couldn't load topics"; the filter reads "Topics unavailable" |
| No topics for the scope | `200 []` | "No topics available for (place) yet", with a link to the national view; the filter reads "No topics available" |

A topic's meeting list (`GET /api/topics/{topic_id}/meetings`) follows the same rule since #816: a failed query is a
`503`, shown as "Couldn't load meetings for this topic", and never as a topic with zero meetings.

Before issue #808 a failed query returned `200 []`, so a failure looked the same as an empty catalog and the page
showed nothing at all.

## Known gap (2026-11-24)

The live `GET /api/topics` returned `[]` with no scope, while `GET /api/topics/100001/meetings` returned 1,908
meetings. The catalog table or a table its query joins is therefore missing, empty or out of date in production. The
503 makes that visible; the cause still has to be read from the API log line `topics list failed`.
