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

| Metric | Theirs | Ours | Why they differ |
|---|---|---|---|
| Public comments | 10,202 | pending the first local run | see below |
| Local governments | 417 | pending | |
| Opposed / in favor / asked questions | 9,232 / 718 / 252 | not counted (needs phase 2 stance) | |
| Meetings with no supporters | 658 of 898 (73%) | not counted (needs phase 2 stance) | |
| Water use | 3,621 (36%) | pending | |
| Quality of life | 3,388 (34%) | pending | |
| Lack of transparency | 3,291 (33%) | pending | |
| Limited community benefit | 1,438 | pending | |
| Few jobs | 1,246 | pending | |
| Taxpayer subsidies | 1,222 | pending | |
| Comments raising 2+ concerns | 88% | pending | |
| Google / Amazon / Meta / Microsoft | 386 / 342 / 315 / 287 | pending | |
| OpenAI / xAI / Anthropic | 151 / 128 / 29 | pending | |
| Elon Musk / Sam Altman / Peter Thiel | 96 / 28 / 23 | pending | |
| Any mention of AI | 2,046 (21%) | pending | |
| Residents / property owners / union workers | 6,832 / 542 / 183 | pending | |
| Red vs blue, rural vs urban counties | split given | not counted (no county vote or rural-urban data in the warehouse) | |
| Mentions per meeting since 2022-Q1 | 22× | pending | |

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

**Cost estimate.** Input tokens ≈ Σ(comment words) × 1.33 + about 150 prompt tokens per comment. At tonight's Jev rate
(151.8M tokens cost $6.37, about $0.042 per 1M input tokens), the 2026 data-center set and the full topic set cost
pending the first local run (filled from `meeting_comment.word_count`).
`python -m ingestion.meetings.comment_segments --dry-run` gives the counts without writing anything.

## Follow-ups (separate issues)

- County 2024 presidential results (for "heavily" red/blue at a 15-point margin) and USDA rural-urban codes. Neither
  is in the warehouse (`bronze_localbench_*` has RUCC for a benchmark sample only), so both need a loader issue first.
- Recorded-meetings-per-quarter denominator for a true "mentions per meeting" (today: passages per mentioning meeting).
- Neon serving copy of the new marts (`hosting.neon.sync_public_to_neon`). Not done here: this phase writes only the local warehouse.
- Reuse the self-introduction helpers from #1231 / PR #1245 (`ingestion.youtube.speaker_intros`) once they merge, so
  one name cleaner serves both.
