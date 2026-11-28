---
title: Topic place rankings - where towns stand on a contested question
description: How topic_place_ranking turns public speakers' own sides into a per-place lean on a topic - counting each speaker once, the evidence minimum, shrinkage toward the national rate, size bands, officials kept apart - and what the API and the Where towns stand page serve.
---

# Topic place rankings

Issue: [#1437](https://github.com/getcommunityone/open-navigator/issues/1437). Decided 2026-11-28. Builds on the
speaker stance classifier ([#1391](speaker-stance-classifier.md)), which reads each public speaker's own side on a
topic from their words at a meeting. The page is [#1438](https://github.com/getcommunityone/open-navigator/issues/1438).

The owner asked for a gauge that shows, per contested local question, which places lean against and which lean for.
Everything here is built from our own recorded meetings, speakers and classifier readings, in our own words. A
company with a similar public page is listed in the citations as reference-only: none of its data, numbers, wording or
layout is used.

## What a row is

`gold.topic_place_ranking`: one row per **place x topic x window** (PK `jurisdiction_id, topic_id, window_months`;
FKs to `jurisdictions` and `civicsearch_topic`). `public.topic_place_ranking` serves it unchanged: it holds counts per
place and no names.

## Counting

- **Only confident sides count.** A reading counts only when `meeting_speaker_topic_side.side` is `for` or `against`,
  which already means the classifier was at least 0.8 sure. Concerns-only, no-side and not-sure readings are left out,
  and so are off-topic mentions, which never reach the mart.
- **Each speaker counts once per place and topic.** A speaker's readings across the window's meetings collapse to
  their majority side. A speaker evenly split between for and against takes no side (`speakers_split`). One regular
  commenter therefore cannot outweigh a room of first-time speakers.
- **How a speaker is recognised across meetings.** Only inside one place, and only by the name the site already shows
  (residents as "First L."). An unnamed speaker ("Speaker N") cannot be recognised, so counts once per meeting. Two
  residents with the same "First L." in one place merge into one, which undercounts and never overcounts. The key
  exists only inside the model and is never stored or served.
- **Window.** The last `ranking_window_months` = 24 months, up to `ranking_as_of` (empty = the run date).
- **Not counted:** possible minors, every school-district place (school-board residents are never read, AGENTS.md),
  and readings with no place.

## Evidence minimum

A place is **ranked** only with at least **10 distinct sided speakers** across at least **2 meetings** in the window
(`ranking_min_speakers`, `ranking_min_meetings`). Below that it is still listed, as unranked, and the page draws it
as a light dot. A single heated hearing cannot rank a town on its own.

## Score and shrinkage

- `against_share = speakers_against / (speakers_for + speakers_against)`.
- `national_against_share`: the topic's against share over every place's sided speakers in the window.
- `shrunk_against_share = (speakers_against + k * national) / (speakers_for + speakers_against + k)`, with
  **k = 10 pseudo-speakers** (`ranking_prior_weight`). A place with 10 speakers sits halfway between its own share and
  the national rate. One with 100 sits within about a tenth of its own share. This is the usual beta-binomial prior,
  written as pseudo-counts: it stops a small place's 10-for-0 from looking more certain than a large place's 80-for-20.
- A ranked place **leans against** when its shrunk share is above 0.5 and **leans for** when it is below. Exactly 0.5
  is neither.

## Size bands and rank

Places are compared only with places of similar size, by Census ACS population (`jurisdictions.population`):
**large** ≥ 250,000, **mid** 50,000-249,999, **small** < 50,000, and **unknown** where we have no population (most
towns). `band_rank` 1 is the most against among ranked places in the band. Ties are broken by more speakers.

## Officials

Officials are never added to residents' counts. An officials' side (`officials_for`, `officials_against`,
`officials_side`) comes only from speakers matched to an official roster (`attribution_method =
'official_roster_match'`). An unconfirmed speaker is never treated as an official. The classifier reads only the
public-comment period today, and only 4 speakers are roster-confirmed, so this marker is almost always empty. Reading
roster-confirmed officials' own words is follow-up work, not something we infer.

## API

- `GET /api/rankings/topics`: per topic, places ranked and unranked, ranked places leaning against and for, the
  national against share, and the median shrunk share of ranked places.
- `GET /api/rankings?topic=<slug|id>&band=&state=`: that topic's places in scope (ranked first, by band and rank),
  with a `national` summary of the same scope.

Shares are fractions 0-1. Nothing is defaulted: an empty scope returns no places and null shares.

## What this is not

It is not a poll or a survey. People who speak at public meetings are not a sample of residents: they are often
people with a stake in the outcome. The rankings describe what was said at the meetings we hold recordings for, and
only those places: a place we have no meetings for has no dot at all, and that says nothing about its residents.

## National results (2026-11-28 build)

The 14 released topics (the 13 initial validated topics plus `battery-storage` from #1486 / #1401), over the 24 months
to 2026-11-28. Speakers are distinct people per place: a person who spoke in two places counts in each. "Lean" counts
only ranked places. "Median" is the median shrunk against-share of ranked places. No place has a roster-confirmed
officials' side yet.

| topic | places | ranked | lean against | lean for | speakers for | speakers against | national against | median |
|---|---|---|---|---|---|---|---|---|
| data-centers | 118 | 23 | 23 | 0 | 125 | 1,015 | 0.890 | 0.913 |
| surveillance-cameras | 94 | 10 | 10 | 0 | 65 | 421 | 0.866 | 0.868 |
| affordable-housing | 98 | 8 | 0 | 8 | 335 | 22 | 0.062 | 0.042 |
| short-term-rentals | 62 | 6 | 0 | 6 | 160 | 105 | 0.396 | 0.315 |
| homelessness-and-shelters | 76 | 5 | 0 | 5 | 271 | 9 | 0.032 | 0.014 |
| license-plate-readers | 62 | 4 | 4 | 0 | 37 | 234 | 0.864 | 0.864 |
| police-staffing | 24 | 3 | 3 | 0 | 4 | 110 | 0.965 | 0.991 |
| guns | 15 | 2 | 0 | 2 | 52 | 8 | 0.133 | 0.098 |
| immigration-and-sanctuary | 38 | 1 | 0 | 1 | 70 | 10 | 0.125 | 0.062 |
| alcohol-licensing | 36 | 1 | 0 | 1 | 47 | 23 | 0.329 | 0.262 |
| pickleball | 34 | 1 | 1 | 0 | 65 | 38 | 0.369 | 0.604 |
| water-fluoridation | 11 | 1 | 0 | 1 | 34 | 19 | 0.358 | 0.226 |
| battery-storage | 9 | 1 | 1 | 0 | 8 | 24 | 0.750 | 0.643 |
| renewable-energy | 28 | 0 | 0 | 0 | 30 | 33 | 0.524 | - |

705 place-topic rows in all, 66 of them ranked (large 29, mid 20, small 15, unknown 2). Most places with readings sit
below the evidence minimum, so the page shows them as light dots.

## Tests

- dbt unit test `topic_place_ranking_counts_once_shrinks_and_bands` (`_schema_topic_place_ranking.yml`) covers: a
  speaker counted once across three meetings, a split speaker taking no side, not-sure, concerns-only, minor and
  out-of-window readings left out, a roster-confirmed official kept apart, a school district left out, the 10/2
  minimum, shrinkage to 7/19 national, and size bands.
- `tests/test_topic_place_ranking_dbt.py` checks that spec against this page's numbers and runs it with
  `RUN_DBT_UNIT_TESTS=1`. `tests/test_api_rankings.py` covers the API.
