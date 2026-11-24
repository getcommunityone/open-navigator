---
title: Meeting sentiment with Jev
sidebar_label: Meeting sentiment (Jev)
description: How to add public-comment stance ("sentiment") to the meeting data with Jev, what unit to measure, how to validate it, and how it feeds the Matrix map dot map.
---

# Meeting sentiment with Jev

Status: **proposal** (not yet built). Builds on [Meeting metrics for the Matrix map](./meeting-metrics-matrix-map-design.md)
and the existing Jev work ([transcript screening](./jev-transcript-screening.md),
[Jev-light cascade](./jev-light-cascade-design.md)).

## Can Jev do it?

Yes, for the classification part. Jev is TypeSafe's System One model (`packages/llm/src/llm/typesafe/client.py`).
One call sends a block of text plus named questions and returns **one typed answer per question**: a Choice
(one label), a Score (a rung on an ordered rubric), or a Noul (probability a statement is true). It returns labels
and probabilities, never text. That fits stance well and does not fit extraction, which stays with Gemini.

"Sentiment" here means **stance toward the item under discussion** (supports, opposes, mixed), not emotional tone.
General tone ("angry", "polite") says little about whether a community backs a data center.

## What the unit of measurement is

The inspiration map (American Sentiment) draws one dot per public comment. **We cannot do that yet:** we have
transcripts, not comment-level records, and caption files carry no speaker boundaries. What we do have:

| Unit | Source | Good for |
| --- | --- | --- |
| Passage (about 3 minutes of caption cues) | `data_center_meeting_mention` (`evidence`, `start_seconds`, `video_url`) | v1: stance on data centers, with a timestamped quote |
| Decision | `event_decision` (`competing_views`, `human_element`, `vote_tally`) plus `decision_speakers.speaker_count` | stance by decision, only where views were extracted |
| Whole transcript | `event_documents` | too coarse for stance |

**Recommendation: v1 measures passages, starting with data centers**, because that mention table already has
verbatim evidence, a timestamp and a site link. Label it honestly as "public-comment passages", not "comments".
Moving to true comment units needs speaker segmentation, a separate project.

## Questions to ask Jev, per passage

All in one request per passage (cheap, and the passage is read once):

| Question | Type | Purpose |
| --- | --- | --- |
| `is_public_comment` | Noul: "A member of the public is addressing the body during this passage" | keeps staff presentations and board debate out of the public-opinion number |
| `speaker_role` | Choice: public commenter, elected official, staff, applicant or developer, other | context for each passage |
| `stance_on_project` | Choice: support, oppose, mixed, neutral or procedural | the stance label |
| `stance_strength` | Score: weak to strong | optional, to weight or filter |

Store the **probabilities**, not just the winning label, and derive labels with a documented threshold.
Count a passage toward the stance share only when `is_public_comment` is high enough (start at 0.7, tune on the
validation set).

## Pipeline (follow the repo rules)

1. **Code:** a package CLI module, `python -m llm.typesafe.passage_stance` (argparse `main()`), next to
   `light_blurb.py`. Nothing goes in `scripts/`.
2. **Bronze:** a table of raw Jev answers keyed by passage, with the question-set version, Jev model id, run id and
   call cost. The question text lives in git with a version number, and the version changes when it does.
3. **dbt:** staging, then a `public` mart such as `meeting_passage_stance` (primary key = passage id, foreign keys to
   the passage, jurisdiction and event). Carry the source forward: every row keeps `video_url`, `start_seconds` and the
   verbatim `evidence`.
4. **Metrics:** add to the meeting-metrics catalog: `public_comment_passages` (additive count),
   `public_comment_oppose_share` and `public_comment_support_share` (rates, numerator and denominator stored),
   always with `coverage_n` and the minimum-sample rule already decided (10 decisions or passages, 3 jurisdictions).
5. **UI:** the Dot map colours each state by the oppose-to-support balance (a diverging scale centred on even),
   drills into counties, and every tile shows the quoted passage with the matched words highlighted, per the
   "Show the Match Evidence" rule. Nothing is shown without a real quote behind it.

## Validate before showing anything

Do this before the number appears on the site (same approach as [meta-gate validation](./jev-meta-gate-validation-design.md)):

- Hand-label a random sample of about 200 passages (stratified by state and by source type), without showing the
  Jev answer.
- Report agreement per question (accuracy and a confusion table), not one headline number. Pick the threshold from
  this set. Re-run it when the question set or Jev model changes.
- Auto-captions have no punctuation or speakers, so expect weaker results on `is_public_comment` than on
  `stance_on_project`. If agreement is poor, do not ship the metric; surface that.

## Cost and approvals

Jev costs $0.042 per million input tokens and output is free (see transcript screening). A 3-minute passage is
roughly 600 tokens, so about $0.000025 per passage, or roughly $2.50 per 100,000 passages (an estimate; read the
real number from `python -m llm.usage.report` after a small run). That is small, but a Jev run is a paid LLM
endpoint, so under `AGENTS.md` **it starts only with the owner's yes**, and the cost goes in the run's issue or PR.

## Constraints and risks

- **Do not use American Sentiment's data.** `community_events.py` blocks `americansentiment.com` and
  `prophecygov.com` because their terms forbid competitors' use. This design computes stance from our own
  transcripts only.
- **Coverage bias** applies even more here: shares from a few passages swing widely, so the minimum-sample rule and
  the "low coverage" hatching are required, not optional.
- **Association, not opinion polling.** Speakers at meetings are self-selected. The caption must say "passages from
  public comment at meetings we have transcripts for", never "how residents feel".
- **Mixed or sarcastic remarks** will be misclassified sometimes. The evidence quote lets a reader judge.

## Phasing

1. Build the question set and `passage_stance` CLI; dry-run on a small sample (no cost) and hand-label it.
2. Owner approves a small paid run; measure agreement and cost.
3. Mart, metric catalog entries, and the Dot map layer.
4. Extend beyond data centers by topic, one validated question set at a time.
5. Separate project: comment-level segmentation so one dot can mean one comment.

## Open questions

- Is data centers the right first topic? (It has the evidence table today; housing and zoning have the Jev-light flags.)
- What agreement level is good enough to ship? Suggest at least 80% on `stance_on_project` among confident public-comment passages.
