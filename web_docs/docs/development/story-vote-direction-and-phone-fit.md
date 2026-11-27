---
sidebar_position: 64
title: Story vote direction, speaker sources and phone fit
description: How story headlines read which way a recorded vote went, how the three speaker sources are reconciled, where the topic control sits in a title, and how each story screen fits a phone (#1290).
---

# Story vote direction, speaker sources and phone fit

**Issue:** [#1290](https://github.com/getcommunityone/open-navigator/issues/1290), following
[#1289](https://github.com/getcommunityone/open-navigator/issues/1289) (PR #1298), which added the stance minimum, the vote
check and the shared display rule. **Code:** `dbt_project/models/marts/data_center_decision.sql` (`vote_side`),
`api/routes/topic_caption_facts.py`, `web_app/src/utils/stanceEvidence.ts`, `web_app/src/utils/storyCaption.ts`,
`web_app/src/components/stance/useScreenFit.ts`.

## 1. Which way a vote went, not whether it passed

#1289 read a recorded vote as "for" when the motion passed and summed yes and no votes over a scope. A motion can restrict
data centers: nationally 11 of the 12 tallied decisions passed (79–10), but 5 of them were moratoriums or a denial
(Manitowoc County's 18-month moratorium passed 23–0). The summed votes turned "America hates data centers." into "America is
divided on data centers." on the strength of moratoriums.

**Decision.** `data_center_decision.vote_side` (dbt, a keyword reading of the item's own words, not a model's) says which way
each tallied vote went for the data center:

| Motion | Passed | Failed |
|---|---|---|
| Pause, ban or prohibit (`moratori`, `ban`, `prohibit`, `pause` in the headline) | `against` | `for` |
| Lifting, ending, repealing or rejecting a pause or ban (with a pause word in the headline) | `for` | `against` |
| An outcome of denied or rejected | `against` | `against` |
| A motion to deny (`deny`, `reject` in the headline only) | `against` | `for` |
| Anything else (approve, rezone, adopt rules, delay) | `for` | `against` |

Null without a tally recording both a yes and a no count, and on a tie. Alabama's one vote ("Data Center Zoning Ordinance
Delayed for Further Review", 8–1) is `for`, the owner's reading ("it can never read opposes").

The caption facts carry the counts as `votes.decisions_for` / `votes.decisions_against` (null when a serving copy lacks the
column). The votes **lean** a way when one side has two thirds of the tallied decisions (`VOTE_LEAN_SHARE`); mixed votes lean
neither way. Nationally (7 for, 5 against) the votes are mixed, so the title about the public stands: "America hates data
centers." A title against a clear lean still becomes "[Place] is divided on [topic].", its line opening "Recorded votes went
the other way: 3 of 3 decisions with a recorded vote went for data centers." An older server without the sides falls back to
#1289's summed votes.

## 2. Three speaker sources, reconciled

| Source | What it counts | Sets a stance? |
|---|---|---|
| Hand counts, `data_center_meeting_position` | Public comments on a data center item, by side | Yes: the minimum's "speakers" (#1289) |
| Caption comments, `data_center_comment` | Public comments our own caption segmenter found (self-introductions, the chair calling speakers), all years | **No**: their side isn't classified yet (epic #1232, phase 2) |
| Transcript reading, `data_center_meeting_lean` | One reading per meeting of the public's position | No (#1289): it is about meetings, not speakers |

Alabama showed all three disagreeing: "no public speakers in 24 meetings reviewed" (hand counts), "the public spoke in 8 (6
against …)" (the reading) and "62 public comments at 10 local governments" (captions). **Decision:**

- Where our captions hold comments, the page never says "no public speakers": the facts read "no speaker’s side is recorded
  in 24 meetings reviewed, and the 62 public comments in our captions are not sorted by side yet." The speaker figures on
  **Who spoke up** show a dash (not available yet), not 0, with "62 public comments are on record in our captions here, but
  no speaker’s side is recorded yet." 0 stays for meetings reviewed where nobody spoke and the captions hold no comment.
- Caption comments still don't count toward the minimum: a comment with no side can't make a place lean.
- The reading in the line under "Not enough recorded activity …" names its own source (#1313): "A reading of all 71 meeting
  transcripts found the public speaking on data centers in 8 (6 against and 2 split)."

API: `GET /api/topics/{topic}/caption-facts` adds `caption_comments: {comments, governments} | null` (data centers only).

## 3. The topic control is the noun in the title

The owner's phone screenshots: "Not enough recorded activity to say ( ▾ )." and "America mostly wants fluoridation ended (
water fluoridation ▾)." The topic control was appended in brackets whenever the title's words didn't contain the topic's
name.

**Decision.** Each topic's title wording (`againstTitle` / `forTitle` in `utils/topicPositions.ts`) marks the topic's place
with `{T}`, which becomes the control: "America mostly wants [water fluoridation] ended.", "Ohio mostly favors [gun
control].", "Arizona mostly opposes [Flock and license plate readers]." The insufficient title is "Not enough recorded
activity on [data centers] to say." A title whose words don't name the topic leads with it ("On [gun control]: …"), never in
brackets (#1313 made the same fix for the insufficient title). `utils/storyHeadlineTopic.test.ts` checks every topic's for, against and split titles: one control, no bracket, the
topic's words not repeated outside it.

## 4. Every screen fits a phone

The owner's screenshot (Alabama Meetings screen, Pixel): a 4-line headline, a line with the next screen's question tacked on
("… 159 passages in 2026. What is on the agenda?") and a chart cut off by the bottom bar.

**Decision.**

- A screen's supporting line no longer ends with the next screen's question (`dropNextQuestion` in `utils/dataStory.ts`);
  Next leads on. The closing screen keeps its own question.
- On a phone (under 768px) the headline is set at 19–24px and the inline Back, which the bottom bar repeats, is hidden.
- `useScreenFit` fits each screen above the bottom bar: the headline and its line stay; the panel keeps its blocks in order
  while they fit, the first one zoomed down (to 55% at most) when it alone is too tall; later blocks and the screen's extras
  under the panel (the statement, the Overview's notes) wait behind **More on this screen**, which shows everything again.
  It measures in the screen's own coordinates, so a page still landing measures the same room.
- The series toggle is dropped under 431px; the count line opens.
- `e2e/story-fit.check.mjs` opens every screen at 360×740 and 412×915 and fails when the panel ends under the bar or the
  screen scrolls inside.

The phone header and the county map's phone layout are owned by #1304 and are not changed here.
