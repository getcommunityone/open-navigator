---
title: Meeting sentiment with Jev
sidebar_label: Meeting sentiment (Jev)
description: How to add public-comment stance ("sentiment") to the meeting data with Jev, what unit to measure, how to validate it, and how it feeds the Matrix map dot map.
---

# Meeting sentiment with Jev

Status: **proposal** (not yet built). Decided 2026-11-24: **data centers first**; stance is scored on a **five-step gradient** and reported in **three buckets** (against, neutral, for). Builds on [Meeting metrics for the Matrix map](./meeting-metrics-matrix-map-design.md)
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
| `stance_on_project` | Score, five rungs, lowest first: strongly opposes, opposes, neutral or mixed, supports, strongly supports | the stance gradient (see below) |
| `is_procedural` | Noul: "The passage is only about process (agenda order, time limits), not the project" | keeps procedural talk out of the gradient |

Store the **probabilities**, not just the winning label, and derive labels with a documented threshold.
Count a passage toward the stance share only when `is_public_comment` is high enough (start at 0.7, tune on the
validation set).

## The sentiment gradient and the three buckets

Jev's Score question rates on an ordered rubric of 2 to 10 rungs, so stance is a gradient from the start rather than a
yes/no label. Use five rungs: strongly opposes, opposes, neutral or mixed, supports, strongly supports (−2 … +2).

Many passages are not for or against anything: a staff presentation, a question, a time limit, a procedural vote.
Forcing those onto a side would invent an opinion. So the **headline is three buckets**, like a Left / Center / Right bar:

| Bucket | Rungs | Also includes |
| --- | --- | --- |
| **Against** | strongly opposes, opposes | |
| **Neutral** | neutral or mixed | any passage Jev flags `is_procedural`, and any passage with no clear stance |
| **For** | supports, strongly supports | |

The three shares always add to 100% of the counted passages, so the bar is complete. The five-step gradient is kept
underneath for detail: it sets the shade within a bucket (strong is darker than weak) and drives the diverging view.

- **Primary view, the three-segment bar:** one stacked bar per place, `Against 30% | Neutral 43% | For 27%`, each
  segment labelled with its share and its passage count on hover. This is the same form as the Folio
  100% stacked bar and the Share layout, and it needs no scale to learn.
- **Colour:** against = vermilion, for = blue, neutral = white or light gray with dark text. A blue and orange-red pair
  stays distinguishable for colour-blind viewers, which red and green does not. Always label the segments, never
  rely on colour alone.
- **One number for a map or tile:** the *balance* among passages that take a side,
  `(for − against) / (for + against)`, from −100% to +100%. Neutral passages are left out of the balance (otherwise
  a place where most talk is procedural would always look "neutral"), but the neutral share is shown beside it so
  nothing is hidden. Show `—` when fewer than the minimum number of side-taking passages exist.
- **Dot map and Tiles** colour by the balance on a diverging scale with a neutral midpoint, with lightness changing as
  well as hue.
- **Diverging bars (the template's Likert chart)** show all five rungs for one place, centred on neutral, for readers
  who want the full gradient.
- **Compare** shows how a place's balance moved between years, once there are two years.
- Store the answer **probabilities per rung**, use the highest-probability rung as the label, and compute buckets
  and shares from the labels so they are reproducible.

## Pipeline (follow the repo rules)

1. **Code:** a package CLI module, `python -m llm.typesafe.passage_stance` (argparse `main()`), next to
   `light_blurb.py`. Nothing goes in `scripts/`.
2. **Bronze:** a table of raw Jev answers keyed by passage, with the question-set version, Jev model id, run id and
   call cost. The question text lives in git with a version number, and the version changes when it does.
3. **dbt:** staging, then a `public` mart such as `meeting_passage_stance` (primary key = passage id, foreign keys to
   the passage, jurisdiction and event). Carry the source forward: every row keeps `video_url`, `start_seconds` and the
   verbatim `evidence`.
4. **Metrics:** add to the meeting-metrics catalog: `public_comment_passages` (additive count),
   `public_comment_against_share`, `public_comment_neutral_share`, `public_comment_for_share` (rates that add to 100%,
   numerator and denominator stored) and `public_comment_balance` (for minus against among side-taking passages, −100% to +100%),
   always with `coverage_n` and the minimum-sample rule already decided (10 decisions or passages, 3 jurisdictions).
5. **UI:** the Dot map colours each state by the balance (a diverging scale centred on even) and a three-segment bar shows the three shares,
   drills into counties, and every tile shows the quoted passage with the matched words highlighted, per the
   "Show the Match Evidence" rule. Nothing is shown without a real quote behind it.

## Validate before showing anything

Do this before the number appears on the site (same approach as [meta-gate validation](./jev-meta-gate-validation-design.md)).

**The test, in plain terms.** Take about 200 passages. A person reads each one and picks a rung on the five-step
scale, without seeing what Jev said. Then compare. "Agreement" just means: *out of every 100 passages, how many did
Jev and the person place the same way?* Two ways to count it:

- **Exact match:** both picked the same rung. This is strict. On a five-step scale even two careful people often
  differ by one step ("opposes" vs "strongly opposes"), so do not expect near 100%.
- **Within one step:** Jev is at most one rung away. This is the fair test for a gradient.

The number that matters most is the **flip rate**: how often Jev says "supports" when the person says "opposes",
or the reverse. A wrong-side error is what would mislead a reader.

**Proposed bar to ship** (replaces the earlier 80% placeholder, which only made sense for a yes/no label):

| Check | Needed |
| --- | --- |
| Within one step of the person | at least 90 of 100 |
| Wrong-side flips (support vs oppose) | at most 5 of 100 |
| Exact match | report it, no minimum; compare with how often two people agree with each other, using a second labeller on 50 passages |

If Jev does not clear the bar, we do not ship the metric; we change the question wording or the rubric and
re-test. Re-run this whenever the question set or the Jev model changes. Auto-captions have no punctuation or
speakers, so expect `is_public_comment` to be the weakest question; test it the same way.

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

## Decisions

| Question | Decision |
| --- | --- |
| First topic | **Data centers** (owner, 2026-11-24): the mention table already has evidence, timestamps and site links. |
| Scale | **Five-step gradient** (owner asked for a gradient, 2026-11-24), not a yes/no label. |
| Buckets | **Three: against, neutral, for** (owner, 2026-11-24): some passages are neither. Neutral includes procedural and no-clear-stance passages and is shown, not dropped. |
| Wrong-side flip | A flip is now support vs against; a passage moving between neutral and a side is one step, not a flip. |
| Agreement bar | At least 90 of 100 within one step, at most 5 of 100 wrong-side flips (best judgement, owner had no preference; the plain-language explanation is above). Change it by adding a dated line here. |

## Open questions

- Confirm the vermilion and blue pair with a colour-blind simulation before the design is final.
- Where to draw the line between neutral and a weak side (rung 0 only, or also low-confidence sides); decide from the validation sample.
