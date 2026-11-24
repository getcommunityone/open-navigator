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

## How the calls are structured (not per person)

- **Captions carry no speaker labels**, so a meeting cannot be split by person. The person-level information that
  exists (`decision_speakers`, `event_decision.human_element->'personal_stories'`) comes from the Gemini extraction, not from
  the transcript.
- **The unit is the passage, one Jev request per passage.** A passage is the same ~3-minute window
  `data_center_meeting_mention` already cuts. All the stance questions go in that one request. A passage can hold
  several speakers; the answer describes the public comment in that window as a whole, and a window with both
  sides lands in the neutral/mixed bucket. Shorter windows (60 to 90 seconds) would separate speakers better at a
  small extra cost; try that if validation shows many mixed passages.
- **Not by decision.** Decisions are the unit of the Gemini extraction, but a decision's discussion is spread across
  the meeting and has no stable text span, so passages are the cleaner unit. A passage can be linked to a decision
  later by time overlap.
- **Existing Jev screening is a gate, not the host.** `screen_transcripts` sends up to 4 evenly spaced chunks per
  video and takes the highest `mentions_data_center` probability, which is right for "is this meeting relevant" but
  would miss most data-center passages for stance. So the stance pass runs as its own module on the stored
  mention passages, and only for videos the screen already marked as discussing data centers. That keeps the cost
  down and reuses the same client, usage table and run pattern (`llm.typesafe.client.JevClient`).

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

## Validate before showing anything (fully automated, no human labeller)

There is no person to label passages, so validation is a suite that runs from code (`python -m
llm.typesafe.passage_stance_validate`, tests in `packages/llm/tests/`). `AGENTS.md` says prompts are checked
"against known answers, not by asking another model whether the result looks right", so no layer below is "an LLM
judges the output". Each layer proves something different, and the site says which layers a metric has passed.

**What "agreement" means:** out of every 100 passages in a test set, how many did Jev place the same way as the known
answer. "Within one step" allows a one-rung miss on the five-step scale; a **wrong-side flip** is "for" where the
answer is "against", or the reverse.

| Layer | Known answer comes from | What it proves | What it can't prove |
| --- | --- | --- | --- |
| 1. Constructed cases | A fixed set of short passages written in the repo with the answer built in ("I strongly oppose this data center", "please approve the rezoning", a staff presentation, a time-limit reminder, negation, sarcasm, hedges, a question). Lives in the test folder only, never served | The question wording and rubric behave as intended; catches regressions when the question set or Jev model changes | Real-world accuracy: real passages are messier |
| 2. Explicit-statement set | Real passages where a speaker states a side in plain words ("I am opposed", "vote no", "I support this project"), found by transparent phrase rules over our own transcripts. The rule gives the label | Accuracy on real caption text where the answer is unambiguous | Subtle or implied stance (the hard cases are excluded by construction) |
| 3. Stability | The same passage re-run, cut at different window edges, and with filler words dropped | Answers don't flip on trivial changes | Whether the answer is right |
| 4. Second reader | Gemini, which already analyses these meetings, asked the stance question independently on a sample | Where two different systems disagree, so those passages are flagged and excluded from headline counts | Ground truth: two models can share a blind spot, so this is reported as agreement, never as accuracy |
| 5. Outcome sanity | Decisions the body itself denied or put on a moratorium (`question_outcome_family`) | Places with denied decisions should lean against on average; a strong contradiction is a bug signal | Cause and effect: boards vote for many reasons, so this is a smoke test only |

**Bar to ship the metric** (best judgement; change it with a dated line):

| Check | Needed |
| --- | --- |
| Layer 1, exact match | at least 95 of 100, and zero wrong-side flips |
| Layer 2, within one step | at least 90 of 100, and at most 5 of 100 wrong-side flips |
| Layer 3, unchanged label under a trivial edit | at least 90 of 100 |
| Layer 4, Gemini and Jev on the same side | reported; passages where they disagree are held out of the counts |
| Layer 5 | reported, not gating |

If a layer fails, the metric does not ship: reword the question or rubric and re-run. The report is written to a table
with the question-set version and Jev model id, so every published number can be traced to the test run that cleared it.

**Be honest on the page.** With no human check, the caption says: "Stance is estimated automatically and checked
against constructed and explicit-statement test cases, not by people." Every tile also shows the quoted passage
with a link to the video at that time, so a reader can judge it themselves.

**Humans can still help later, passively.** A "this label looks wrong" button on the quoted passage logs a flag
(per `AGENTS.md`, feedback becomes issues). Flags feed Layer 2's set over time without anyone having to sit and
label.

## Cost and approvals

Jev bills input tokens only: $0.042 per million, output free (see transcript screening). Stance runs **only on
data-center passages**, not on whole meetings, so long or boring meetings with no data-center talk cost nothing extra.

Per request: a ~3-minute passage is about 600 tokens, plus about 300 tokens of question text, so about 900 tokens,
which is about **$0.00004 per passage**. All figures below are my arithmetic from stated assumptions; the real
counts come from the dry run (`--dry-run` counts passages and estimates tokens without sending anything).

| Scenario (200,000 meetings) | Passages sent | Tokens | Estimated cost |
| --- | --- | --- | --- |
| **Gated (recommended):** only videos the screen marked as discussing data centers. Assume 2% to 5% of meetings, 3 to 5 passages each | 12,000 to 50,000 | 11M to 45M | **about $0.50 to $2** |
| Every passage of every meeting (no gate), assuming 40 passages for a 2-hour meeting | 8,000,000 | 7.2B | about $300 (about $0.0015 per meeting) |
| Re-run after a wording change, gated | same as gated | same | about $0.50 to $2 each time |
| Gemini second-reader sample (validation Layer 4), about 500 passages | 500 | small | under about $1 (price from the usage tables; confirm with a dry run) |

What drives it: how many passages mention data centers, not how many meetings we have. Even the ungated worst case
is a few hundred dollars, and the gated plan is a couple of dollars. A Jev run is still a paid LLM endpoint, so under
`AGENTS.md` **it starts only with the owner's yes**, and the cost goes in the run's issue or PR. Read usage before
and after with `python -m llm.usage.report`.

Why this stays cheap: the gate already exists (`mentions_data_center_p` from the screen), stance reuses stored
passages, answers are cached in the bronze table so a passage is never re-sent unless the question-set version
changes, and a hard `--max-passages` cap on the CLI stops a run that is bigger than expected.

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

1. Build the question set, the `passage_stance` CLI and the validation suite; Layer 1 and the Layer 2 phrase rules run with no spend.
2. Owner approves a small paid run (Jev, plus a small Gemini sample for Layer 4); measure agreement and cost.
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
| Agreement bar | The layered automated bar above (owner has no person to label, 2026-11-24). Best judgement; change it by adding a dated line here. |

## Open questions

- Confirm the vermilion and blue pair with a colour-blind simulation before the design is final.
- Where to draw the line between neutral and a weak side (rung 0 only, or also low-confidence sides); decide from the validation sample.
