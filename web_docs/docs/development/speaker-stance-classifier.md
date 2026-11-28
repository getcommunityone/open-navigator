---
title: Speaker stance classifier - topics, positions, validation and run order
description: Which topics a classifier reads each public speaker's own side and heat on, how for and against are defined, how the hand-labelled gold set gated each topic, the run order, and what is served.
---

# Speaker stance classifier

Issue: [#1391](https://github.com/getcommunityone/open-navigator/issues/1391). Decided 2026-11-27. Builds on
[Mixed comments: speakers, stance shapes, attribution and heat](mixed-comments-speakers-and-stance-shapes.md) (#1386),
which left most public speakers `unclear` (40,961 of 76,592) or `concerns_only` (22,332) because captions rarely say
"I support" or "I oppose".

## What runs

`python -m llm.typesafe.speaker_stance` asks TypeSafe Jev, once per (public speaker, topic), two things about the
passages of that speaker's **own** turn text that name the topic (`build_state`: 700 characters each side of every
keyword hit, merged, at most 2,800 characters, `speaker_state/1`):

- `side` (Choice): `for` / `against` the topic's concrete local action, `concerns_only`, `no_position`, `off_topic`;
- heat: four yes/no thresholds (`heat_2` .. `heat_5`); heat is 1 plus the consecutive thresholds judged true.

A speaker is read only for the topics their own words match: the curated topic's seed keywords (the phrases behind
`meeting_comment.topic_ids`), or the reframed topic's own whole-word phrases. Possible minors and every speaker at a
school-board meeting are never sent. Jev returns probabilities, never text, and rows are keyed by `meeting_speaker_id`
(a hash; never linked across meetings), so nothing here names anyone.

Readings land in `bronze.bronze_speaker_topic_stance_jev` (PK speaker, topic, `question_version`) as each answer
arrives. A rerun skips everything already read at the topic's current question version and pays nothing twice; a 401,
402 or 403 stops the run at once with a progress summary (`--summary-json`), so a top-up resumes with the same command.

## Topics

The candidates were the original curated stories (100001-100020) and the most-discussed or fastest-rising CivicSearch
topics on the year-over-year list (`/api/topics/yoy`, 2025 against Jan-Nov 2026). A topic was kept only where a
resident can be for or against a concrete local decision.

### Chosen (19 defined)

| topic | id | "for" means | source |
|---|---|---|---|
| data-centers | 100001 | approving / building a data center | curated |
| water-fluoridation | 100002 | keeping or adding fluoride | curated |
| short-term-rentals | 100003 | allowing short-term rentals | curated (meeting-level TopicDef) |
| license-plate-readers | 100004 | buying, keeping or expanding the cameras | curated (meeting-level TopicDef) |
| guns | 100005 | a local gun limit (against = gun rights) | curated (meeting-level TopicDef) |
| pickleball | 100006 | building or keeping courts / play | curated (meeting-level TopicDef) |
| traffic-safety | 100010 | speed humps, lower limits, cameras, crosswalks | curated |
| police-staffing | 100011 | more police funding, officers or pay | curated; absorbs "Police matters" (66) |
| parks-funding | 100016 | spending on parks and recreation | curated; absorbs "Parks and Recreation" (30) |
| homelessness-and-shelters | 100018 | shelters, services or housing for homeless people | curated; absorbs "Homelessness issues" (27) |
| immigration-and-sanctuary | 100019 | limiting local help to ICE (sanctuary); against = working with ICE | curated |
| bike-lanes | 100020 | building or keeping bike lanes / paths | curated; absorbs "Bicycle transportation" (57) |
| local-taxation | 74 | raising local taxes or fees | reframed from "Local taxation" |
| affordable-housing | 83 | approving or funding affordable housing | reframed |
| zoning-regulations | 77 | rezoning to allow denser housing | reframed from "Zoning regulations"; absorbs "Land use" (78) |
| renewable-energy | 90 | approving local solar / wind / battery projects | reframed from "Renewable energy" |
| surveillance-cameras | 28 | expanding city surveillance cameras | reframed (rising 2.66x) |
| public-transit | 55 | expanding or funding transit | reframed |
| alcohol-licensing | 14 | approving a liquor license or alcohol sales | reframed |

Data centers keeps its own definition (the meeting screen's question lives in `screen_transcripts`). Water
fluoridation's speaker question asks plain keep / end, not the meeting screen's five positions. The meeting-level
`TopicDef`s and their pinned hashes are untouched (`test_meeting_topic_hashes_unchanged`).

### Dropped, with reasons

- **No local position (generic buckets):** Property ownership (82), Education, schools, students (51), Budget
  discussions (121), Planning process (70), Debt management (96), Insurance discussions (21), Permit processes (68),
  Financial audit (79), Bidding process (49), Water management (110), Stormwater (109), Sewer infrastructure (97),
  Building setbacks (105), Fire department (22), Emergency Medical Services (23), Street lighting (47), Swimming pools
  (15), Signage regulations (54), Parking issues (29), Downtown development (56). Residents talk about these, but there
  is no single for/against decision their comments map to.
- **Merged into a curated topic:** Police matters, Parks and Recreation, Homelessness issues, Bicycle transportation,
  Gun violence (65, into guns), Drugs (18), Land use.
- **Curated, no position:** Violent crime (100007), Theft and break-ins (100008), Domestic violence (100013), Fire and
  EMS (100015), Animal shelters (100017): reports and concern, not a contested measure.
- **Curated, dropped for safety:** Drugs and overdoses (100009) mixes harm-reduction sites with health conditions
  (AGENTS.md, sensitive data); Youth crime (100012) and School safety (100014) are about minors and school boards.

## Positions in plain words

`web_app/src/utils/topicPositions.ts` has an entry per topic in everyday words ("Want more homes allowed" / "Against
denser zoning"; immigration names both sides: "Favor sanctuary limits" / "Favor working with ICE"), and
`speakerSideLabel()` says "Concerns only", "No side taken" or "Not sure" for the rest. A position says what was said;
it never infers a trait.

## Validation: hand labels, not another model's opinion

950 real public speakers, 50 per topic (30 random, then 20 whose passage holds a first-person stance cue, `CUE_RE`),
were labelled by hand from the exact passage Jev is sent, blind to any model output: one of the five sides, plus
`clear` when a for/against side is plain from the passage alone. The committed file
(`packages/llm/src/llm/typesafe/gold/speaker_stance_gold.json`) carries no speech: speaker hash, topic, label, the
passage's SHA-256 and a short reason with no name. `python -m llm.typesafe.speaker_stance_gold score` rebuilds each
passage, checks its hash and asks Jev; Jev's answers are committed beside it and `tests/test_speaker_stance.py`
recomputes every number below.

A topic proceeds only with **at least 8 clear items, clear accuracy >= 85%, no for/against swap, and >= 80% of the
sides it would serve (at the 0.8 floor) matching the hand label**.

| topic | items | clear | clear acc | swaps | served-side precision @0.8 | run |
|---|---|---|---|---|---|---|
| affordable-housing | 50 | 9 | 1.0 | 0 | 0.842 | yes |
| alcohol-licensing | 50 | 11 | 1.0 | 0 | 1.0 | yes |
| bike-lanes | 50 | 6 | 1.0 | 0 | 0.571 | held |
| data-centers | 50 | 32 | 1.0 | 0 | 0.97 | yes |
| guns | 50 | 8 | 1.0 | 0 | 0.9 | yes |
| homelessness-and-shelters | 50 | 9 | 1.0 | 0 | 0.846 | yes |
| immigration-and-sanctuary | 50 | 21 | 1.0 | 0 | 0.808 | yes |
| license-plate-readers | 50 | 27 | 1.0 | 0 | 1.0 | yes |
| local-taxation | 49 | 7 | 1.0 | 0 | 0.7 | held |
| parks-funding | 50 | 7 | 1.0 | 0 | 0.733 | held |
| pickleball | 50 | 12 | 0.917 | 0 | 0.938 | yes |
| police-staffing | 50 | 23 | 1.0 | 0 | 0.933 | yes |
| public-transit | 36 | 3 | 1.0 | 0 | 0.6 | held |
| renewable-energy | 50 | 10 | 1.0 | 0 | 0.909 | yes |
| short-term-rentals | 50 | 18 | 1.0 | 0 | 0.905 | yes |
| surveillance-cameras | 50 | 12 | 0.917 | 0 | 1.0 | yes |
| traffic-safety | 50 | 6 | 1.0 | 0 | 0.9 | held |
| water-fluoridation | 50 | 20 | 1.0 | 0 | 0.909 | yes |
| zoning-regulations | 50 | 5 | 1.0 | 0 | 0.857 | held |

Jev never swapped for and against on a clear case. The errors are the other way: on passages the labellers called
`off_topic` or `no_position` (often staff presenting, or a passing mention), Jev sometimes picks a side. The floor
answers that: across all topics, sides served at P >= 0.6 matched 79% of the time, at 0.7 84%, at **0.8 88%** (keeping
93% of the clear cases), at 0.9 92% (keeping 83%). The floor is 0.8 (`MIN_SIDE_CONFIDENCE`, dbt var
`speaker_side_min_confidence`); below it the mart says `not_sure`, which is never counted. `concerns_only` is weaker
(67% at 0.8 on 9 items) and is shown as its own label, never as a side.

Six topics are **held** (`HELD`; `--topic all` skips them, naming one still runs it): too few clear items to show
85%, or too many wrong sides served. More hand labels for them is follow-up work, not a re-run of anything paid.

The gold run cost 935 calls, 1,018,620 input tokens, **$0.0428**; about 1,090 input tokens per speaker-topic.

## Run order

Owner: "sort by the most trending topics with heat or different opinions". `python -m
llm.typesafe.speaker_stance_priority` (free) scores each topic as **normalized rise + normalized contention +
normalized heat**, equal weights, each min-max scaled 0-1 across the 19 topics:

- rise: 2026 share of recorded meetings over 2025 share (`topic_meeting_year`, the numbers behind `/api/topics/yoy`);
- contention: of the meetings where a public speaker named the topic, the share with one 'for' cue shape and another
  'against' one; averaged with the Jev per-meeting share where the public was split or officials sided against it,
  where `topic_meeting_lean` exists;
- heat: mean AI meeting-analysis heat (`gold.public_comment`) in those meetings; under 5 rated comments, the median.

Data centers goes first regardless. **Within a topic the hottest meetings go first** (owner: "We should prioritize
meetings with a lot of heat"), so if credits run out the most heated, contested meetings are already read. A free
pre-run estimate per meeting (`meeting_heat_scores`), four parts each scaled 0-1 and summed with equal weights:

- `ai_heat`: the AI meeting analysis's highest comment heat in the meeting (`gold.public_comment`, 1-5 to 0-1; 0 when
  none);
- `speakers`: public speakers at the meeting, ln(1 + n) / ln(1 + the largest meeting's n);
- `contested`: for that topic, `topic_meeting_lean` says both sides spoke (`mixed`) or officials sided against the
  public;
- `chair_cues`: the chair keeping order in the transcript (point of order, out of order, your time is up, please
  address the board, recess), ln(1 + n) / ln(1 + the 99th percentile), capped at 1.

2026 meetings break ties, then newest first.

| # | topic | meetings | rise | contention | rated comments | heat | score |
|---|---|---|---|---|---|---|---|
| 1 | data-centers | 670 | 5.56 | 0.07 | 28 | 2.54 | 2.095 |
| 2 | license-plate-readers | 329 | 3.37 | 0.10 | 61 | 2.41 | 1.748 |
| 3 | short-term-rentals | 1,309 | 1.55 | 0.15 | 92 | 2.08 | 1.513 |
| 4 | immigration-and-sanctuary | 163 | 1.85 | 0.02 | 30 | 3.07 | 1.297 |
| 5 | police-staffing | 281 | 1.53 | 0.03 | 13 | 3.00 | 1.257 |
| 6 | guns | 1,959 | 1.36 | 0.11 | 59 | 2.20 | 1.251 |
| 7 | surveillance-cameras | 1,322 | 2.66 | 0.02 | 97 | 2.41 | 1.074 |
| 8 | zoning-regulations | 3,128 | 1.93 | 0.04 | 146 | 2.35 | 1.017 |
| 9 | homelessness-and-shelters | 1,701 | 1.29 | 0.04 | 101 | 2.55 | 0.994 |
| 10 | affordable-housing | 1,666 | 1.40 | 0.04 | 47 | 2.36 | 0.878 |
| 11 | pickleball | 962 | 1.16 | 0.06 | 9 | 2.22 | 0.857 |
| 12 | water-fluoridation | 168 | 0.80 | 0.05 | 0 | (median) | 0.798 |
| 13 | alcohol-licensing | 680 | 1.29 | 0.03 | 4 | (median) | 0.760 |
| 14 | bike-lanes | 676 | 1.59 | 0.01 | 12 | 2.33 | 0.742 |
| 15 | traffic-safety | 1,008 | 1.45 | 0.01 | 46 | 2.35 | 0.704 |
| 16 | local-taxation | 2,490 | 1.15 | 0.02 | 79 | 2.14 | 0.583 |
| 17 | renewable-energy | 363 | 1.70 | 0.02 | 10 | 2.00 | 0.580 |
| 18 | public-transit | 1,402 | 0.87 | 0.02 | 43 | 1.77 | 0.245 |
| 19 | parks-funding | 732 | 1.32 | 0.01 | 19 | 1.53 | 0.109 |

## What is served

- `gold.meeting_speaker_topic_side`: one row per meeting x public speaker x topic; `side` (`not_sure` under the floor,
  `off_topic` dropped), `side_confidence`, `side_method = 'classifier'`, `side_version = jev:<question_version>`,
  `heat` (served at `heat_confidence >= 0.65`), PK (speaker, topic), FKs to `meeting_speaker_position`,
  `civicsearch_topic` and `jurisdictions`. Public serves a slim projection without the `not_sure` rows.
- `meeting_speaker_position.heat`: the AI meeting analysis's rating is kept where it exists; otherwise the classifier's
  heat (mean over the speaker's topics), `heat_method = 'classifier'`, its mean margin as confidence, version
  `jev:<question_version>`.
- `/api/topics/{topic}/caption-facts` returns `classifier_speakers` (for, against, concerns only, no position,
  meetings), a separate source labelled "speakers' own words, classifier", never added to the hand-counted speakers.
  The data-center Positions summary shows it as its own line.

## Budget

The owner authorised up to $40, then capped it at the prepaid balance: $25 funded on 2026-11-26, less $5.9485 of Jev
spend since (`python -m llm.usage.report --since 2026-11-26`), minus a $1 margin. The run's own `--max-usd` stops it
at the cap. Results and exact cost are in the issue and PR.

## Results of the 2026-11-27 run

All 13 validated topics were read: 18,878 speaker-topics (plus 6 from the skip-logic check), 21,291,040 input tokens,
**$0.8942**; with the gold run ($0.0428) the task spent **$0.9370** of the $18.0 cap. Container restarts stopped the run
twice; each restart's job build counted the rows already read as done, so nothing was paid for twice.

| topic | read | on topic | for @0.8 | against @0.8 | concerns only | no side | not sure |
|---|---|---|---|---|---|---|---|
| homelessness-and-shelters | 2,974 | 1,624 | 667 | 49 | 7 | 52 | 849 |
| affordable-housing | 2,685 | 2,152 | 990 | 74 | 18 | 56 | 1,014 |
| guns | 2,440 | 649 | 153 | 117 | 4 | 4 | 371 |
| data-centers | 2,430 | 2,214 | 152 | 1,119 | 179 | 58 | 706 |
| short-term-rentals | 2,095 | 1,879 | 485 | 332 | 36 | 77 | 949 |
| surveillance-cameras | 2,054 | 1,109 | 151 | 463 | 13 | 12 | 470 |
| pickleball | 1,269 | 876 | 256 | 61 | 20 | 62 | 477 |
| alcohol-licensing | 903 | 700 | 135 | 64 | 25 | 42 | 434 |
| license-plate-readers | 590 | 577 | 82 | 250 | 8 | 14 | 223 |
| renewable-energy | 487 | 285 | 49 | 56 | 18 | 14 | 148 |
| police-staffing | 409 | 331 | 33 | 177 | 7 | 6 | 108 |
| immigration-and-sanctuary | 295 | 199 | 95 | 32 | 0 | 0 | 72 |
| water-fluoridation | 253 | 194 | 50 | 71 | 5 | 3 | 65 |

Among on-topic speakers read, the share the free cue rules left `unclear` or `concerns_only` and the classifier did not
give a confident side fell from **74.5% to 36.1% for data centers** (2,214 speakers) and **62.6% to 34.7% for guns**
(649). Guns has the most off-topic hits (1,791 of 2,440: caption errors such as "fire arm", gun-violence talk with no
limit at issue), which the classifier drops.

**Heat:** 6,499 public speakers now carry a classifier heat (`heat_confidence >= 0.65`), beside the 138 with the AI
meeting analysis's rating, which is kept. On the 22 speakers that have both, the classifier's heat matches exactly 22.7%
and within 1 point 90.9% (Pearson 0.65), against 13.6% / 77.3% for a constant guess of 2; the overlap is small, so
heat is shown with its method and confidence and is not used to rank anything without a minimum count.

`gold.meeting_speaker_topic_side` holds 12,789 rows (3.5 MB); the public projection drops the 5,886 `not_sure` rows
(6,903 rows). Publish with `--only meeting_speaker_topic_side meeting_speaker_position` (the second for the classifier
heat); no other serving table changes.

## Known limits

- The current question version per topic is the one read most recently, so a reworded topic that is only part-way
  re-read hides its older readings until the re-read finishes; finish a re-read before rebuilding the mart.
- The curated ids 100010-100020 come from the warehouse's seed (the crime / parks / bike-lanes topic branches); `main`'s
  seed file does not have them yet (#1401).
- Six topics are held (#1402). Usage rows lost at container restarts: #1403.
