---
title: Meeting sentiment (public-comment stance)
sidebar_label: Meeting sentiment
description: How public-comment stance is extracted with the existing meeting analysis, stored per speaker and per decision, validated without human labelling, piloted on 40 meetings, and shown in three buckets.
---

# Meeting sentiment (public-comment stance)

Status on 2026-11-24: **phase 1 code is written and unit-tested; nothing has been run on real meetings and no
stance appears on the site yet.** This page was rewritten after a full review the same day; the earlier drafts are in
git history. Related: the meeting-metrics proposal for the Matrix map (issue #806),
[Jev-light cascade](./jev-light-cascade-design.md), [Batch analysis light vs full](./batch-analysis-light-full-design.md).

## In short

- "Sentiment" means **stance**: what a member of the public asked the body to do about the action being decided.
  It is not emotional tone.
- Stance is extracted **in the analysis call we already make**, for both the full and the light tier, as one row per
  public speaker per item (`public_participation[]`). No separate pass is needed for analysed meetings.
- It is reported as **against, for, asked questions, and neutral**, because many comments take no side.
- Each comment also carries **how heated** it was (1 to 5) and the **speaker's role** (resident, advocacy group,
  expert and so on), in both tiers.
- A **pilot of 40 meetings** (20 full, 20 light, from different counties and states) comes before any wider run.
- Checks are automated. With nobody labelling by hand, the site says the stance is machine-estimated and shows the
  speaker's own quoted words and a link to the moment in the recording.

## What the review changed

The earlier draft proposed adding a `stance` to `human_element.personal_stories` and deriving a decision's stance from
those voices, with Jev backfilling the stored story text. Reading the pipeline end to end showed four problems.

1. **The pipeline already has a slot for this, and nothing fills it.** `bronze_public_participation_from_ai` reads a
   `public_participation[]` array (speaker, stance, summary, timestamps) and feeds the `engagement` part of the
   interestingness score. Neither current prompt asks for that array, so only about 1 of 1,569 analyses carries it and
   engagement is near zero. Asking for the array fixes sentiment and engagement together, with the loader already built.
2. **`personal_stories` is the wrong population.** The prompt defines it as "specific anecdotes used to argue a point",
   so it holds the storytellers, not everyone who spoke, and only on contested decisions. Counting stance over it
   would over-weight memorable speakers and miss general public comment.
3. **Deriving a decision's stance from a majority of voices throws information away** and made the full and light
   tiers answer different questions. Both tiers now emit the same rows, and the per-decision numbers are plain counts.
4. **Jev reading the stored story text is not an independent check.** That text is the first model's paraphrase, so
   agreement would mostly measure whether Jev can read a summary. The check now rests on the verbatim quote
   (`stance_evidence`), which code can verify against the transcript.

Smaller corrections: "unknown" is never counted as neutral, and already-analysed meetings are not backfilled by
guesswork. The review first dropped a per-speaker strength score as the least reliable judgment to ask for; the owner
then asked for "how heated" per comment, so it is back as `heat`, with a rubric tied to what was said (below) and a
check of its own.

## The data

### What the prompts ask (one row per public speaker per item)

Both `prompts/policy_analysis_part_1.md` (full) and `prompts/policy_analysis_lite.md` (light) now ask for:

| Field | Meaning | Full | Light |
| --- | --- | --- | --- |
| `speaker_id` | the speaker's slug (`people[].person_id` in full) | yes | yes |
| `decision_id` | the decision or uncontested item the comment is about; null for general public comment | yes | yes |
| `stance` | `For`, `Against`, `Asked questions`, `Mixed or neutral`, `Not stated`, toward **the action being decided** | yes | yes |
| `heat` | how heated the comment was, 1 to 5 (rubric below); null when too little was said | yes | yes |
| `speaker_role` | the capacity the speaker gave: Resident, Property owner, Business owner, Advocacy group, Expert, Union worker, Applicant or developer, Student, Other, Not stated | yes | yes |
| `stance_evidence` | the speaker's own words, verbatim, 25 words or fewer; null when no phrase shows it | yes | yes |
| `summary`, timestamps | one sentence; seconds into the recording | yes | no |

Rules written into the prompts: only members of the public and outside stakeholders (the body and staff are covered by
the vote and `competing_views.held_by`); a speaker who only asks questions is `Asked questions`; "supports it but only
with a bigger setback", a delay request or information only is `Mixed or neutral`; a comment that does not address the action is `Not stated`; never infer a
stance from a role, employer or name; never invent a speaker.

A prompt change is a new prompt version (the file hash, `llm.prompt_version`), so every row can be traced to the
wording that produced it.

### Stance buckets

| Bucket | `stance` values | Counted in the balance? |
| --- | --- | --- |
| **Against** (Opposed) | Against | yes |
| **For** (In favor) | For | yes |
| **Asked questions** | Asked questions | no, but always shown |
| **Neutral** | Mixed or neutral, Not stated | no, but always shown |

- The shares add to 100% of speakers with a known stance: `Against 30% | Questions 8% | Neutral 35% | For 27%`.
  A three-way view (Opposed, In favor, Asked questions) simply leaves the neutral segment out and says so.
- **The gradient** is the balance among speakers who took a side, `(for − against) / (for + against)`, from −1 to +1.
  Neutral speakers are left out of it so a mostly procedural meeting does not read as "split", and the neutral share is
  shown beside it.
- A missing stance is **unknown**, not neutral, and is not counted.

After this lands: run `bronze_public_participation_from_ai` once with `--full-refresh` (its key now includes the item
id). A speaker who comments on several items now has several rows, so the public-comment duration in
`int_civic__item_signals` sums each row's span; the speaker count is unchanged.

### How heated (1 to 5)

Captions carry no tone of voice, so heat is judged from the words and from what the transcript records. The same
rubric text is in both prompts (a test fails if they drift apart):

| Heat | Marker |
| --- | --- |
| 1 | calm; information or a neutral question |
| 2 | polite; a mild preference or concern |
| 3 | firm or emphatic; urges the body to act |
| 4 | states anger, frustration or alarm; accusations or warnings |
| 5 | personal attacks, threats of legal or electoral retaliation, shouting noted in the transcript, or cut off or gaveled by the chair |

Heat is the least reliable of the three facets, because loudness and sarcasm do not survive captioning. It is reported
as a distribution and a per-decision mean and maximum, never as a single score for a place, and it has its own check
(below). The prompt forbids raising it because of the topic or the speaker's side.

### Speaker role

The role is what the speaker said about themselves ("I live on Oak Street" is Resident; "I'm with the Rivers Alliance"
is Advocacy group). It is never inferred from a name or a stance; a speaker who gave no capacity is `Not stated`. The
list is fixed so counts can be filtered and compared across tiers; anything else is `Other`.

### Tables (dbt)

| Model | Grain | Key | Notes |
| --- | --- | --- | --- |
| `bronze_public_participation_from_ai` (changed) | meeting × speaker × item | `source_event_id_speaker_id` | adds `decision_id`, `stance_evidence`, `speaker_role`, `heat`; the key gains the item id when present |
| `public_comment` (new) | meeting × speaker × item | `public_comment_id` | `stance`, `stance_bucket`, `heat`, `speaker_role`, quote, timestamps, `state_code` and `state`, `video_id`; links to `event_meeting` and, when it is a contested decision, `event_decision` |
| `decision_public_stance` (new) | decision | `event_decision_id` | `speakers_for`, `speakers_against`, `speakers_question`, `speakers_neutral`, `speakers_total`, `stance_balance`, `heat_mean`, `heat_max`; each speaker counts once |

`public_stance_bucket()` is the one macro that maps stance text to a bucket; a value outside the vocabulary maps to
null, not neutral. `public_comment.event_meeting_id` is an enforced foreign key. A decision with no public-comment data has
**no row**, so the page shows "No public-comment data for this meeting", never a neutral bar. The foreign keys into
`event_meeting` and `event_decision` are relationships tests because those tables are partitioned with composite keys
(the same convention as `decision_speakers`).

### Coverage by tier

| Tier | Has | Stance available |
| --- | --- | --- |
| **Full** | decisions, people, named voices, views, room mood, timestamps | per speaker per item, with summary and time |
| **Light** | summary, decisions, uncontested items | per speaker per item, with quote; no summary or time |
| **Screen only** (Jev screen, blurb) | meeting kind and topic probabilities | none until the passage pass below |
| **Analysed before this prompt version** | whatever its tier had | none: shown as "no public-comment data". Never inferred from the outcome |

The light prompt in the repository has no people list, so a light speaker is identified only by the slug built from the
name as spoken. Speakers who are never named are skipped, which undercounts public comment in every tier; the page says
"named speakers".

Not built yet: an `analysis_tier` column on these marts. The tier is known from the analysis metadata
(`prompt_name`), but it is not carried into `event_meeting` today; it needs its own issue before tiers are compared.

## Pilot: 20 full and 20 light meetings (owner, 2026-11-24)

Purpose: see real output on real pages before spending on a wider run.

- **Selection, by rule, not by hand:** meetings with a transcript where the Jev screen says a data center is discussed
  and decisions were made (both probabilities at least 0.5); at most one meeting per county and two per state; ordered
  by a hash of the video id so the list is reproducible. Take the first 40.
- **Runs:** light analysis on all 40 (the batch design already requires light before full), then full analysis on 20
  of them. That gives 20 light-only meetings, 20 full meetings, and **20 meetings read by both tiers**, which is a free
  agreement check between two different models on the same recording.
- **Cost (estimate, to be replaced by the usage report):** full is about $0.012 per meeting from logged usage, so
  about $0.25 for 20 plus a few cents for the added rows; light on 40 is cents. Under $1 in total. The owner approved
  this pilot in the session on 2026-11-24; read `python -m llm.usage.report` before and after and put the figures in
  the pilot's issue.
- **Output:** a pilot report page under `web_docs/docs/development/` listing every meeting with its state, county,
  tier, the number of speakers in each bucket, and a link to each decision page, plus the results of the checks below.
- **What must exist first:** the stance has to be readable on the page. That is the API field and the
  `DecisionDetail` bar and chips (phase 2 below). Publishing to the live site is a production deploy and stays the
  owner's call.
- **Where it runs:** on the machine that reaches the warehouse (`localhost:5433`). This cloud session cannot reach it.

## Checks (automated, no human labeller)

`AGENTS.md` asks for checks "against known answers, not by asking another model whether the result looks right".

| Check | How | Proves | Does not prove |
| --- | --- | --- | --- |
| 1. Quote is real | code confirms each `stance_evidence` appears in that meeting's transcript (case and whitespace normalised) | the evidence was not invented | that the stance label is right |
| 2. Quote matches the label | transparent phrase rules on the quote ("vote no", "I oppose", "please approve", "I support") give a side; compare with `stance` | accuracy where the speaker was explicit | subtle or implied stance |
| 3. Constructed cases | a fixed set of short transcripts with the answer built in (support, opposition, conditions, a question, a staff presentation, negation, sarcasm), kept in tests only | the prompt wording behaves; catches regressions | real-world accuracy |
| 4. Two tiers, same meeting | the 20 pilot meetings read by both light and full: do they find the same speakers and the same side | where two different models disagree | ground truth (they can share a blind spot) |
| 6. Heat matches the words | phrase rules on the quote and summary: explicit threats, insults or "I am furious" must not sit at 1 or 2; a bare question must not sit at 4 or 5; plus constructed cases at each level | gross heat errors and drift between prompt versions | fine distinctions between neighbouring levels |
| 5. Outcome smoke test | decisions the body denied should lean against among public speakers on average | gross errors | cause and effect |

Checks 1, 2 and 6 are built (#818) as a package CLI that reads one analysis file and its transcript, with no network,
database or model call:

```bash
python -m llm.gemini.public_comment_checks --analysis analysis.json --transcript transcript.txt
```

It exits non-zero when a bar is missed and lists each row that failed a check. Several analysis and transcript pairs
can be given at once and are added into one report, which is how the pilot is judged. Check 2 only counts quotes that
state a side in plain words, with negations handled ("do not support" reads against, "not opposed" reads for). A quote
that hedges, sets a condition, states both sides or asks a question is counted neither way, because a wrong reading is
worse than a missed one. Quotes under three words are not counted as evidence, and the flip-rate bar is applied only
once there are 20 side-stating quotes; a quote that is not in the transcript fails at any sample size. Checks 3
(constructed transcripts run through the model), 4 and 5 need a model run or the warehouse and are not built.

Bar to show the numbers (best judgement; change with a dated line under Decisions): check 1 at least 98 of 100 quotes
found; check 2 at most 5 of 100 wrong-side flips (a quote that says "oppose" on a row marked For, or the reverse);
check 3 at least 95 of 100 with no wrong-side flip. Checks 4 and 5 are reported. A row failing check 1 is dropped
from the counts. If a bar is missed, the wording is changed and the checks re-run; the metric does not ship.

The page caption says: "Stance is estimated automatically from named public speakers and checked against their quoted
words, not reviewed by people."

## On the site

- **Decision page:** a stance bar above "Voices in the room" (`Against n | Questions n | Neutral n | For n`), a stance
  chip, a heat marker and the role on each speaker, the quoted words with the matched phrase highlighted, and the timestamp link where one exists.
- **Filters** (browse and search surfaces): Stance (Opposed, In favor, Asked questions, Neutral), How heated (1 to 5)
  and Speaker role, each with its count, read from `public_comment`. The active filter is named in the scope label and
  carried in the URL, and every result shows the quoted words that put it there.
- **Colour:** against is vermilion, for is blue, neutral is white or light gray with dark text; segments are always
  labelled, so colour is never the only signal. Confirm the pair with a colour-blind simulation.
- **Matrix map:** `public_comment_for_share`, `_neutral_share`, `_against_share` and `public_comment_balance` join the
  meeting-metrics catalog. The Dot map and Tiles colour by the balance; the Share bar shows the three shares; every
  value shows how many speakers and meetings it rests on and obeys the minimum-sample rule.
- **Wording:** "named speakers at meetings we have analysed", never "how residents feel". People who speak at meetings
  are self-selected.

## Later: reaching meetings that are not analysed

Screen-only meetings have no decisions or speakers. For those, Jev can rate **passages** that mention a topic
(`data_center_meeting_mention`, about three minutes each, with a verbatim excerpt and a timestamp):

- one Jev request per passage, asking whether a member of the public is speaking and the stance on a five-step scale,
  mapped to the same three buckets;
- gated on the existing screen (`mentions_data_center_p`), so meetings with no data-center talk cost nothing;
- about $0.00004 per passage (about 900 input tokens at $0.042 per million), so roughly $0.50 to $2 for 12,000 to
  50,000 passages. These counts are assumptions until a dry run counts the real passages;
- kept separate (`unit = passage`) and never merged with speaker counts, because a passage can hold several speakers.

This waits until the pilot shows the speaker-level numbers are worth extending.

## Constraints

- **Do not use American Sentiment's (or ProphecyGov's) data.** `community_events.py` blocks `americansentiment.com`
  and `prophecygov.com` because their terms forbid competitors' use. Stance comes from our own transcripts only.
  Peers are listed under [Proprietary competitors](../data-sources/citations.md#proprietary-competitors)
  ([American Sentiment](../data-sources/citations.md#american-sentiment),
  [ProphecyGov](../data-sources/citations.md#prophecygov)).
- **Paid runs need the owner's yes for that run** (`AGENTS.md`). The pilot has it; a wider run does not.
- **No fabricated data:** no stance without a row, no row without a named speaker, no quote that is not in the transcript.
- **Auto-captions** have no speaker labels and often garble names, so some speakers will be missed or split in two.

## Phasing

1. **Done in code (2026-11-24), not yet run:** `public_participation[]` in both prompts; `PublicComment` in
   `llm.gemini.part1_schema` with tests; the bronze change, `public_stance_bucket()`, `public_comment` and
   `decision_public_stance`. The rendered SQL of the three models ran on a scratch PostgreSQL 16 with test-only rows
   (contract columns and types, keys, buckets and heat all as designed). `dbt build` against the warehouse has not run.
2. Build the dbt models against the warehouse; add the stance fields to the decision API; bar and chips on
   `DecisionDetail`; checks 1 to 3 as a package CLI with tests.
3. Run the 40-meeting pilot, write the pilot report with links, and decide from it.
4. Wider runs on new analyses (the prompt now emits stance on every new meeting), catalog entries, Matrix map layers.
5. Passage pass for screen-only meetings; `analysis_tier` on the marts; comment-level segmentation as its own project.

## Decisions

Change any of these by adding a dated line, not by rewriting.

| Date | Decision | By |
| --- | --- | --- |
| 2026-11-24 | Data centers are the first topic. | owner |
| 2026-11-24 | A gradient, reported in three buckets (against, neutral, for), because some comments are neither. | owner |
| 2026-11-24 | No human labelling; checks must be automated. | owner |
| 2026-11-24 | Extend the existing extraction rather than add a separate pass; handle light meetings too. | owner |
| 2026-11-24 | Pilot 20 light and 20 full meetings from different counties and states, with linked pages, before anything wider. | owner |
| 2026-11-24 | Carry stance in `public_participation[]` (one row per public speaker per item) instead of `personal_stories`; drop the per-speaker five-step strength; unknown is not neutral; no backfill by inference. | review, best judgement |
| 2026-11-24 | Pilot runs light on all 40 and full on 20 of them, so 20 meetings are read by both tiers. | review, best judgement |
| 2026-11-24 | Track stance including "Asked questions", how heated (1 to 5) and speaker role per comment, in both the light and the full analysis. | owner |
| 2026-11-24 | Heat is judged from words by a shared five-level rubric and reported as a distribution, mean and maximum per decision; roles come from a fixed list and are never inferred. | review, best judgement |
| 2026-11-24 | Check bars: 98 of 100 quotes found, at most 5 of 100 wrong-side flips, 95 of 100 constructed cases. | review, best judgement |

## Open questions

- Should council members' and staff positions be shown beside the public bar, from `competing_views.held_by` and the
  vote, or kept separate as now?
- How to carry `analysis_tier` into `event_meeting` (needs an issue).
- Whether unnamed speakers ("a resident on Oak Street") should be counted with a generated slug; today they are skipped.
