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

A curated topic appears on the site after `dbt seed` and a build of `civicsearch_topic` and the models downstream of
it (`dbt ls --select civicsearch_topic+`), followed by the usual publish. Search's "Try searching for" suggestions are
data centers, short-term rentals, Flock cameras and license plate readers.

## What the page shows

| Situation | API | Browse Topics |
| --- | --- | --- |
| Topics load | `200` with the list | pills, "More topics", a working Topic filter |
| The query fails | `503 {"detail": "Topics are unavailable right now."}` | "Couldn't load topics"; the filter reads "Topics unavailable" |
| No topics for the scope | `200 []` | "No topics available for (place) yet", with a link to the national view; the filter reads "No topics available" |

Before issue #808 a failed query returned `200 []`, so a failure looked the same as an empty catalog and the page
showed nothing at all.

## Known gap (2026-11-24)

The live `GET /api/topics` returned `[]` with no scope, while `GET /api/topics/100001/meetings` returned 1,908
meetings. The catalog table or a table its query joins is therefore missing, empty or out of date in production. The
503 makes that visible; the cause still has to be read from the API log line `topics list failed`.
