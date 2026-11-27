---
title: Data center comments, comment by comment
description: How Open Navigator splits meeting captions into public comments once per meeting, flags concerns, companies, AI, roles and places with free keyword rules, and how its 2026 numbers compare with americansentiment.com's data-center page.
---

# Data center comments, comment by comment

Epic [#1232](https://github.com/getcommunityone/open-navigator/issues/1232) · phase 1 [#1233](https://github.com/getcommunityone/open-navigator/issues/1233). Decided 2026-11-26.

## Theirs vs ours (2026)

"Theirs" are the figures the owner read off americansentiment.com/datacenters (2026). We never fetch or copy that
site: its terms forbid competitors' use (see `ingestion.data_centers.community_events`). Every "ours" figure comes from
our own captions through `public.data_center_comment` and `GET /api/data-centers/comment-metrics?year=2026`.

Measured 2026-11-27 on the local warehouse (segmenter 1.2.0): 47,578 comments in 13,682 of 18,260 topic meetings, all
years. The 2026 data-center slice is below.

| Metric | Theirs (2026) | Ours (2026) | Why they differ |
|---|---|---|---|
| Public comments | 10,202 | **2,300** (2,020 say "data center" themselves, 280 are from the same comment period) | coverage and segmentation (below) |
| Local governments | 417 | **230** | we have data-center captions for 333 governments in 2026, and comments were found at 230 of them |
| Meetings | ~898 (658 + 240) | **599** with a data-center comment (976 meetings mention data centers; 771 of those had any comment segmented) | |
| Opposed / in favor / asked questions | 9,232 / 718 / 252 | **not counted**: needs the phase 2 stance pass | |
| Meetings with no supporters | 658 of 898 (73%) | **not counted**: needs stance | |
| Water use | 3,621 (36%) | **1,175 (51%)** | keyword list is broad (water, wells, gallons, aquifer) |
| Quality of life | 3,388 (34%) | **1,137 (49%)** | noise, traffic, health, pollution, generators |
| Rushed review | listed | **614 (27%)** | |
| Farmland / wildlife loss | listed | **575 (25%)** | |
| Lack of transparency | 3,291 (33%) | **430 (19%)** | NDAs and secrecy are often said without these exact words |
| Company distrust | listed | **289 (13%)** | |
| Community character | listed | **253 (11%)** | |
| Taxpayer subsidies | 1,222 (12%) | **249 (11%)** | close in share |
| Property rights | listed | **174 (8%)** | |
| Limited community benefit | 1,438 (14%) | **87 (4%)** | a model reads "what do we get out of this" better than keywords do |
| Few jobs | 1,246 (12%) | **59 (3%)** | we only count "few / only / temporary jobs" so that pro-jobs comments don't count |
| Electricity costs / grid (ours only) | not on their list | **450 (20%)** | |
| Comments raising 2+ concerns | 88% | **62%** (1,434) | our comments are cut by text rules; keyword recall is lower |
| Google / Amazon / Meta / Microsoft | 386 / 342 / 315 / 287 | **98 / 106 / 150 / 49** | same order of companies; fewer comments |
| OpenAI / xAI / Anthropic | 151 / 128 / 29 | **28 / 11 / 7** | |
| Elon Musk / Sam Altman / Peter Thiel | 96 / 28 / 23 | **21 / 3 / 3** (Bezos 7, Gates 3, Zuckerberg 3) | |
| Any mention of AI | 2,046 (21%) | **501 (22%)** | the share matches |
| Residents / property owners / union workers | 6,832 / 542 / 183 | **911 / 46 / 49** (+ advocacy groups 108, elected officials 73) | we read roles only from the introduction; many speakers give none |
| Red vs blue, rural vs urban counties | splits given | **not counted** | no county 2024 vote or rural-urban codes in the warehouse (follow-up) |
| Mentions per meeting, 2022-Q1 to now | 22× | meetings mentioning data centers: 22 → 646 (2026-Q2), about **29×**; passages per mentioning meeting 1.5 → 5.0, about **3.3×** | ours isn't divided by all recorded meetings, so part of the growth is our 2026 collection being denser |
| Places named (phase 1b, ours only) | not reported | towns/cities 1,799 · counties 680 · roads 375 · neighborhoods 366 · districts 141 · schools 134 · sites 119 comments | |

**Why our counts are lower.**

- **Coverage.** We have captions for about 976 data-center meetings in 2026. They have about 898 meetings with
  comments, but at 417 governments to our 333. Our 2026-Q3 is thin: 10 meetings mention data centers, against 646 in Q2,
  because recent captions aren't loaded yet.
- **Segmentation.** A comment is found only when the speaker introduces themselves or the chair calls them. 4,578 of
  18,260 meetings gave no comment at all. Our average comment is 722 words, which is long for a 3-minute limit. Some
  turns run into the next speaker's when that speaker never introduces themselves, so we under-count comments and
  over-count concerns per comment.
- **Keywords instead of a reader.** Concerns phrased without the listed words are missed (limited community benefit,
  few jobs), and broad words (water, noise) catch more. Where both sides use simple words, the shares agree: AI 22% vs
  21%, taxpayer subsidies 11% vs 12%.

## What a comment is

A comment is one speaker's turn at the microphone during a meeting, cut out of the meeting's timed YouTube captions.
The captions carry no speaker labels, so the boundaries are text rules (`packages/ingestion/src/ingestion/meetings/comment_segments.py`):

- **Start:** a self-introduction ("My name is…", "my name's…", "I'm Jane Doe and I live…") or the chair calling a
  speaker ("next speaker", "next is Ms. Cooper", "please come forward", "state your name", "you have three minutes").
  From an introduction the start backs up to the greeting before it ("Good evening, Mayor… my name is"), stopping at the
  caption tool's `>>` speaker-change mark, a pause of 3.5 seconds or more, or 60 seconds.
- **End:** the next speaker's start, the chair or timer closing it ("your time is up", "wrap it up", "thank you for
  your comments", "anyone else wish to speak", "close the public hearing"), a 20-second silence, or 8 minutes.
- **Dropped:** anything under 30 words (procedure, not a comment). Council discussion and staff reports without an
  introduction or a call never become comments.
- **Comment period:** comments less than 3 minutes apart share a `block_index`.

Segmentation runs **once per meeting and is topic-agnostic** (owner, 2026-11-26: "do it once per meeting and not every
topic"). It covers every meeting a curated topic links to (`public.topic_transcript_link`) plus the data-center set
(`public.data_center_meeting_mention`). Every topic reads the same comments.

**Public, and about a data center** (`data_center_comment`). A comment counts when its introduction doesn't say staff,
the applicant or a consultant (seed `comment_role_terms`, `is_public_comment = false`), and either:

- `own_words`: it says a Data centers topic keyword (curated topic 100001: data center, data centre, hyperscale, server farm); or
- `same_block`: it sits in a comment period where at least two public comments, and at least a third of them, say
  one, and it raises at least one data-center concern. Speakers often say "this project" without repeating "data center".

## Free flags (phase 1, no model)

All rules are keyword lists in dbt seeds, matched in SQL (`int_meeting_comment__flags`). None of them is a model's
reading of the comment.

| Flag | Seed | Matched on |
|---|---|---|
| Topics | `curated_topics` keywords | the comment |
| Concerns (multi-label) | `comment_concern_terms` (data-centers list follows the reference categories; "Electricity costs / grid" is ours, `in_reference_list = false`, left out of the multi-concern share) | the comment |
| Companies, public figures | `comment_entity_terms` (aliases: Google/Alphabet, Amazon/AWS, Meta/Facebook, OpenAI/ChatGPT, xAI/Grok, Anthropic/Claude AI…) | the comment |
| Any mention of AI | `comment_entity_terms` (`entity_type = ai`) | the comment |
| Self-described role | `comment_role_terms` (resident, property owner, union worker, business, farmer, advocacy group, elected official) | the introduction only (first 40 words from it), never inferred from the rest |
| Places (phase 1b) | `comment_place_patterns` + gazetteer (our `jurisdictions`, curated `data_center_project`) | the comment, case-sensitive |

## Privacy

Per [AGENTS.md](https://github.com/getcommunityone/open-navigator/blob/main/AGENTS.md), Privacy and data ethics:

- **No home addresses, ever.** Before any text is stored, the segmenter replaces what follows "I live at / on / off",
  "my address is" and any house-number street address with `[address removed]` (`scrub_personal_location`, unit-tested).
  "I live in Joliet" (a town) and "300 acres on Ridge Road" (no house number) are kept. The place tagger then sees only
  public places.
- **Names:** the name as heard stays in bronze and intermediate. Marts serve only `speaker_display_name` "First L."
  through the existing `speaker_display_name` macro, and nothing for a possible minor (an age under 18, a grade, a
  school year or scouts in the introduction).
- **No text served.** `meeting_comment`, `data_center_comment` and `data_center_comment_place` carry no comment text.
  The text stays in the private intermediate table.
- Nothing is looked up about anyone. It is all the caption's own words.

## Places named (phase 1b), the owner's NER question

"Are we capturing if the residents mention addresses, locations, districts, schools etc. as NER?" Yes for public
places, free, in `data_center_comment_place` (one row per comment, kind and place):

- roads and routes ("Route 9", "Ridge Road", "County Road 12"), schools ("Oak Hill Elementary", "… School District"),
  counties, parishes and townships ("Greene County"), neighborhoods and subdivisions, districts and wards
  ("District 3"), named sites ("the Pine Ridge site");
- gazetteer hits from our own data: jurisdictions in the meeting's state, and curated data center project names.

A resident's own address is never tagged (it was scrubbed first). A model-based NER pass could replace the shapes later.
That would be paid, so it belongs with phase 2.

## Free now vs needs the paid classifier

| Free now (phase 1) | Needs the per-comment classifier (phase 2, on hold) |
|---|---|
| comments, governments, meetings | opposed / in favor / asked a question |
| concerns, multi-concern share | meetings with no supporters (and comments in them) |
| companies, people, AI mentions | role × position |
| self-described roles, places | red/blue and rural/urban position splits (also need county data, below) |
| mentions per meeting by quarter | |

## Phase 2 design (not run): one classifier pass per comment

One call per comment answers every question together, so cost scales with comments, not topics:

1. **topic**: one of the curated topics, or none;
2. **stance on that topic**: opposed, in favor, question, or no position;
3. **concerns**: the shared list (a short topic-specific follow-up only for comments on that topic);
4. **self-described role**, confirming or filling the keyword role.

It follows the Jev pattern (`llm.typesafe`, a fixed output schema checked against known answers). It replaces the
per-(meeting, topic) topic-lean reads that the stories use today. It runs only on the owner's explicit yes.

**Cost estimate** (input tokens = words × 1.33 + 150 prompt tokens per comment, at tonight's Jev rate of $6.37 for
151.8M tokens, about $0.042 per 1M):

| Comment set | Comments | Words | Input tokens | Cost |
|---|---|---|---|---|
| 2026 data-center comments | 2,300 | 1.66M | 2.55M | about $0.11 |
| All 2026 comments, every topic | 20,357 | 14.1M | 21.8M | about $0.92 |
| All comments segmented, all years | 47,578 | 88.3M | 124.6M | about $5.23 |

Phase 2 would fill: opposed / in favor / question, meetings with no supporters, role × position and, once county data
exists, the red/blue and rural/urban splits. It runs only when the owner lifts the hold.

## Follow-ups (separate issues)

- [#1260](https://github.com/getcommunityone/open-navigator/issues/1260): county 2024 presidential results and USDA
  rural-urban codes, for the red/blue and rural/urban splits. Neither is in the warehouse.
- [#1261](https://github.com/getcommunityone/open-navigator/issues/1261): split speakers who never introduce themselves
  (the 722-word average comment).
- [#1262](https://github.com/getcommunityone/open-navigator/issues/1262): reuse the #1231 self-introduction helpers,
  and add a recorded-meetings-per-quarter denominator for a true "mentions per meeting".
- A Neon serving copy of the new marts (`hosting.neon.sync_public_to_neon`) is out of scope: this phase writes only to
  the local warehouse.
