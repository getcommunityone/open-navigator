---
sidebar_position: 39
title: Topic meeting lean
description: How Jev reads how the public and elected officials leaned on each curated topic, per meeting, into topic_meeting_lean (#1126), and what the maps show from it.
---

# Topic meeting lean

[#1126](https://github.com/getcommunityone/open-navigator/issues/1126) extends the data-center reading
([Data center meeting lean](data-center-meeting-lean.md)) to the other curated topics, so every topic story can draw the
four-colour map ([#1127](https://github.com/getcommunityone/open-navigator/issues/1127)).

## In short

- **What:** for each meeting linked to a topic, Jev (TypeSafe's classifier) answers three questions: how the members
  of the public leaned, how the elected officials leaned, and what happened to an item on the topic.
- **Which meetings:** only those in `topic_transcript_link` for that topic. Data centers keep their own screen.
- **What is read:** only the passages that name the topic. The transcript is cut into chunks of about 10k tokens and
  up to 3 chunks containing the topic's keywords are sent, most keyword hits first. A long meeting's late public
  comment is read ([#1145](https://github.com/getcommunityone/open-navigator/issues/1145)) and an unrelated first hour
  isn't paid for.
- **What it is not:** a count of speakers. Every lean is labelled "AI reading of meetings". Nothing is tied to a person.

<details>
<summary>The questions and which way "for" points</summary>

Each topic's wording lives in `llm.typesafe.topic_lean.TOPICS` and is hashed into its own question version, so
rewording one topic re-reads only that topic.

| Topic | "In favor" means in favor of |
|---|---|
| Short-term rentals | allowing short-term rentals (permits, fewer limits) |
| Flock and license plate readers | buying, keeping or expanding the cameras |
| Guns | the firearm-related proposal before the body (a range, show, store, rule or detection contract) |
| Pickleball | building, keeping or expanding the courts or venue |
| Water fluoridation | keeping or adding fluoride in the water |
| Bike lanes | building or keeping the lanes or paths |

Guns is the one topic where "for" depends on the proposal, because a gun range and a gun restriction point opposite
ways. Its map reads "for or against what was proposed", and the hand check below decides whether it is shown.

Labels: `public_lean` and `official_lean` are `mostly_opposed`, `mostly_supportive`, `mixed` or `did_not_speak`;
`outcome` is `approved`, `denied`, `tabled_or_deferred`, `moratorium`, `discussed_no_action` or `no_item`. A lean is
averaged only over the chunks where someone likely spoke on the topic, as for data centers.
</details>

<details>
<summary>Tables and flags</summary>

- **Bronze:** `bronze.bronze_transcript_topic_lean_jev`, primary key (video_id, topic_id, question_version), created by
  the first run. Until then `stg_jev__transcript_topic_lean` builds empty, so dbt runs keep passing.
- **Mart:** `public.topic_meeting_lean`, one row per (video_id, topic_id) under the topic's current question version,
  primary key (video_id, topic_id), foreign key topic_id → `civicsearch_topic`. Served on Neon (small).
- **Flags**, with the data-center thresholds: `public_against` (mostly opposed, P ≥ 0.7), `public_for` (mostly
  supportive, P ≥ 0.7), `officials_sided_against_public` (public mostly opposed, officials mostly supportive, outcome
  not a denial or a moratorium).
- **Served by** `GET /api/topics/{topic_id}/state-map` (the map) and `GET /api/topics/{topic}/caption-facts` (the
  caption).
</details>

<details>
<summary>Run it</summary>

Paid (Jev's per-token price). A run starts only on the owner's go-ahead for that run; read usage before and after and
put the cost on #1126 (AGENTS.md).

```bash
python -m llm.typesafe.screen_transcripts --topic pickleball --limit 20 --dry-run   # tokens and cost, nothing sent
python -m llm.typesafe.screen_transcripts --topic pickleball --limit 20             # a small first batch
python -m llm.typesafe.screen_transcripts --topic all --limit 100000                # every topic's linked meetings
cd dbt_project && dbt build --select stg_jev__transcript_topic_lean+                # then publish to Neon as usual
```
</details>

## Hand check

To do after the first run: 10 meetings per topic, read against the recording, the same way as the data-center check.
Until it is written here, treat the colours as unverified, and in particular "public mostly supported" and "public split" (labelled so since #1190), which
were about 2 of 4 right for data centers.
