---
sidebar_position: 39
title: Topic meeting lean
description: How Jev reads how the public and elected officials leaned on guns, short-term rentals, pickleball, license plate readers and water fluoridation in each meeting, into topic_meeting_lean (#1126), the questions and their stored versions (#1201, #1239), the CareQuest mapping for fluoridation, the thresholds and what the stories show.
---

# Topic meeting lean (AI reading)

The data center story can show where the public leaned against data centers and where officials sided against the
public ([Data center meeting lean](data-center-meeting-lean.md)). Issue
[#1126](https://github.com/getcommunityone/open-navigator/issues/1126) asks Jev the same questions for five more topics,
so their stories can draw the four-colour map and a disagreement caption
([#1125](https://github.com/getcommunityone/open-navigator/issues/1125)).

Jev is a cheap multiple-choice transcript classifier. It returns probabilities, never text, so **every value here is an
AI reading of one meeting's transcript, not a count of speakers**, and it is an aggregate for the meeting, never tied
to a person (AGENTS.md, Privacy).

## How it runs

Paid (Jev's per-token price). A run starts only on the owner's go-ahead for that run; read usage before and after and
put the cost on the run's issue (AGENTS.md). `--dry-run` sends nothing: it counts the meetings still to read and
estimates the tokens and cost.

```bash
python -m llm.typesafe.screen_transcripts --topic <slug> [--limit N] [--dry-run] [--max-input-tokens N]
python -m llm.typesafe.screen_transcripts --topic all --limit 100000 --dry-run   # every topic, one after another
python -m llm.typesafe.screen_transcripts --topic guns,pickleball --dry-run      # a comma-separated list
cd dbt_project && dbt build --select stg_jev__transcript_topic_lean topic_meeting_lean   # then publish to Neon as usual
```

`--topic` takes a slug, a comma-separated list of slugs, or `all`; `--limit` and `--max-input-tokens` apply per topic.

| Slug | topic_id | What is supported or opposed |
|---|---|---|
| `guns` | 100005 | A local gun-control measure (limits on where guns are carried or fired, sales, gun shows, shops or ranges near homes, storage, assault weapons, ghost guns). A staple, nail, glue, radar or speed "gun", police buying their own service weapons, a shooting report with no measure, and ShotSpotter don't count. A Second Amendment sanctuary resolution is the opposite side. |
| `short-term-rentals` | 100003 | Allowing short-term rentals (Airbnb, VRBO, stays under about 30 days). Long-term rentals, hotels, RV parks and equipment or venue rentals don't count. |
| `pickleball` | 100006 | Pickleball courts and play: building, converting, lighting or keeping courts, and their hours. Neighbors' noise and location complaints are the "against" side. A passing mention in a list of recreation programs doesn't count. |
| `license-plate-readers` | 100004 | A government's (usually police) use of automated license plate readers, including Flock cameras. Red-light and speed cameras, ordinary security cameras and a "flock" of birds don't count. |
| `water-fluoridation` | 100002 | Community water fluoridation. Toothpaste, dental varnish and school dental programs, other water chemicals, and routine water quality reports don't count. |

The definitions are in `packages/llm/src/llm/typesafe/topic_lean.py` (`TOPICS`).

- **Which meetings:** the meetings `public.topic_transcript_link` links to the topic (curated keyword matches).
- **Which part of the transcript:** only the chunks (about 100,000 characters each) that contain one of the topic's
  keywords, at most four. The rest of a long meeting costs nothing and can't drown out the passage. A chunk that is
  too long for Jev (32k tokens) is retried at half size. This is passage-targeted, not the head of the transcript, so
  the [#1145](https://github.com/getcommunityone/open-navigator/issues/1145) blind spot of the data-center screen
  (which read only the first chunks) doesn't apply. Each row records `chunk_selection` (`keyword_passages`, or
  `evenly_spaced` when no keyword is in the caption text) and `passages_covered` (keyword-passage chunks screened, of
  `keyword_chunks`). `--neighbor-chunks N` also sends N chunks either side of each passage chunk; it defaults to 0
  because a chunk is about 100,000 characters and already holds the passage.
- **Combining chunks:** each answer is averaged only over the chunks where that group spoke on the topic, or where an
  item came up (`public_lean()`, as for data centers).
- **Where it lands:** `bronze.bronze_transcript_topic_lean_jev`, PK `(video_id, topic_id, question_version)`. Each
  topic's questions have their own version hash; a run skips meetings already screened at the current version, so it
  can be stopped and resumed. Rewording a topic's questions starts a new version.

## The questions

Four topics share the labels:

| Column | Answers |
|---|---|
| `public_lean` | `mostly_supportive`, `mostly_opposed`, `mixed`, `did_not_speak` |
| `official_lean` | the same, for the elected officials (not staff, not the public) |
| `outcome` | `advanced`, `blocked`, `tabled_or_deferred`, `discussed_no_action`, `no_item` |

`advanced` and `blocked` are defined per topic. For example, for guns `blocked` means the body rejected or repealed a
limit on firearms, adopted a sanctuary resolution or approved a range, shop or show; for pickleball it means courts
were denied, removed or closed, hours cut, or play limited for noise.

### Water fluoridation: CareQuest's poll positions

At the owner's request (2026-11-26) the fluoridation leans mirror the national poll question "Which of the following
comes closest to your position?", so the story can chart meetings beside the poll. Source: CareQuest Institute,
"Attitudes about Fluoride: National Survey Results", Marketing for Change Co., July 7–9, 2025, n=1,114, ±2.94%.

| Jev label (public and officials) | CareQuest answer | Rolled up in the mart to |
|---|---|---|
| `support_require_all` | Support fluoridation; all communities should be required to fluoridate | `mostly_supportive` |
| `support_local_choice` | Support fluoridation; each community should decide | `mostly_supportive` |
| `no_opinion` | No opinion | `no_opinion` |
| `oppose_local_choice` | Oppose fluoridation; each community should decide | `mostly_opposed` |
| `oppose_ban_all` | Oppose fluoridation; all communities should be banned from fluoridating | `mostly_opposed` |
| `did_not_speak` | (not a poll answer: nobody in the group took a position) | `did_not_speak` |

A speaker who only asks their own community to keep (or stop) fluoridating, without calling for a requirement (or a ban)
everywhere, counts as `*_local_choice`.

The outcome follows CareQuest's state legislation categories as far as a local meeting can:

| Jev outcome | `outcome_group` |
|---|---|
| `voted_to_end_fluoridation` | `blocked` |
| `voted_to_keep_or_start` | `advanced` |
| `tabled_or_deferred` | `tabled_or_deferred` |
| `discussion_only` | `discussed_no_action` |
| `no_fluoridation_item` | `no_item` |

## The mart

`public.topic_meeting_lean` (gold, published to `public`): one row per meeting and topic, PK `(video_id, topic_id)`,
FK `topic_id` → `civicsearch_topic`, FK `jurisdiction_id` → `jurisdictions`. Only rows under each topic's current
question version (the version with the latest `screened_at`, `stg_jev__transcript_topic_lean`).

- `public_lean` / `official_lean` and their `_p`: for fluoridation, the group (support, oppose, no opinion) with the most
  summed probability, and that sum. `public_position` / `official_position` and their `_probabilities` keep the five
  CareQuest answers (null for other topics).
- **`public_against`**: `public_lean = 'mostly_opposed'` with p ≥ 0.7 (the data-center threshold).
- **`public_for`**: `public_lean = 'mostly_supportive'` with p ≥ 0.7.
- **`officials_sided_against_public`**: the public mostly opposed, officials mostly supportive, and the body did not
  block it (`outcome_group <> 'blocked'`, the analogue of the data-center moratorium, denial and rules exclusions).
- **`excluded_no_item`** ([#1136](https://github.com/getcommunityone/open-navigator/issues/1136)): the outcome says no
  item on the topic came up (`outcome_group = 'no_item'`) with p ≥ 0.7. The keyword link was a false hit (a passing
  mention, another sense of the word), so maps and counts leave the meeting out, as for data centers.
- **`official_action`** (#1136): what the body did, read from the outcome, **only where the public did not speak**
  (otherwise `none`): `for`, `against` or `none`. The direction is always the subject in the table above:

| Topic | `for` (subject advanced) | `against` (blocked or tabled) |
|---|---|---|
| guns | adopted or advanced a limit on firearms (incl. denying or restricting a range, gun shop or gun show) | rejected or repealed a limit, adopted a Second Amendment sanctuary resolution, approved a range, shop or show; or tabled the item |
| short-term rentals | approved a rental permit, or rules that allow, register or loosen limits on them | denied a permit, banned, capped, paused (moratorium) or tightened limits; or tabled |
| pickleball | approved, funded or built courts, converted courts, added lights or hours | denied, removed or closed courts, cut hours, limited play for noise; or tabled |
| license plate readers | approved a contract, purchase, installation, renewal or expansion | rejected, cancelled, paused or removed them, or limited use or data sharing; or tabled |
| water fluoridation | `voted_to_keep_or_start` | `voted_to_end_fluoridation`, or `tabled_or_deferred` |

`discussed_no_action` / `discussion_only` and `no_item` give `none`. For guns, `for` means for gun control, so a map
should label it that way.

## The code that wrote the stored readings (#1201, #1239)

Every row in `bronze.bronze_transcript_topic_lean_jev` was written on 26 Nov 2026 by the `topic_lean.py` now on
`main`. Until [#1201](https://github.com/getcommunityone/open-navigator/issues/1201) that version existed only as an
uncommitted file in a working copy, while `main` held an earlier writer (PR #1166) whose table had none of
`topic_slug`, `keyword_chunks`, `transcript_chars`, `chunk_selection` or `passages_covered` (its first save failed
with a NotNullViolation on `topic_slug`), and whose differently worded questions hashed to different versions, so its
dry run counted every meeting already read as unread. The earlier writer is gone; the one that matches the table and
its question versions stays. Each topic's `question_version` is pinned in `packages/llm/tests/test_topic_lean.py`
(`STORED_QUESTION_VERSIONS`), and another test checks that `CREATE_SQL` / `UPSERT_SQL` and the dbt source list the
same 20 columns.

| Topic | `question_version` | Rows (27 Nov 2026) | Still to read (`--dry-run`) |
|---|---|---|---|
| `guns` | `48468cc5296e` | 7,036 | 587 |
| `short-term-rentals` | `357daa1ae513` | 4,156 | 0 |
| `pickleball` | `ec1984d88dd7` | 3,960 | 0 |
| `license-plate-readers` | `9a2753c719c8` | 1,216 | 0 |
| `water-fluoridation` | `5a7828a925fd` | 526 | 0 |

What changed on `main` with it, and why the stored version wins over the earlier `main` code:

- **Questions.** The stored wording (`subject`, `excludes`, `sides`, `advanced`, `blocked` per topic) replaces the earlier
  `thing` / `stance` wording. Keeping the earlier wording would mean re-reading all 16,894 meetings to get readings
  that match the code. Guns is the gun-control question
  ([#1239](https://github.com/getcommunityone/open-navigator/issues/1239)), not the earlier "the firearm-related
  proposal before the body" (`7b0f743c88e3`, never stored).
- **Outcomes.** `advanced` / `blocked` (defined per topic) replace the earlier `approved` / `denied` / `moratorium`.
- **Keywords and chunks.** Keywords come from `public.civicsearch_topic.keyword_stats` (the phrases the topic links
  matched), not the seed; chunks are the screen's (`--chunk-chars` 100,000, `--max-chunks` 4), not the earlier 40,000 / 3.
  Both versions already read only keyword passages ([#1145](https://github.com/getcommunityone/open-navigator/issues/1145)):
  the stored one also falls back to evenly spaced chunks (never just the head) and records `chunk_selection` /
  `passages_covered`. None of this is in the question hash, but it is what produced the readings.
- **Bike lanes** were in the earlier `TOPICS` (topic_id 100007, never read) and are not in the stored version. In the
  local warehouse `civicsearch_topic` 100007 is "Violent crime", not bike lanes, so a bike-lanes run would read the
  wrong meetings. Adding it back needs its own question and the right topic id
  ([#1253](https://github.com/getcommunityone/open-navigator/issues/1253)).
- `--topic all` (and comma lists) from the earlier CLI is kept; the earlier `--topic-chunk-chars` /
  `--topic-max-chunks` are replaced by the screen's `--chunk-chars` / `--max-chunks`, plus `--neighbor-chunks` and
  `--max-input-tokens`.

### Water fluoridation's labels (#1204)

All 526 water-fluoridation rows carry `question_version` `5a7828a925fd`, the CareQuest poll question above. Their
labels (`oppose_local_choice` 75, `support_local_choice` 22, `oppose_ban_all` 9, `no_opinion` 7, `did_not_speak` 413
on 26 Nov 2026) are that question's own choices, not stray labels: [#1204](https://github.com/getcommunityone/open-navigator/issues/1204)
compared them with the earlier `main` question, which never wrote any row. The data is unchanged. The mart rolls them
up as in the table above, so `public_lean` holds only `mostly_supportive`, `mostly_opposed`, `mixed`, `no_opinion` or
`did_not_speak`, and its `accepted_values` test checks that set: a label outside it is a real failure (a writer out of
step with its question), not the known fluoridation labels. `public_position` / `official_position` have their own
`accepted_values` test on the five positions plus `did_not_speak`.

## Positions shown on the stories (#1200)

Each meeting's reading is shown as one of four positions, in the topic's own words (`web_app/src/utils/topicPositions.ts`,
which restates each topic's `subject` and `sides`; a vitest reads `topic_lean.py` and checks them):

- **Against** (`public_against`: mostly opposed, P ≥ 0.7), e.g. "Want limits on short-term rentals", "Favor gun
  rights".
- **For** (`public_for`: mostly supportive, P ≥ 0.7), e.g. "Want to allow short-term rentals", "Favor gun limits".
- **Split** (neutral): mixed, or a for/against lean under P 0.7.
- **Missing**: no reading yet, or `did_not_speak`. Never shown as split.

Gun control is the one topic where "for" and "against" could each be read either way (against guns, or against gun
limits), so the site names both sides instead ([#1237](https://github.com/getcommunityone/open-navigator/issues/1237)):
**Favor gun limits** (`mostly_supportive`: asking for limits on guns, or objecting to a range, shop or show near homes)
and **Favor gun rights** (`mostly_opposed`: defending gun rights or backing a Second Amendment sanctuary resolution).
The topic id (100005), slug and URL stay `guns`; only the display name is "Gun control". The headline's conclusion and
its thresholds: [Story captions](story-captions.md#decision-each-topics-position-in-its-own-words-and-the-places-conclusion-in-the-title-1200).

## Hand check

To do: 10 meetings per topic, read against the recording, the same way as the data-center check. Until it is written
here, treat the colours as unverified, in particular "public mostly supported" and "public split" (labelled so since
#1190), which were about 2 of 4 right for data centers.
