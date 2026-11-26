---
sidebar_position: 62
title: Data center meeting lean
description: How the story maps read the public's and officials' lean on data centers from Jev's screen of each meeting, the thresholds, the hand checks and the limits (#1113, #1117).
---

# Data center meeting lean (AI reading)

Counted speaker stance (`data_center_meeting_position`) covers only a few states. To show more of the country, the data
center story maps also show **Jev's reading** of each meeting where a data center came up
([#1113](https://github.com/getcommunityone/open-navigator/issues/1113),
[#1117](https://github.com/getcommunityone/open-navigator/issues/1117)). Jev is a cheap yes/no and multiple-choice
transcript classifier (`packages/llm/src/llm/typesafe/screen_transcripts.py`). It returns probabilities, never text, so
every value here is an AI reading of a transcript, not a count of speakers. The maps label it that way.

## The questions

Jev answers these per meeting (`bronze.bronze_transcript_screen_jev`):

| Column | Question, in short | Answers |
|---|---|---|
| `dc_public_lean` | How did **members of the public** lean on a large data center facility? Officials, staff, consultants and the applicant don't count; IT equipment or a records "data center" doesn't count. | `mostly_opposed`, `mostly_supported`, `mixed`, `no_public_comment_on_data_center` |
| `dc_official_lean` | How did **elected officials** lean? | `mostly_supportive`, `mostly_opposed`, `divided`, `no_official_position` |
| `dc_outcome` | What happened to the data center item? | `approved`, `denied`, `moratorium`, `tabled_or_deferred`, `discussed_no_action`, `no_data_center_item` |
| `dc_project_approved_p` | P(the approved item was a specific data center project, not rules limiting data centers) | 0–1 |

Only rows under the **current question version** are used: the version with the latest `screened_at`
(`stg_jev__transcript_screen.is_current_question_version`). It isn't hardcoded, so a reworded question takes over as
soon as its first rows land; older versions asked differently worded questions and aren't mixed in.

## The two readings shown

`data_center_meeting_lean` (gold, published to `public`; PK `video_id`, FK `jurisdiction_id` → `jurisdictions`) has one
row per meeting video in `data_center_meeting_mention` with a current screen, and two flags:

- **`public_against`**: `public_lean = 'mostly_opposed'` with probability ≥ 0.7.
- **`officials_sided_against_public`**: the public mostly opposed **and** officials mostly supportive **and** the outcome
  is not `moratorium` or `denied` **and** it isn't approving rules (`dc_outcome = 'approved'` with
  `project_approved_p` < 0.3 doesn't count).

The API sums them per state (positions `by_state`, national, never narrowed by the scope) and per government
(meeting-mentions `by_place`) as `public_against_meetings` and `disagreement_meetings`. If the table is missing the
counts are 0 and nothing fails.

On the maps, an area with **no counted speakers** and at least one public-against meeting is a lighter tint of the
Spoke against red; disagreement meetings are not drawn on the map (no outlines, at the owner's request) but are stated in the hover card, readout and data table. Counted speakers always win the fill.

## Hand checks (#1113)

- First run (1,830 meetings, about $1.76): of 8 sampled "opposed", 6 right, 1 ambiguous, 1 wrong (a juvenile records
  "data center"). "Supported" was 3 of 7 right and "mixed" 1 of 5; confidence (0.82–0.98) didn't separate the wrong ones.
- Second run, questions split into public and officials and limited to large facilities (1,829 meetings, $1.85): 32
  states had a public-opposed meeting at p ≥ 0.7. "Supported" and "mixed" stayed weak (about 2 of 4 right).
- Disagreement defined as public opposed and (officials supportive or outcome approved) gave 44 meetings; a check of 10
  found about 5 plausible, 4 false and 1 unclear. The false ones approved rules or a moratorium, which is why the rule
  now needs officials supportive, excludes moratoriums and denials, and asks Jev whether an approval was a specific
  project (`dc_project_approved_p`, filled by the third re-screen).

So only "public leaned against" (about 7 of 8 right) and the refined disagreement rule are shown.

## Decision: the headline gates on confident "against" only (#1134)

The data-center story's **America hates data centers.** used to rest only on 29 hand-counted speakers in 4 states. It
may now also pass on this reading: confident (p ≥ 0.7) "public leaned against" meetings of at least **50 nationally,
10 for a state and 3 for a city or other single place** (a single government holds few data center meetings, so 3
separate meetings is the least that is more than one evening's crowd). Because "supported" and "mixed" failed the hand
checks above, the gate does **not** compare against them (no "against ≥ 2× for/mixed" ratio), and the sentence states
only the against count: "The public leaned against data centers in 283 meetings across 32 states (AI reading of
meetings)." The confident for, mixed and spoke counts are served on positions `lean_totals` / `scope_lean_totals`
(`public_for_meetings`, `public_mixed_meetings`, `public_spoke_meetings`, same p ≥ 0.7) for audit only. On 26 Nov 2026
they were 14, 7 and 304 nationally; the 1,449 confident "no public comment" meetings are not counted as spoke.

## Decision: one title from the caption picker (#1134, #1125)

The title for every view of the story (home hero, story header, Overview) comes from one function, `pickCaption`
(`web_app/src/utils/storyCaption.ts`; thresholds in [Story captions](story-captions.md)): "hates" first (the gates
above, or the speaker gate), then "is divided on" (officials sided against the public in at least 10 meetings, or counted
speakers split with both sides substantial), then volume and the question. A place gets exactly one title. "Divided" and
"hates" never rest on the "supported" or "mixed" readings. On 26 Nov 2026 no Alabama scope reached a conclusion: the
state had 6 confident public-against meetings (under 10) and no officials-sided meeting, and Tuscaloosa had none.

## Limits

- It is a classifier's reading of a transcript. A meeting can be misread; the hover line says "AI reading" and the
  legend says "AI reading of meetings".
- "Supported" and "mixed" public leans are kept in the mart for audit but never served on a map, so the maps can only
  show opposition, never support, from this source. Support shows only where speakers are counted.
- Coverage follows the screen: while a re-screen under a new question version is running, only the meetings already
  screened under it count, so the numbers grow as it finishes.
- A meeting is placed by its government; a meeting whose government isn't in `jurisdictions` counts for its state but
  isn't on the county map.
