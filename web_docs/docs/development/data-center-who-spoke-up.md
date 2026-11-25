---
sidebar_position: 38
title: Who spoke up about data centers
description: The rule for which public comments and which votes count as being about a data center item, what the rule misses, the two marts and the endpoint that serve the counts, and how to build them.
---

# Who spoke up about data centers

[Issue #930](https://github.com/getcommunityone/open-navigator/issues/930) puts five figures at the top of the
[data stories](../guides/data-stories.md) hub and gives the Data Center Story a "Who spoke up" screen: how many public
speakers spoke for a data center item, how many spoke against, how many asked a question, and the votes for and against
where a tally was recorded. This page is the rule for what counts, and what the rule misses.

## In short

- A public comment counts only when it is **about the data center item**. A comment on another item of the same meeting never counts.
- "About the data center item" means one of four things, all checked with the same data center words the rest of the site uses ([#932](https://github.com/getcommunityone/open-navigator/issues/932) added two).
- Votes count only for decisions that are about a data center **and** recorded both a yes and a no count.
- A figure with no data behind it is null in the table and the API, and reads "not recorded" on the page. It is never zero.

## The rule for a public comment

`public_comment` has one row per meeting, public speaker and item, with the speaker's stance. A row counts when any of
these holds. The table keeps the first that applies, in this order, in `match_basis`.

| `match_basis` | The comment counts when |
| --- | --- |
| `data_center_decision` | It is linked to a decision (`public_comment.event_decision_id`) whose `headline` or `decision_statement` says a data center word |
| `data_center_item` | It is on an uncontested (consent) item (`event_uncontested_item`, matched on the meeting and `item_id`) whose `headline` says a data center word |
| `own_words` | The speaker's own quoted words (`stance_evidence`) or the comment's `summary` says a data center word |
| `same_item` | Another public speaker on the **same item of the same meeting** says a data center word in their own quoted words (`stance_evidence`, not the summary). The item is about a data center even though its headline names it another way |

`same_item` is what catches an item like Casa Grande's "Phoenix Mart PAD major amendment (DSA 2600139)": the headline never
says "data center", but one speaker on it says "The data centers need to go away". The ten other speakers on that item ("We
ask that you deny this PAD", "Is there a way that the applicants can address the diesel generators?") are about the same
project, so they count. It needs an `item_id`, so general public comment (no item) never counts because of another speaker.

"A data center word" is the one definition in `dbt_project/macros/data_center_terms.sql` (`data_center_regex`): "data
center", "data centre", "datacenter", "datacentre", "hyperscale" and "hyperscaler", matched on word boundaries, so "metadata
center" is no match. `data_center_meeting_mention`, `data_center_project_mention` and `decision_company_mention` use the same
macro. There is no second definition.

Being made in a meeting where a data center came up is **not** enough. A meeting can discuss a data center for three minutes
and a park budget for an hour; the speakers on the park budget are not data center speakers.

### Each speaker once per meeting

A speaker who has several counted rows in one meeting (a comment on the rezoning and another on the water contract) is counted
once. The row that stands for them is the one with a known stance first, then the earliest in the recording, then the lowest
`public_comment_id`. `is_counted` marks it.

### Stance

The four counts use `public_comment.stance_bucket` as it is: for, against, question, neutral. A speaker whose stance is
unknown (null) is in none of the four. Unknown is never counted as neutral.

### What the rule misses

Comments that are about a data center and are **not** counted:

- General public comment that never says the words. It has no item, so only `own_words` can catch it, and "Please do not approve this project, our wells are already low" names no data center.
- A comment on an item whose headline and statement name the project some other way ("the Project Sail rezoning") when no speaker on that item says a data center word either.
- Anything said in a meeting that has no analysis. `public_comment` only holds analysed meetings, so the counts cover fewer meetings than the "meetings where a data center came up" count, which comes from transcripts.

Comments that are counted and are arguably not about the data center:

- A comment on a data center item (by its headline, or through `same_item`) is counted even when the speaker talked about a side issue of that item.
- Through `same_item`, one speaker's passing mention of a data center pulls in every speaker on that item, even when the item itself is about something else. `same_item` reads only the speaker's verbatim quote (`stance_evidence`), never the AI's `summary`, so it takes a speaker's own words to spread.

Rules that were considered and left out:

- Counting a comment because it was spoken during a transcript passage that mentions a data center. A passage is three minutes long, and the next speaker on another subject often falls inside it, so it would count comments that are not about the data center. (The comments' timestamps are also null in the light analyses, so the rule could not be applied.)
- Matching the decision's narrative fields (`competing_views`, `smart_brevity`, `human_element`). Measured in #932: they matched no decision the headline had not already matched.
- A wider vocabulary. Measured in #932 over all comments and decisions: "megawatt", "servers", "substation", "backup generators" and "digital infrastructure" hit more often in meetings where no data center came up than in meetings where one did, so they would add more wrong rows than right ones.

## The rule for a vote

`event_decision.vote_tally` is JSONB with two keys, `yes` and `no`. Either value may be a number, a numeric string or null.
The analysis prompt sets both to null when a decision was made by consensus or without a recorded vote.

- A decision is a **data center decision** when its `headline` or `decision_statement` says a data center word (the same test as above, on the latest extraction of the decision).
- A decision has a **recorded tally** only when both `yes` and `no` are whole numbers. A tally with a yes count and no "no" count is not used, because writing 0 for the missing side would invent a number.
- `decisions_with_tally` counts those decisions. `votes_for` and `votes_against` are the sums of `yes` and `no` over them, and are null when there are none.

What this misses: votes on uncontested items, and decisions where the extraction did not capture the tally. Uncontested items
are in `event_uncontested_item` since #932, but their `vote` is text as said ("voice vote", "5-0"), not a tally, so they are
not summed into `votes_for` and `votes_against`. When the page was built, the data center decisions the live API returned all had a null `vote_tally`, so in
production the two vote figures may read "not recorded" until tallies are extracted.

## The tables

All three are dbt marts in `gold`, published to `public` by `publish_public_serving`. The two `data_center_*` marts are copied
to Neon. `event_uncontested_item` is not yet (it is `NON_SERVING` in `hosting.neon.sync_public_to_neon` until
[#933](https://github.com/getcommunityone/open-navigator/issues/933) gives it a reader). `event_uncontested_item` is read from `bronze.bronze_uncontested_items_from_ai`, which unpacks `structured_analysis->'uncontested_items'` with the same publishable-analysis filter as the other `bronze_*_from_ai` extractions.

| Model | Grain | Primary key | Foreign keys |
| --- | --- | --- | --- |
| `data_center_meeting_position` | One row per meeting where a data center came up | `data_center_meeting_position_id` | `event_meeting_id` to `event_meeting` |
| `event_uncontested_item` | One row per uncontested (consent) item of a recording's preferred analysis (`int_preferred_event_analysis`, as `event_decision` uses); the sibling of `event_decision`, which holds only contested decisions. An `item_id` the analysis repeated within one meeting keeps its first item only (13 such items on the local warehouse, 24 Nov 2026) | `event_uncontested_item_id` | `event_meeting_id` to `event_meeting` |
| `data_center_public_comment` | One row per counted public comment | `public_comment_id` | `public_comment_id` to `public_comment`, `data_center_meeting_position_id` to `data_center_meeting_position`, `event_meeting_id` to `event_meeting`; `event_decision_id` to `event_decision` as a relationships test |

The rule itself is one intermediate view, `int_data_center__public_comment`. Both marts read it, so the counts and the
quotes can never use different rules.

A meeting has a row in `data_center_meeting_position` when its recording has a passage in `data_center_meeting_mention`, or
it has a data center decision, or it has a counted comment. Its columns are `event_meeting_id`, `video_id`, `meeting_date`,
`jurisdiction_name`, `state_code` and `state`, the four speaker counts (`speakers_for`, `speakers_against`,
`speakers_question`, `speakers_neutral`; 0 means the meeting was analysed and no such speaker was found),
`decisions_with_tally`, and `votes_for` and `votes_against` (null when no tally is recorded).

`data_center_public_comment` carries what a quote on the page needs: the speaker's own words (`quote`, verbatim from the
transcript), `speaker_role`, `stance_bucket`, `start_seconds`, `video_url`, the meeting's place and date, and
`decision_headline`, the item the comment is on (a contested decision or an uncontested item). The headline is shown with the quote ("On: ..."), so a quote that
does not itself say "data center" still shows why it is there.

`data_center_public_comment` was not in the issue's contract. It was added because the endpoint has to return quotes, the
API may only read `public`, and the rule for which comments count must stay in dbt.

## Decisions on data center items

[#933](https://github.com/getcommunityone/open-navigator/issues/933) adds `data_center_decision`, a mart in `gold` served
in `public` and copied to Neon. It has one row per decision a meeting took on a data center item:

| Source | `contested` | Counts as a data center decision when |
| --- | --- | --- |
| `event_decision` (debated) | true | its `headline` or `decision_statement` says a data center word |
| `event_uncontested_item` (passed without debate: consent agenda, routine vote) | false | its `headline` says a data center word |

- `votes_for` and `votes_against` come only from a debated decision whose tally records both sides as whole numbers (the
  vote rule above).
- An item passed without debate keeps its vote as said in `vote_text` ("voice vote", "5-0"). It's never turned into
  numbers.
- Only debated decisions have a page, so `decision_url` (`/decisions/:id`) is null for the others.
- The primary key `data_center_decision_id` is the source row's own id. The foreign key `event_meeting_id` points to
  `event_meeting`.

`GET /api/data-centers/decisions?state=&city=&limit=` returns:
- the scope;
- `counts`: `contested`, `uncontested` and `meetings`, over the whole scope;
- the decisions, newest first.

When the mart isn't loaded, `available` is false and the counts are null. The Data Story's **Decisions** screen draws one
dot per decision in two groups: "Debated" and "Passed without debate" ([Data stories](../guides/data-stories.md)).

## The endpoint

`GET /api/data-centers/positions?state=&city=&limit=`

- `scope`: the filters applied (national, state or city), as every data center endpoint returns it.
- `available`: false when the table is not in the database yet. Every total is then null.
- `totals`: `meetings` (meetings with at least one counted speaker or one recorded tally), `meetings_reviewed` (all rows in scope), the four speaker counts, `decisions_with_tally`, `votes_for` and `votes_against` (null when `decisions_with_tally` is 0).
- `quotes`: `for`, `against` and `question`, up to `limit` each (default 3, at most 10). Each has `public_comment_id`, `quote`, `speaker_role`, `jurisdiction_name`, `state_code`, `meeting_date`, `video_url`, `start_seconds`, `jump_url`, `decision_headline` and `match_basis`. Quotes are spread across meetings (one per meeting first), newest meeting first.

`available` and `meetings_reviewed`, and the quote's `jump_url`, `decision_headline` and `match_basis`, are additions to the
issue's contract.

## Build it

The tables do not exist until dbt has built them. Until then the endpoint answers with `available: false` and the page shows
"Who spoke for and against is not loaded yet."

```bash
./scripts/dbt.sh run --select bronze_uncontested_items_from_ai event_uncontested_item public_comment+ data_center_meeting_position data_center_public_comment
./scripts/dbt.sh test --select event_uncontested_item int_data_center__public_comment data_center_meeting_position data_center_public_comment
./scripts/dbt.sh run-operation publish_public_serving
```

The first command also rebuilds `public_comment` and what reads it. If `public_comment` is already current, select only
`int_data_center__public_comment data_center_meeting_position data_center_public_comment` (with `event_uncontested_item` the
first time, since the rule reads it). Every `dbt run` publishes the
`public` views when it ends, so the third command is only needed after a run that failed part-way.

## How it was checked

There was no warehouse where this was written. The three models' Jinja was rendered by hand and run against a throwaway
PostgreSQL 16 cluster holding a handful of made-up test rows: a meeting with speakers on both sides plus speakers on a park
budget and on roads (not counted), a speaker with an unknown stance (in no count), a speaker with two rows (counted once), a
decision with a tally, one without, one with only a yes count (not used), one with string values, a superseded extraction of
a decision, a meeting dated in the future (date null), and "metadata center" (no match). The endpoint's own SQL was then run
against those tables for national, state and city scopes, and with the table dropped. Those rows exist only in that cluster.
`dbt parse` could not be run there (the dbt packages could not be downloaded), so the first `dbt run` is the first real
compile.
