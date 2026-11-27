---
sidebar_position: 63
title: Story captions
description: How each topic story and Browse topics tile picks the strongest true statement for its place, the thresholds behind each rule, and why (#1125).
---

# Story captions

[#1125](https://github.com/getcommunityone/open-navigator/issues/1125). The owner (26 Nov 2026) asked for a compelling
caption for every topic: lead with disagreement where it is high-volume, and otherwise with high volume where states
differ. Only the data-center story had a conclusion ("America hates data centers."); the rest said "X talked about Y in N
meetings." or showed a fixed blurb.

## Decision (27 Nov 2026, #1316): a place never borrows America's title

The owner, on `/stories/license-plate-readers?state=FL`: *"If florida is selected why is it showing america map and
national level header"*, and *"if there is not enough data to show at zip show city if not enough at city show county if
not at county show state"*. The step-up chain ends at the state. With a state or a city chosen, `pickCaption` no longer
uses the national entry of `facts.wider`: a thin state keeps its own title (Florida: "Florida weighed Flock and license
plate readers in 9 meetings."), and a city may still name its state's conclusion ("Alabama hates data centers."). This
replaces the national fallback of #1182 and #1200 for place scopes; the national page is unchanged. `TopicStory` also
passes `zoom` to `StoryStatesMap`, so a chosen state is drawn as that state rather than the national map.

## Decision (27 Nov 2026, #1330): every recorded position counts, public and official, and disagreement is headlined

[#1330](https://github.com/getcommunityone/open-navigator/issues/1330). The owner, on Alabama: *"how can we have 71 meetings
with 5 speakers — are we only counting public speakers? I thought we were counting all speakers and highlighting where they
disagree."* The #1289 minimum counted only hand-counted public speakers, so Alabama (0 counted) read "Not enough recorded
activity …" over a record that holds a position in 32 meetings.

- **Evidence.** A position is the public's (the meeting reading's `public_lean`: against, for or split) or officials' (the
  same reading's `official_lean`: against or for at P >= 0.7, divided otherwise), plus hand-counted speakers and recorded
  votes. Named supporters and opposers on each decision come from #1327's `supported_by` / `opposed_by`.
- **Minimum.** `STANCE_MIN_POSITION_MEETINGS = 5` meetings with any recorded position, public or official, or 3 decisions
  with a recorded vote (or 5 hand-counted speakers). Below all three: "Not enough recorded activity on [topic] to say.", and
  the facts count the meetings with a position. Any topic with a loaded reading is held to it, not only data centers.
- **Alabama, recomputed (27 Nov 2026):** 32 meetings with a position clear the minimum; the public's reading leans against
  (6 of 8), the one recorded vote went for data centers, so the title is **"Alabama is divided on data centers."**
- **Disagreement.** Where the reading found officials siding against the public (`officials_sided_against_public`), the
  Overview and the Who spoke up screen say so: "In Georgia, officials sided against the public in 11 of 27 meetings where
  both took a side." The count opens those meetings (`GET /api/data-centers/disagreement-meetings`, the #1296 drill
  pattern); the Who spoke up screen headlines it.
- **Who spoke up names who.** "Public: 6 against · 2 split (8 meetings)" and "Officials: 7 against · 8 for · 13 divided (28
  meetings); recorded votes: 1 decision for, 0 against; named supporters N · opposers M". The hand-counted figures follow
  under "Speakers counted by hand".

Contract: caption facts add `official_against_meetings`, `official_for_meetings`, `official_divided_meetings`,
`position_meetings`, `both_position_meetings` (null when the reading isn't loaded); new
`GET /api/data-centers/disagreement-meetings?state=&city=&limit=&offset=` (`total` equals `disagreement_meetings`).

## Decision (27 Nov 2026, #1290): votes read by which way they went; speaker sources reconciled; the topic is the noun

[#1290](https://github.com/getcommunityone/open-navigator/issues/1290) revises #1289 below; the reasons are in
[Story vote direction, speaker sources and phone fit](story-vote-direction-and-phone-fit.md).

- **Votes.** The vote check reads which way each tallied vote went for the topic (`data_center_decision.vote_side`: a passed
  moratorium is against, a passed approval or delay is for) and leans a way only with two thirds of the decisions. This
  answers #1289's caveat below; nationally the votes are mixed (7 for, 5 against), so the title is "America hates data
  centers." again.
- **Speakers.** Where our captions hold public comments, the facts say "no speaker’s side is recorded …, and the 62 public
  comments in our captions are not sorted by side yet", never "no public speakers" (#1313's reading line, which names its own
  source, follows).
- **Title.** #1313 put the topic control in the insufficient title; #1290 does the same for every topic's conclusion wording,
  which marks the topic's place (`{T}`), so no title shows the control in brackets ("America mostly wants [water
  fluoridation] ended.").

## Decision (27 Nov 2026, #1289): the stance headline agrees with the recorded votes, and needs a minimum

[#1289](https://github.com/getcommunityone/open-navigator/issues/1289). The owner found the Alabama page reading
"Alabama mostly opposes data centers." while its only recorded decision passed 8 for, 1 against and no public speakers were
found in 24 meetings reviewed. The title rested on the AI reading of 8 meetings alone (6 against, 2 split; the #1224 lower
tier).

After the rules below pick a caption, the scope's **recorded** activity checks it (`utils/stanceEvidence.ts`):

- **The minimum.** A stance caption (`position`, `sentiment`, `disagreement` and the `wider_*` kinds) needs at least
  **3 decisions with a recorded vote** or at least **5 hand-counted public speakers** in the scope. Below both, the title
  is **"Not enough recorded activity to say."** (kind `insufficient`), and the basis gives the facts first ("One decision
  passed 8–1; no public speakers in 24 meetings reviewed.") and then the AI reading as it stands. The numbered points under
  the title, which carry editorial leads such as "Communities are saying no.", are hidden for such a scope. A broader
  scope's title (`wider_*`) is not shown in its place: the page is about the place the reader chose.
- **Agreement with the votes.** A caption that claims a side for its own scope (`position` for or against, `sentiment`)
  must not take the side opposite the scope's recorded votes (votes for against votes against, summed over its decisions).
  When it would, the title becomes "[Place] is divided on [topic]." and the basis adds "Recorded votes: 79 for and 10
  against, in 12 decisions." Nationally this turns "America hates data centers." into "America is divided on data
  centers." (283 AI-read meetings against, 18 of 29 counted speakers against, recorded votes 79–10 for, on 27 Nov 2026).
  The Overview's speaker line (`overviewLean`) follows the same rule.
- **Nothing reviewed yet.** For data centers, a scope with no meeting reviewed (the API sends `speakers` and `votes` as
  null) counts as nothing recorded, so it is below the minimum too. Only an older server, which sends no `votes` field at
  all, keeps the earlier behaviour.
- **Topics with no hand counts or votes.** Only data centers keep counted speakers and votes
  (`data_center_meeting_position`). A topic with neither on record is not held to the minimum, since there is nothing to
  count for it yet; its title still rests on the AI reading alone.

Caveat, stated so it can be revisited: a vote "for" means the motion passed, and a motion can itself restrict data centers
(a moratorium or a strict ordinance). Summed votes are the owner's proxy for which way officials went until decisions carry
a direction of their own.

Update (27 Nov 2026, #1313): the title reads "Not enough recorded activity on [data centers ▾] to say.", with the topic
as an inline control. It used to be "… to say ( ▾ )." with an empty picker in brackets. The basis names each source and its
scope, so the two lines can't contradict: "One decision passed 8–1; no public speakers in 24 meetings reviewed by hand. A
reading of all 71 meeting transcripts found the public speaking on data centers in 8 (6 against and 2 split)." With no
public comment found it says so, and it adds how many meetings are not read yet.

Contract: `GET /api/topics/{topic}/caption-facts` adds `speakers.meetings_reviewed` and
`votes: {decisions, for, against} | null` (data centers only; null when no meeting in scope was reviewed).

## Decision (27 Nov 2026, #1224): the selected place gets its own title from 5 meetings, and the topic is always a control

The owner, on a phone at `/stories/data-centers?state=AL`, where the title read "America hates data centers." while
Alabama was selected:

> "If Alabama is selected, it should say Alabama hates, with the opportunity to change, and should be able to change data
> centers; now only 1 option."

`pickCaption` now has a lower tier between "hates" and the broader fallback. The titles stay the short conclusion
(the decision below), and the place word is the inline place control:

| Meetings where the public spoke (the place's own AI reading) | Title |
|---|---|
| At least the `HATES_MIN_MEETINGS` floor (10 in a state, 50 nationally, 3 in a city), majority against, a "hates" topic | "[Alabama] hates data centers." (unchanged) |
| At least the floor, otherwise | "[Ohio] mostly favors gun limits." / "… is split on …" (unchanged) |
| `LEAN_MIN_MEETINGS` (5) up to the floor, more than half on one side | "[Alabama] mostly opposes data centers." / "[Ohio] mostly favors gun limits.": the topic's own words (`againstTitle` / `forTitle`), never "hates" |
| 5 up to the floor, no side over half | "[Ohio] is split on gun control." |
| Under 5 | Today's fallback: the nearest broader conclusion as the title, the place's own facts in the basis, its place control in the subhead |

The basis line carries the count ("Most meetings were against data centers: 6 of 8 where the public spoke."). "Hates" on
the place's own hand-counted speakers (rule a) still outranks the lower tier.

The topic in the title is always a control (`withTopicBlank`): on the topic phrase when the words name it, otherwise in
brackets before the full stop ("Ohio mostly favors gun limits (gun control ▾)."). It lists every live story, the Data
Center Story and each topic story (`storyTopicOptions`), never a coming-soon topic, the same list on every story page.
Choosing one opens that story on its Overview with `?state=&city=` kept (`storyStartHref`).

## Decision (26 Nov 2026, #1234): the title is the short conclusion only, no "AI reading" text

**This decision overrides the title wording in the older sections below** (#1182 "America hates data centers; Tuscaloosa,
Alabama brought them up in 2 meetings.", #1200 "…: the public was against them in 283 of 341 meetings where it spoke (AI
reading)."). The owner, on the live site on a phone, 26 Nov 2026:

> "This title is terrible, we need the simple America hates conclusion we had before."
> "If you are in Tuscaloosa scope it should not say the United States."
> "This should not have same title twice and AI reading is garbage text, remove it."

What `pickCaption` now returns, for every title (home cards, story header, `/stories` cards, topic stories):

- **The title is only the conclusion sentence**, about 60 characters at most, nothing appended: "America hates data
  centers.", "Alabama hates data centers." (only when Alabama's own reading passes its floor), "America hates Flock and
  license plate readers.", "America is split on short-term rentals.", "California mostly wants limits on short-term
  rentals." (the predicate is the topic's `againstTitle` / `forTitle` in `utils/topicPositions.ts`; a topic without them
  says "mostly opposes / mostly supports [topic]"). "hates" stays limited to data centers, Flock / plate readers and
  pickleball. A topic without "hates" whose (a) passes says "[Place] mostly opposes [topic]." (no count). No counts, no
  "(AI reading)", no "; [place] brought them up …" clause.
- **A place whose own reading is under the floor** (`wider_position`, `wider_sentiment`) gets the nearest broader
  conclusion as that same simple sentence ("America hates data centers." at Tuscaloosa), so the title says what the map
  beside it shows. The place's own facts open the basis line ("Tuscaloosa, Alabama talked about data centers in 2
  meetings. Of its 2 meetings read, the public spoke in 1, under the 3 a conclusion of its own needs. Across America, the
  public was against data centers in 300 of 340 meetings where it spoke. …"), and the subhead starts with the place
  ("Tuscaloosa, Alabama hasn't had enough public comment on data centers to call. Showing America.", #1285; before: "Tuscaloosa, Alabama has too few meetings where the public took a side for a conclusion of its own; the title is
  America's."). No "In the United States," lead is added anywhere.
- **No conclusion anywhere**: the count titles stay ("California and North Carolina took up guns most: 659 and 585
  meetings.").
- **Counts move to the basis**, which opens with the conclusion's count ("The public was against data centers in 283 of
  341 meetings where it spoke.") and then the full split.
- **No "AI reading" sentence text** in any title, subhead or basis line: "(AI reading)", "AI reading of each meeting's
  transcript: …" and "with an AI reading" are gone ("Of 1,828 meetings read nationwide, …", "Of its 71 meetings read,
  …", "20 of 700 meetings have a reading so far"). One plain disclosure stays where a reader can find it: the map legend
  and its **How to read this map** note ("The AI reading is a classifier's reading of each meeting's transcript, not
  counted speakers."). Compact chips stay ("AI reading" on milestone cards and the home topic tiles).
- **The title is said once.** The story header states it; the Overview screen never repeats it but leads with its own
  count of the record ("A data center came up in 17 meetings in Texas.", kicker "First, where are they?"), via
  `distinctHeadline(title, ...candidates)` in `utils/dataStory.ts`, which a topic story's Overview can reuse.
- **The home title's place control** (#1212): on the place word when the title names the scope ("[America ▾] hates data
  centers."). When it names a broader place (or, nationally, the leading state), `splitCaptionAtPlace` returns null and
  the control goes in the line under the title, on the place where that line names it, else as "Showing [place ▾]"
  (`HomeStorySubhead`; on the story, the cover's subhead).

Before and after, live data 26 Nov 2026 (data centers):

| Scope | Before | After |
|---|---|---|
| National | America hates data centers: the public was against them in 283 of 341 meetings where it spoke (AI reading). | America hates data centers. |
| `?state=AL` | America hates data centers: the public was against them in 283 of 341 meetings where it spoke (AI reading); Alabama brought them up in 71 meetings. | America hates data centers. (subhead: "Alabama hasn't had enough public comment on data centers to call. Showing America.") |
| `?state=AL&city=Tuscaloosa` | America hates data centers: … (AI reading); Tuscaloosa, Alabama brought them up in 2 meetings. | America hates data centers. (subhead starts "Tuscaloosa, Alabama …", the place control) |
| `?state=TX` | Texas hates data centers: the public was against them in 17 of 18 meetings where it spoke (AI reading). (header and Overview) | Texas hates data centers. (header only; Overview: "A data center came up in N meetings in Texas.") |

## Decision: one title, five rules, real counts only

`pickCaption(topic, facts, scope)` in `web_app/src/utils/storyCaption.ts` returns `{kind, template, place, basis, ai}`. The
template keeps the place and topic as blanks, so one title serves the story header on `/stories/<topic>` (`DataStory.tsx`,
`TopicStory.tsx`), the home story card (`HomeDataStories.tsx`) and each tile on the home **Browse topics** strip
(`HomeTopicStrip.tsx`), all scoped to `?state=&city=`. `facts` comes from
`GET /api/topics/{topic}/caption-facts?state=&city=` (`api/routes/topic_caption_facts.py`). The picker ignores facts for
any scope other than the one shown, so the scope label and the numbers always match.

The owner (26 Nov 2026) wants the conclusion style as the one title: "[Place] hates [topic]." or "[Place] is divided on
[topic].", and the record's volume otherwise. The rules, in order; each needs its own counts and otherwise falls through
(CLAUDE.md, No Fabricated Data):

| # | Kind | Title | Needs | Source |
|---|------|-------|-------|--------|
| a | `sentiment` | "[America] hates [data centers]." | Confident public-against meetings at volume (AI reading), or the counted-speaker gate | `data_center_meeting_lean` / `topic_meeting_lean`; `data_center_meeting_position` |
| b | `disagreement` | "[America] is divided on [data centers]." | Officials sided against the public at volume (AI reading), or counted speakers split | the lean marts; `data_center_meeting_position` |
| c | `state_gap` | "[California] took up [short-term rentals] in 570 meetings, more than any other state." | A clear lead; a near tie names both | browse transcript-count marts, `data_center_meeting_mention` |
| d | `volume` | "[Florida] took up [short-term rentals] in 47 meetings." | Any meetings | same |
| e | `question` | The topic's question | none | none |

The basis line under the title gives the numbers. For (b) it reads "In 23 meetings across 10 states, officials backed data
centers while the public pushed back (AI reading)." Every AI reading says "(AI reading)" in the basis, and a tile (which
shows no basis) is prefixed **AI reading**.

**Only the confident "against" reading is used** (titles: superseded 26 Nov 2026, #1200, below). Jev's "for" and "mixed" labels were unreliable in hand checks
([Data center meeting lean](data-center-meeting-lean.md)), so they are never counted and never used in a ratio, and (a) is
a count of confident against-meetings, not a share of meetings read.

**"Hates" only where "against" has one direction.** For data centers, Flock and plate readers, and pickleball, a public
against is against the thing. ~~For guns, short-term rentals and fluoridation the public can be against the thing or
against limits on it, so (a) is skipped for them~~ (superseded 26 Nov 2026, #1182, below); (b) still applies, because
officials and the public disagreeing needs no direction.

## Decision: the title says what the map shows (#1182)

The owner (26 Nov 2026): "Say what the map says". At `?state=AL&city=Tuscaloosa` the home title read "Tuscaloosa, Alabama
talked about data centers in 2 meetings." beside an almost all red national map (public mostly opposed, AI reading).

- **(a2) `wider_sentiment`.** When the place's own reading fails (a) and (b), the picker tries the broader scopes in
  `facts.wider` (city: the state, then the country; state: the country) and takes the first whose confident
  public-against meetings pass (a) at that scope's floor (10 state, 50 national). The title names that scope as text and
  keeps the place as its blank: "America hates data centers; Tuscaloosa, Alabama brought them up in 2 meetings." With no
  meetings in the place the tail is "has none on record yet". The basis gives the broader count, then the place's own
  reading as it is: "has no AI reading of its own yet", "None of [place]'s N meetings with an AI reading read as mostly
  against.", or "6 of Alabama's 71 meetings with an AI reading read as mostly against, under the 10 a reading of its own
  needs." (never "too few readings" for a place with many readings that aren't against); the subhead names only what the broader scope's public mostly opposed. It is an AI
  reading (`ai: true`). It runs after the place's own (a) and (b) and before (c), because (c) and (d) describe volume
  while the map beside the title is coloured by lean.
- ~~**"Leaned against" for the other topics.**~~ (wording superseded 26 Nov 2026, #1190, below; the rule stands) `topic_meeting_lean` (#1126) fixes which way "for" points for each topic
  (allowing short-term rentals, keeping fluoride, building lanes; for guns, the proposal before the body, superseded by #1237: gun limits vs gun rights), so a confident
  "against" now has a stated direction. Those topics get (a) with "leaned against" (`CaptionCopy.against`) on the same
  thresholds, never "hates"; guns reads "leaned against what was proposed on guns". When (b) also passes for such a topic,
  "is divided" leads, as before.
- **API.** `GET /api/topics/{topic}/caption-facts` adds `wider` (`CaptionWiderLean[]`: `level`, `state_code`, `state`,
  `lean_meetings`, `public_against_meetings`, `public_against_states`, `disagreement_meetings`), read with the same lean
  SQL at the broader scope; a scope with no reading loaded is left out, and national scope has `wider: null`.
- **Start button.** `storyStartLabel(topic, label)` names the topic and the place: "Start the data center story for
  Tuscaloosa, Alabama", "Start the Flock and license plate readers story" nationally.

Titles on 26 Nov 2026 (local warehouse): national data centers "America hates data centers." (283); Flock and license
plate readers "America hates Flock and license plate readers." (186 confident public-against meetings, over the floor of
50 since the #1126 run); water fluoridation "America leaned against water fluoridation." (81); Alabama "America hates
data centers; Alabama brought them up in 71 meetings." (Alabama 6, under 10); Tuscaloosa as above.

## Decision: plain words for the AI reading, never "leaned" (#1190)

The owner (26 Nov 2026), verbatim: "leaned against is terrible title nobody including me knows what that means". The
figure behind the phrase is Jev's reading of each meeting's transcript: whether the members of the public who spoke were
mostly against, mostly for or split on the topic (`topic_meeting_lean`, `data_center_meeting_lean`). The copy now says that.

- **Titles for topics without "hates"** (everything but data centers, Flock and license plate readers, and pickleball) lead
  with the count: "In 81 meetings, the public mostly opposed water fluoridation."; at a place, "In 12 meetings in Arizona,
  the public mostly opposed short-term rentals." Gun control says "the public mostly opposed local gun-control measures", because
  opposing could mean opposing guns or opposing gun limits (`CaptionCopy.opposed`, which replaces `CaptionCopy.against`).
  Because the title states the AI count, it needs the meeting reading itself; "hates" may still rest on counted speakers.
  The "[Place] hates X." titles are unchanged.
- **The wider-scope fallback** (#1182) keeps "America hates data centers; Tuscaloosa, Alabama brought them up in 2
  meetings."; without "hates" it reads "Across America the public mostly opposed water fluoridation; Tuscaloosa, Alabama
  brought it up in 2 meetings."
- **Basis lines**: "In 283 meetings across 32 states, the public mostly opposed data centers (AI reading of each meeting's
  transcript)." The place's own reading: "Of Tuscaloosa, Alabama's 2 meetings with an AI reading, none had a public mostly
  opposed." or "Of Alabama's 71 meetings with an AI reading, 6 had a public mostly opposed, under the 10 a title of its own
  needs."
- **Maps, hover cards and tables**: "Public mostly opposed", "Public mostly supported", "Public split" (was "Mixed"),
  "AI reading: the public mostly opposed in 8 meetings."; "Officials sided against the public" stays. The unit matrix's
  public groups use the same three words.
- Copy only: column, field and table names (`public_against_meetings`, `topic_meeting_lean`) are unchanged.

Titles on 26 Nov 2026 after the change (local warehouse): water fluoridation "In 81 meetings, the public mostly opposed water
fluoridation." (was "America leaned against water fluoridation."); data centers "America hates data centers." and, at
`?state=AL&city=Tuscaloosa`, "America hates data centers; Tuscaloosa, Alabama brought them up in 2 meetings." (unchanged
titles, new basis wording). Guns (0 confident public-against meetings of 20 read) and short-term rentals (1 of 19) do not
reach the national floor of 50, so they keep their volume titles ("California and North Carolina took up gun control most: 659
and 585 meetings.", "California took up short-term rentals in 570 meetings, more than any other state.").

**No zero clauses.** No title or basis states a zero ("0 spoke for"): a zero clause is left out (owner rule).

**No per-resident claim.** An earlier draft named the state with the most meetings per resident (guns: South Dakota, 268
per million). Meeting coverage varies hugely by state, so a per-resident rate measures our coverage, not the state's
interest. It was dropped. When the top two states are within `STATE_GAP_MIN_RATIO` of each other, both are named: "California
and North Carolina took up gun control most: 659 and 585 meetings."

## Decision: "Gun control", with two named sides (#1237)

The owner (26 Nov 2026), on the guns map legend "Opposed the gun proposal / Backed the gun proposal / Split": "On guns how
are you defining oppose? We should probably label it gun control. I can't tell what we are doing and don't trust it."
and "These titles are terrible. Is the proposal control or rights expansion? Define it better."

- **The topic shows as "Gun control"** on the home tile, the /stories card, the story eyebrow, the Start button
  ("Start the gun control story"), the tab ("Gun control — Data story | Open Navigator"), Next story labels and titles
  (`CAPTION_COPY.guns.topic` = "gun control"). The names come from the web copy layer (`homeTopicTiles.ts`,
  `topicStories.ts` `TOPIC_COPY`, `storyCaption.ts`), not the `curated_topics` seed: the seed's "Guns" is denormalized
  into `meeting_topic_link.link_label` and the browse/search marts, so renaming it would mean rebuilding those marts and
  the Neon copy for a label the story surfaces already override. Browse Topics and search keep the catalog's "Guns".
  The topic id (100005), slug and `/stories/guns` are unchanged.
- **Two named sides, not for/against a proposal.** The stored readings were written by the gun-control question
  (`question_version` `48468cc5296e`): `mostly_supportive` = asking for a limit on firearms, **"Favor gun limits"**;
  `mostly_opposed` = defending gun rights, opposing the limit, or backing a Second Amendment sanctuary or other
  rights-expansion resolution, **"Favor gun rights"**. Split stays "Split"; missing reads "No reading yet, or the public
  didn't speak on it".
- **The map's "How to read this map" note defines both sides and what isn't counted:** "Gun limits = a local measure
  restricting firearms (where they may be carried or fired, sales, ranges or shops near homes, storage). Gun rights =
  opposing such limits or backing a Second Amendment sanctuary or rights-expansion resolution. Not counted: police
  service weapons, ShotSpotter, tools called guns."
- **Titles** follow whatever title rule is in force, with the topic's words: "In Ohio, most meetings that took up gun
  control favored gun limits: …", "Ohio is split on gun control …". Main's `topic_lean.py` still holds the earlier
  "proposal before the body" question; committing the data-writing one is
  [#1239](https://github.com/getcommunityone/open-navigator/issues/1239), and a skipped vitest turns on once it lands.

## Decision: each topic's position in its own words, and the place's conclusion in the title (#1200)

The owner (26 Nov 2026), with a phone screenshot of `/stories/guns` (an all-grey map, title "California and North
Carolina took up guns most: 659 and 585 meetings."): "We need for, against, neutral and missing — use best words
available — for positions on each of our topics, and state the conclusion summary position in the state in headline."

- **One vocabulary.** `web_app/src/utils/topicPositions.ts` holds each topic's words for the four positions, restating
  the stance Jev was asked about in `llm.typesafe.topic_lean.TOPICS` (data centers: their own screen). A vitest reads
  `topic_lean.py` and fails if a topic has no words, or if guns or short-term rentals stop following its stance.

  | Topic | Against | For | Neutral | Missing |
  |---|---|---|---|---|
  | Data centers | Against data centers | For data centers | Split | No AI reading yet / Public didn't speak on it |
  | Short-term rentals | Want limits on short-term rentals | Want to allow short-term rentals | Split | same |
  | Flock and license plate readers | Against the cameras | For the cameras | Split | same |
  | Gun control (`guns`) | Favor gun rights | Favor gun limits | Split | No reading yet / Public didn't speak on it |
  | Pickleball | Against the courts | For the courts | Split | same |
  | Water fluoridation | End fluoridation | Keep fluoride in the water | Split | same |
  | Bike lanes | Against the bike lanes | For the bike lanes | Split | same |

  Gun control names both sides instead of for/against a "proposal" (#1237, below).
- **Neutral and missing are kept apart.** Per meeting (AI reading): against = mostly opposed with P ≥ 0.7; for = mostly
  supportive with P ≥ 0.7; **split** = mixed, or a for/against lean under P 0.7 (the public spoke but no confident side);
  **missing** = no reading yet, or read and the public didn't speak on the topic. A label outside the question's choices
  is in none of the four (#1204). The grey on the map says "No AI reading yet, or the public didn't speak on it", and the
  note under it defines split.
- **Rule (p) `position`, before every other rule.** With at least `HATES_MIN_MEETINGS` meetings where the public spoke
  (for + against + split; 50 national, 10 state, 3 city), the title states the place's conclusion with the count:
  - a side with more than half: "In Ohio, most meetings that took up gun control favored gun limits: 41 of 63
    where the public spoke (AI reading)."; nationally "Across America, most meetings that took up short-term rentals
    wanted limits on short-term rentals: …";
  - against, for data centers, Flock and license plate readers, and pickleball only: "America hates data centers: the
    public was against them in 283 of 341 meetings where it spoke (AI reading).";
  - no side over half: "America is split on short-term rentals (AI reading of 641 meetings where the public spoke)."
  The denominator leaves out meetings where the public didn't speak: they hold no position. The basis line gives every
  count, larger first and no zeros: "AI reading of each meeting's transcript: of 1,203 meetings read nationwide, the
  public spoke in 221 (186 against the cameras, 19 for the cameras and 16 split). In 982 it didn't speak on it."
- **(p2) `wider_position`.** It takes (a2)'s place: after the place's own (a) and (b), so counted speakers can still give
  a place its own title ("Ohio hates data centers."), and before the volume rules. A city or state below the floor then
  takes the nearest broader scope with a conclusion, named: "America hates data centers: … (AI reading); Tuscaloosa, Alabama brought them up in 2 meetings."
- **Too few.** Below the floor the earlier rules run (with (p2) in (a2)'s place, since the against-only (a2) could
  contradict a broader scope that is split), and the line under the title says how far the
  reading has got: "20 of 7,623 meetings have an AI reading so far; the public spoke on guns in 1, too few for a
  conclusion." or "No meeting in Ohio has an AI reading of the public's position yet." (only when the reading loaded
  and found none: caption-facts sends `lean_meetings: 0` then, and null when the read failed, which adds no line).
  Readings whose label is outside the question's choices (#1204) are said as such ("113 meetings more have a reading in
  labels this page can't show yet."), never as "not read yet".
- **Supersedes** "Only the confident 'against' reading is used" (#1125) for titles: the owner asked for for, against and
  neutral. The for and split readings are still unverified by hand check (2 of 4 right for data centers), so every title
  and basis says "AI reading". The national subhead of a "hates" conclusion keeps the story's own subhead.
- **API.** caption-facts adds `public_split_meetings` and `public_silent_meetings` and fills `public_for_meetings` for
  data centers too; each `wider[]` entry adds the same three. state-map adds `silent_meetings` per state, and
  `no_side_meetings` is the split count above.
- **Unit matrix.** `GET /api/data-centers/meeting-mentions` rows serve `ai_public_lean` with a lean under P 0.7 as `mixed`,
  so the matrix's "By who spoke" groups match the title's split.
- **Where the words show.** Topic map legend, hover line and data table (`StoryStatesMap`'s `positions` prop, with a
  "Public didn't speak on it" column), the Data Center Story's unit matrix "By who spoke" groups (`sideLabelsFor`), and
  the Overview, which states the same title.

## Thresholds and why

| Constant | Value | Why |
|----------|-------|-----|
| `LEAN_MIN_MEETINGS` | 5 | Meetings where the public spoke before a place gets its own "mostly …" or "is split" title below the hates floor (owner, 27 Nov 2026). Five is a handful of separate meetings, not one night; it never says "hates". A city's floor is already 3, so it is unchanged. |
| `HATES_MIN_MEETINGS` | 50 national, 10 state, 3 city | Confident public-against meetings before "hates" leads. Fifty across the country, ten in a state and three in one place are each a pattern, not one heated night. Nationally 283 data-center meetings pass; Georgia 37; Arizona 14. |
| conclusion gate | ratio 2, 10 speakers | Unchanged from #989 (`STORIES['data-centers'].conclusion`): counted speakers against at least twice for, at least 10 speakers. Either it or the AI count is enough for (a). |
| `DISAGREEMENT_MIN_MEETINGS` | 10 | Ten separate meetings where officials sided against the public. Nationally 23 data-center meetings pass (10 states), but (a) leads there. |
| `SPLIT_MIN_SPEAKERS_PER_SIDE` | 10 | The same floor as the headline's `minSpeakers`, applied to each side. |
| `SPLIT_MIN_MINORITY_SHARE` | 0.35 | Below about a third the smaller side is a minority, and the stance is lopsided, not split. |
| `STATE_GAP_MIN_RATIO` | 1.25 | A state is named alone only when it leads the next by a quarter or more; below that the two are named together, since a lead of a few percent is within coverage noise. "More than twice" is said only at a ratio of 2 or more. |
| `STATE_GAP_MIN_MEETINGS` | 50 | A lead built on a handful of meetings is noise. Both states of a near tie need it. |
| `STATE_RANK_MAX` | 3 | "The 2nd / 3rd most of any state" is worth saying; 7th is not. A tie gives no rank. |
| `PLACE_GAP_MIN_MEETINGS` | 10 | A city is ranked among its state's places only with ten meetings or more, and only when strictly ahead of the next place. |

Every state-gap basis says that how many meetings are on record varies by state, because coverage, not only interest,
drives the counts.

## Where the counts come from

- **Data centers:** meetings are distinct `video_id` in `data_center_meeting_mention`, the figure the Data Center Story
  already shows; speakers from `data_center_meeting_position`; AI readings from `data_center_meeting_lean`.
- **Other topics:** `browse_transcript_count`, `browse_entity_state_transcript_count` and
  `browse_entity_place_transcript_count` (entity_type `topic`). For curated topics these equal the distinct meetings in
  `topic_transcript_link`, the same counts `/api/topics/{id}/states` serves the story map.
- **AI readings for other topics:** `topic_meeting_lean` (#1126, one row per meeting and topic). The route reads it in its
  own try block: until it lands, every reading is null and rules (a) and (b) fall through, with no code change needed after.
- The route still returns state populations, but the picker no longer uses them (see above).
- Each optional read (population, speakers, lean) is wrapped on its own; a missing table or column gives null, never 0.

## Topics

Strip card to caption key: Data centers `data-centers`; Short-term rentals `short-term-rentals`; Flock and license plate
readers `license-plate-readers` (one curated topic, 100004, so one tile since #1133; `flock` stays an alias); Guns `guns`; Pickleball `pickleball`; Bike lanes `bike-lanes` (the curated topic
from #1131; until it has meetings the tile keeps its blurb. It no longer borrows the CivicSearch "Bicycle transportation"
count, #1133); Starting a nonprofit and Insurance shopping are guides with no meeting
record, so they always ask their question and the tile keeps its blurb. Insurance is not linked to the CivicSearch topic
"Insurance discussions": a meeting about insurance is not evidence about shopping for it, so the guide does not borrow that count.

National titles on 26 Nov 2026 (local warehouse):

| Topic | Title | Basis |
|-------|-------|-------|
| Data centers | America hates data centers. | 283 confident public-against meetings (AI reading); 29 counted speakers, 18 against, 3 for |
| Short-term rentals | California took up short-term rentals in 570 meetings, more than any other state. | next North Carolina, 317 |
| Flock and license plate readers | California weighed Flock and license plate readers in 228 meetings, more than twice any other state. | next Washington, 105 |
| Guns | California and North Carolina took up guns most: 659 and 585 meetings. | ratio 1.13, a near tie; next Ohio, 399 |
| Pickleball | California brought up pickleball in 446 meetings, more than any other state. | next North Carolina, 292 |
| Water fluoridation | America took up water fluoridation in 526 meetings. | top states tied at 45, under the 50-meeting floor |
| Starting a nonprofit, Insurance | the question | guides with no meeting record |
| Bike lanes | none yet | the curated topic (#1131) has no meetings linked, so the tile keeps its blurb |

Once `topic_meeting_lean` (#1126) reaches `public`, (a) and (b) can lead for other topics (gold on 26 Nov 2026 held 34
confident public-against meetings for Flock and license plate readers, under the national floor of 50).
