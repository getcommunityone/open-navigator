---
title: Data stories
description: What the data stories hub and the Data Center Story are, who spoke for and against, how the story opens on an overview then asks its question after the record, how a story screen is built, how screens move on a phone, on a wide screen and with reduced motion, the cue on the next step, the voice rules for its sentences, how the place in scope is carried, and how to add a story.
---

# Data stories

A data story opens on an **overview of the record**, shows what public meetings said one screen at a time, and only then asks its topic question so you can agree or disagree and see how other readers answered. Each screen of the record has a bold sentence computed from the data, one line of context, and a chart where every dot is a record you can open. Along the way, each contested screen asks the statement its record is about (Agree / Disagree / Not sure) and shows **where you sit** once you answer ([#981](https://github.com/getcommunityone/open-navigator/issues/981)); there is no separate challenge any more. The hub never leads with the question (#950).

The **Data Stories** item in the header scrolls to the Data stories section of the home page (`/#data-stories`), which shows the story's real counts and opens the story, the challenge and the full hub at `/stories` ([#975](https://github.com/getcommunityone/open-navigator/issues/975)). The first story is the Data Center Story at `/stories/data-centers`.

The home page opens on the Data stories section, with search second; the line "Every local decision, in one place." now closes the page, under Impact ([#995](https://github.com/getcommunityone/open-navigator/issues/995)). The section's map draws each state as small boxes ([#1087](https://github.com/getcommunityone/open-navigator/issues/1087), described below), and hovering one shows a card quoting that state: a speaker's own words with their recorded side ("Spoke against · Business owner") where one is on record, otherwise the newest meeting passage, verbatim, with the place, date, meeting and a link to the moment in the recording. Under it, **Browse topics** opens the story's screens (who spoke, projects, decisions, environment and resources, jobs) for the page's place. On the home page, the Data stories section leads with the story's conclusion, **America hates data centers.**, with its subtitle and a line giving the real speaker counts behind it. The headline shows only while the national record backs it (see [Story statements and where you sit](../development/story-statements-where-you-sit.md#decision-conclusion-headlines-shown-only-when-the-record-backs-them-989)); otherwise the story's question shows. **Start the story** comes right under it, in view on a laptop and a phone. The hub card does the same ([#989](https://github.com/getcommunityone/open-navigator/issues/989)). The section names the story (**The Data Center Story**). It has a US map with one marker per state where a data center came up in at least one meeting; a marker's size follows that real count and clicking it opens the story for that state. The page's own place is highlighted, with its counts and a **Start the story** button named for that place. Under the box, **All data stories** lists every story there is, and says so plainly while there is only one ([#985](https://github.com/getcommunityone/open-navigator/issues/985)).

Under the headline and its subtitle, the hero's left column lists up to three numbered points, each with a round teal icon, a bold title and a line with the real figure ([#1122](https://github.com/getcommunityone/open-navigator/issues/1122)). The titles are fixed; every figure is national and comes from `GET /api/data-centers/positions`:

1. **"Communities are saying no."** The meetings (and states) where Jev read the public as mostly opposed (`lean_totals.public_against_meetings` / `public_against_states`), then (only when the meeting reading is missing) "29 speakers counted by hand in 4 states: 18 against and 3 for." from the counted speakers in `totals`, with the number of states counted from `by_state` (states with any counted speaker), never hard-coded ([#1134](https://github.com/getcommunityone/open-navigator/issues/1134)).
2. **"Projects are being stopped."** The meetings whose data center outcome Jev read as tabled or deferred, denied or a moratorium (`lean_totals.stopped_meetings`).
3. **"Officials don't always listen."** The meetings (and states) where officials sided against the public (`lean_totals.disagreement_meetings` / `disagreement_states`, the #1113 rule).

Jev's figures are labelled "AI reading", because they are a classifier's reading of the transcript, not counted speakers. A point with no data (a 0, or `lean_totals` null because `data_center_meeting_lean` isn't loaded) is left out and the rest are renumbered; a sentence with no data is dropped from point 1. On a page scoped to a place, each point uses the place's own figure where it has one and otherwise the national figure, starting **"Nationally:"** ([#1134](https://github.com/getcommunityone/open-navigator/issues/1134), see below). Under the points, a large pill **Start the story for [place] →** keeps the page's scope, and a second pill **Next story: Short-term rentals →** (from `nextStoryLink` in `storyNav.ts`) carries it too. On a phone the points stack above the map and both buttons are full width. The copy is built by the pure helper `web_app/src/utils/heroPoints.ts`, with tests; the map on the right is unchanged.

The home map is now drawn like the Explore map: each state is a grid of small square boxes in its own shape (Alaska and Hawaii where the Albers map puts them), not a pin ([#1087](https://github.com/getcommunityone/open-navigator/issues/1087)). Where speakers are on record, a state's boxes are split in bands by the real counts of those who **spoke against**, **spoke for**, **asked a question** or took **no side** (from `data_center_meeting_position`, served nationally as `by_state` on `GET /api/data-centers/positions`); a caption gives the number of speakers and states behind the split. A state with meetings but no speaker on record is one grey (**Meetings, no stance on record**) and a state with no meetings stays the empty tint, so no split is ever drawn without real counts. Hovering a box (tapping, on a phone) shows one of that state's real passages, cycling through them across its boxes, with the place, date, quote and the state's speaker counts; clicking opens that state's story. A data table under the map lists every state with its meetings and speaker counts and links to its story, for keyboard and screen readers. The short-term rentals card uses the same map without a split, shaded by meetings only. Each state's outline is drawn over its boxes, and a state with meetings but no recorded stance is grey, light to dark by its real meeting count ([#1103](https://github.com/getcommunityone/open-navigator/issues/1103)). The legend has four entries: Spoke against (red), Spoke for (green), No side (purple) and Meetings with no stance on record (grey, darker = more meetings). A speaker who only asked a question is drawn as No side, while hover cards still say "asked a question" ([#1110](https://github.com/getcommunityone/open-navigator/issues/1110)). Hovering shows a quote card ([#1108](https://github.com/getcommunityone/open-navigator/issues/1108)). It carries the meeting's own recording thumbnail with "Hear it at m:ss", the place and date, the quote verbatim and large, and a speaker row: an initials avatar (never a photo), the shortened name, the side, and only the role or item on record. The meeting video popup uses the same card without the image.

Beyond counted speakers, both maps show an **AI reading** of each data center meeting ([#1117](https://github.com/getcommunityone/open-navigator/issues/1117)). Jev, a classifier, read every meeting's transcript for how members of the public and elected officials leaned (`data_center_meeting_lean`, served as `public_against_meetings` and `disagreement_meetings` on positions `by_state` and meeting-mentions `by_place`). A state or county with no counted speakers but at least one meeting where the public mostly opposed a data center (probability at least 0.7) is a lighter red, labelled **Public leaned against (AI reading of meetings)**; counted speakers keep their own colours. Where Jev read the public as opposed and officials as supportive, and the meeting wasn't a moratorium, a denial or an approval of rules (**officials sided against the public**), the map draws nothing extra (the owner preferred no dark outlines); it is stated in the hover card, the readout and the data table. The hover card and readout add a line such as "AI reading: the public leaned against in 2 meetings; officials sided against the public in 2 meetings." only when a count is above 0, and the data tables add both columns. "Supported" and "mixed" readings are never shown, because hand checks found them unreliable. The state drill-down also draws each county's border as a thin line over its dots, and it tells towns from counties the way printed maps do: towns and cities stay dark and bold beside their ring, while county governments are small, uppercase, letter-spaced grey text at the county's centre ("FAYETTE COUNTY"), placed after the towns. Method and limits: [Data center meeting lean](../development/data-center-meeting-lean.md). On a phone, one tap on a state opens its story ([#1120](https://github.com/getcommunityone/open-navigator/issues/1120)); there is no hover there, so the quote card is a desktop affordance.

### What a meeting quote card shows (#1124)

A meeting passage's card on the story maps (the national dot map, the state's county map and the home map) adds three things from the record, each left out when the record has nothing ([#1124](https://github.com/getcommunityone/open-navigator/issues/1124)):

- **AI summary.** The meeting's own AI summary (`event_meeting.meeting_summary`), labelled "AI summary" and clamped to about three lines. It is shown as plain, escaped text. A meeting with no summary shows no block.
- **Open the meeting analysis →.** A link to the meeting page (`/meetings/<event_meeting_id>`), which has "How this summary was made". The link keeps the story's scope (`?state=&city=`). A recording that is not in `event_meeting` has no link.
- **The speaker, only when on record.** The card names a speaker as "First L.", with the recorded role, only when a counted public comment from the same meeting (`data_center_public_comment`) has a name and its whole verbatim quote (20 characters or more) is inside the passage's excerpt. If two different speakers match, no name is shown. There is no guess from timing. Otherwise the card keeps "In the meeting · `<title>`". The API also shortens any fuller name to "First L." (AGENTS.md, Privacy).

The fields come from `GET /api/data-centers/meeting-mentions` as nullable `meeting_summary`, `meeting_url`, `speaker_display_name` and `speaker_role`. Each lookup is optional, so a database without `event_meeting` or `data_center_public_comment` leaves them null and the passages are still served. On the local warehouse (2026-11-26), 645 of 6,323 passages have a summary and 647 have a meeting page. Only 3 passages have a named speaker, because the public comment mart has 29 named comments and none of them has a timestamp. No transcript segment in `event_documents` carries a diarized speaker. More names need diarized transcripts (WhisperX speaker turns at each passage's start) or timed public comments.

## Which topics get a story

A story or a challenge needs meeting recordings or transcripts behind it. Figure-only data, such as census measures, is shown under Explore.

Every curated topic with at least one linked meeting has a live story at `/stories/<query_id>` ([#1133](https://github.com/getcommunityone/open-navigator/issues/1133)). The list is read at runtime from `GET /api/topics` (curated topics with a meeting count above 0, `utils/topicStories.ts`), so a topic added later goes live with no code change. `/stories/data-centers` stays on the Data Center Story (`DataStory`); every other slug is told by `TopicStory`: its caption (#1125), the map of meetings per state with each state's newest passage, what was said and what was decided. On the home **Browse topics** strip a tile is live when its topic has meetings, and selecting it shows that topic's story card above, keeping the place. Flock and license plate readers share one topic and one tile. **Starting a nonprofit** links to its guide. A tile whose topic has no meetings on record (Insurance shopping until #1079 has data) says "Coming soon". Bike lanes has its own curated topic (100007, [#1162](https://github.com/getcommunityone/open-navigator/issues/1162)) and goes live after the next seed and rebuild finds meetings for it. A curated topic with meetings that has no tile of its own gets a plain one, most meetings first, before the guides. At the end of a story, **Next story** walks the same live list. Within a story, a screen whose figures are not from recordings or transcripts (for the Data Center Story, sites on record and projects on record) is marked "For context" with its source named, and is never the story's headline claim. The opener's large counts lead with the transcript-based ones and show counts from other sources after them with their source.

Every topic story's map is the home box map with the same four-entry legend ([#1127](https://github.com/getcommunityone/open-navigator/issues/1127)). For topics other than data centers the colours come from the **AI reading of meetings** (`topic_meeting_lean`, [#1126](https://github.com/getcommunityone/open-navigator/issues/1126)), served by `GET /api/topics/{topic_id}/state-map` as distinct meetings per state: **Public leaned against** (red), **Public leaned for** (green), **Mixed** (purple) and **Meetings, no AI reading yet** (grey, darker = more meetings). A state's boxes are split in bands by those meeting counts, never by counted speakers, and the caption, hover card and data table say "AI reading of N meetings". Until the reading exists for a topic, the endpoint answers `available: false` and the map is grey with the note "No AI reading of these meetings yet; states show meetings only"; a failed request leaves the plain meetings map and claims no stance. Choosing a state (`?state=`) highlights it on the national map; the county drill-down the Data Center Story has needs a jurisdiction on each topic meeting and is tracked separately.

On the home hero, **Start the story** and the next-story button stick to the bottom of the screen until their own place scrolls into view, so they are always reachable ([#1174](https://github.com/getcommunityone/open-navigator/issues/1174)). The desktop hover card ends with "Click to open the story for [state] →". The map's cards prefer a named speaker's own words ("Rob D.", never a full surname): the home map asks `GET /api/data-centers/positions?per_state=3` for up to three quotes per state and side, and named speakers rank first.

## The heading is a sentence

The hub is headed by a short sentence, "What people are saying about [topic] in [place]", and the story keeps the longer "What did local meetings in [place] say about [topic]?". The two blanks are the controls: the place blank opens a dialog with one search box for a city, county or ZIP code (pick a suggestion and it applies and closes), one-click **The United States** and **All of [state]**, **Use my location**, and an "Or pick a state" list. It has a close button, and Escape or a click outside closes it too; on a phone it is a bottom sheet. A county has no city grain here, so picking one applies its state and the dialog says "Stories are told by city or state; showing all of [state]". The lookup uses the same geocoder helpers as the home page location search (`web_app/src/utils/resolvePlace.ts`), picks carry the geocoder's own city name so nothing has to be typed exactly, and the choice is kept only in the address (`state` and `city`), never in the saved site-wide location, the topic blank lists the topics that have a story (today only data centers). They are underlined inline controls you can reach with the keyboard, named "Place" and "Topic", and at least 44 pixels tall on a phone. Because the story is built from meeting records, the screens that are things said in meetings (concerns, job claims, passages, agendas, decisions, company-hosted meetings) carry the sentence; sites and projects are marked "For context". The component is `web_app/src/components/stance/SentenceHeading.tsx`; it has the same props as the shared story component being built elsewhere, and the two should be merged.

## The hub

The hub is one card per topic. Today there is one story (data centers), already named in the page sentence so the card does **not** repeat the topic as a second title. The page sentence stays within two lines. When the place blank is **the United States**, there is no **Showing: National** line and the counts row is not labelled National (#959 / #962); a city or state still gets a Showing line with broaden controls. The card opens with a care-first hook about power, water and land, a lede that invites **Start the story**, then a compact row of counts (small enough that the first viewport reaches Start): meetings where a data center came up, meeting passages quoted, agendas that name a data center, sites on record, projects on record and jobs claims. Every count is the endpoint's own whole-scope total. A count that is missing or zero is left out. Under a city, a count the source cannot narrow to a city (sites) is labelled with its own, wider place ("data center sites on record in Alabama") and the note under the row says which counts are city-level and which are state-level; the story's opener does the same. **Who spoke for and against** appears on the hub only when that table is loaded with figures — the empty "not loaded yet" line is never shown here (it still appears inside the story). Below the data, the main button is **Start the story**, with a subtle pulse (disabled under reduced motion). The agree/disagree statements are not on this card — they come inside the story, after each screen's record. If the data cannot be loaded the card says so and offers **Try again**; the button still works. If nothing is on record for the place it says "No data available for this place."

### Who spoke up

When the positions table is loaded, the hub card shows what people said about data centers at local meetings in the place in scope, as five figures and one chart (under the power/water/land hook). The story's own **Who spoke up** screen always has this block:

| Figure | What it counts |
| --- | --- |
| spoke for | Public speakers who asked the body to approve a data center item |
| spoke against | Public speakers who asked the body not to |
| asked a question | Public speakers who only asked questions |
| votes for | Yes votes on data center decisions that recorded a tally |
| votes against | No votes on those decisions |

The chart has one mark per speaker, grouped and headed by what they did ("Spoke against · 23 speakers · 56%"). Each group has its own colour and its own shape, so colour is never the only cue: teal squares for, amber diamonds against, open squares for a question, and short grey bars for speakers who took no side. When there are more than 240 speakers one mark stands for several, and the line under the chart says how many ("Each dot is 10 speakers; the last dot of a group is what is left over."). One line under it says what is counted and where: "Speakers at local meetings in Alabama where a data center item was discussed. From 6 meetings and 3 decisions with a recorded vote."

Only comments about the data center item count. A comment on another item of the same meeting never does. The rule, and what it misses, is in [Who spoke up about data centers](../development/data-center-who-spoke-up.md).

A figure with no data behind it is never shown as zero:

- When no decision in scope recorded a tally, both vote figures read **not recorded**, with "Votes were not recorded for these decisions."
- When no public comment on a data center item is on record for the place, the three speaker figures read **not recorded**, with "No public comment on a data center item is on record for these meetings."
- A real zero beside real counts stays zero (nobody spoke for, eleven spoke against).
- Until the table behind these figures has been built in the database, the story screen is one quiet line, "Who spoke for and against is not loaded yet."; the hub omits the block entirely so the care-first hook and Start stay in view (#962).

The figures come from `GET /api/data-centers/positions?state=&city=&limit=`, which sums the dbt mart `data_center_meeting_position` for the place and returns a few of the speakers' own words on each side from `data_center_public_comment`. The block is `web_app/src/components/stance/PositionsBlock.tsx`; its figures, caption and "not recorded" rules are `positionFigures` and `positionsCaption` in `web_app/src/utils/dataStory.ts`, with tests.

## The Data Center Story

Twelve screens, in this order. Each has a short word as its header (never a number), and each numbered dot down the left edge is named after its screen. The id is what `?screen=` carries. The story opens on the record, not on the question (#950).

| Screen | Word | Id | What it shows |
| --- | --- | --- | --- |
| Opener | Overview | `overview` | A dot map of the country: each state's dots shaded by its real number of meetings where a data center came up, nationally (none stays grey). Hover or choose a state to read its count; clicking a state narrows the whole story to it (`?state=`). In a state or city scope that state stands out and the rest are muted but keep their own counts; clicking it again broadens (city → state → country), and **United States** goes straight to the country. A data table lists every state with a count. In a state or city scope the map is that state's counties instead, like the Census map's state drill-down, in the home box map's colours: where its governments have speakers on record, a county's dots are split in bands by the real counts of those who spoke against, for, asked a question or took no side; a county with meetings but no stance on record is grey, light to dark by its real meeting count; a county with none takes the empty colour, and the legend matches the home map's ([#1106](https://github.com/getcommunityone/open-navigator/issues/1106)). A county government counts by its geoid; a city, town or school district is placed by its coordinates and drawn as a ring. Hovering a county quotes one of its passages and gives its stance counts, and the data table lists counties with their governments. A government that can't be placed is named under the map, not shaded ([#1039](https://github.com/getcommunityone/open-navigator/issues/1039)). Each ring's government is named beside it in the Data Explorer's label style (dark text, white halo), largest meeting counts first, and a label that would overlap one already drawn is left out; a county government is named at its county's centre only when that spot is free. At a state or city scope the Overview headline says which way speakers leaned once at least as many are on record as the national headline needs (10): two thirds or more against reads "Arizona pushed back: 11 of 12 speakers spoke against data centers.", two thirds or more for reads "… welcomed data centers …", otherwise "… was split …"; the meeting count moves to the line under it, and with fewer speakers the neutral count stays ([#1115](https://github.com/getcommunityone/open-navigator/issues/1115)). On a phone the maps say **Tap** instead of **Hover**, and tapping a county selects it like hovering does ([#1057](https://github.com/getcommunityone/open-navigator/issues/1057)). Then the row of large real counts ([#970](https://github.com/getcommunityone/open-navigator/issues/970)) |
| Who spoke up | Who spoke up | `voices` | The five figures, one dot per speaker, and up to three of the speakers' own words on each side, each linked to the moment in the recording |
| Where they are | Sites | `sites` | Data center sites by status (one dot per site) |
| What is proposed | Proposals | `projects` | Projects by status (one dot per project) |
| What is promised | Promises | `jobs` | Jobs claims by phase (one dot per claim) |
| What is raised | Concerns | `concerns` | Concerns ranked, with count and share (one dot per mention) |
| When it comes up | Meetings | `meetings` | Meeting passages by year (one dot per passage). Hovering or focusing a dot previews the recording's thumbnail, title, place and date; clicking it (or Enter / Space) plays the recording in a dialog from the quoted moment. Nothing loads from YouTube before the hover, and the player exists only while the dialog is open: Escape, Close or a click outside removes it and returns focus to the dot ([#972](https://github.com/getcommunityone/open-navigator/issues/972)) |
| What is on the agenda | Agendas | `agendas` | Agendas for upcoming and past meetings |
| What was decided | Decisions | `decisions` | Decisions on data center items, debated or taken up without debate (one dot per decision, titled with its outcome as recorded); a debated one links to its page, one without debate to the meeting recording. "Not loaded yet" when the table isn't in the database ([#933](https://github.com/getcommunityone/open-navigator/issues/933)) |
| Where people gather | Gatherings | `gatherings` | Company-hosted meetings by kind |
| Your answer | Your answer | `verdict` | After the record: the topic question, how readers answered, then the challenge |

### The title states the place's strongest statement (#993, #1125)

The story's title, and the caption on each **Browse topics** tile on the home page, is the strongest statement the record
supports for the topic and the place in scope (`?state=&city=`), with the place and topic still clickable on the story. The
caption picker (`web_app/src/utils/storyCaption.ts`) reads `GET /api/topics/{topic}/caption-facts` for exactly that scope
and tries, in order:
1. **"[America] hates [data centers]."** when the public was read as confidently against in enough meetings (an AI
   reading: at least 50 nationally, 10 in a state, 3 in one place) or the counted speakers pass the headline's gate
   (against at least twice for, at least 10 speakers). Only for topics where "against" has one direction.
2. **"[America] is divided on [data centers]."** when officials sided against the public in at least 10 meetings (an AI
   reading; the basis says "In 23 meetings across 10 states, officials backed data centers while the public pushed back
   (AI reading).") or counted speakers split with both sides substantial.
3. **Volume with state differences.** "[California] took up [short-term rentals] in 570 meetings, more than any other
   state.", or for a near tie "California and North Carolina took up guns most: 659 and 585 meetings."; "...the 2nd most of
   any state."; for a city "...more than any other place in Florida.". There is no per-resident claim: meeting coverage
   varies too much by state.
4. **Plain volume.** "[Florida] took up [short-term rentals] in 47 meetings."
5. **The question**, when nothing is on record. Guides with no meeting record (starting a nonprofit, insurance) always
   show their question, and their tile keeps its blurb.

The home story card uses the same title. No title or basis line ever states a zero.
A small line under the title gives the numbers behind it, and says when coverage varies by state. Every number is a real
count for the scope; missing data falls through to the next rule. Thresholds and the reasons for them:
[Story captions](../development/story-captions.md).

### One title, with a scoped subhead and numbered points (#1134)

The home hero, the story header and the story's Overview screen state the **same** caption for the page's scope, from
`pickCaption`. On the Overview, any caption but the bare question (hates, divided, state comparison, meeting count) is
the headline and the meeting count moves to the line under it ("A data center came up in 71 meetings in Alabama. First,
where are they?"), so the Overview never makes a different or stronger claim than the title. Only when the title is the
question does the Overview fall back to its speaker-lean or meeting-count headline (#1115). The national "hates" basis
names the states the meetings span: "In 283 meetings across 32 states, Jev (an AI classifier) read the public as mostly
against data centers (AI reading)." (`public_against_states` on caption-facts). On the home hero at a state or city
scope, the numbered points wait for the place's own figures, so national figures never flash first. Hand counts in a basis always name their scope: "29
speakers counted by hand in 4 states: 18 against and 3 for." (`speakers.states` on caption-facts), never "nationwide".

Under the title, the hero and the story header both show:
- **a subhead about the caption's scope only** (`captionSubhead` in `storyCaption.ts`): the story's national line only
  with the national "hates" caption; for a place a sentence about that place (for example "At local meetings in Arizona,
  the public has mostly spoken against data centers."), never a national claim;
- **the basis line** from the caption;
- **three numbered points** (`storyHeroPoints` in `heroPoints.ts`, from `GET /api/data-centers/positions`): each uses
  the place's own figure where it is above 0 (`scope_lean_totals`, the AI-reading totals narrowed by `state` and by `city`
  as a substring of the meeting's government name: "6 meetings in Alabama where the public leaned against (AI reading).")
  and otherwise the national one (`lean_totals`), starting **"Nationally:"**. Point 1 is a short form, so it doesn't
  repeat the basis line word for word.

"Supported" and "mixed" readings are never evidence for a title: hand checks found them unreliable (served as
`lean_totals.public_for_meetings` / `public_mixed_meetings` for audit; see
[Data center meeting lean](../development/data-center-meeting-lean.md)).

### No zero clause in a title (#1134)

A title or point never states a zero ("0 asked a question", "and none about operations jobs"). Zero clauses are dropped
and the rest are joined plainly, larger side first where that reads better: "Of 6 people who spoke on a data center item
at local meetings in Texas, 2 spoke for it and 1 against." Questions and speakers who took no side go in the line under
the title, only when there are any ("3 took no side."). With no one for or against, the title says only how many spoke.
Recorded votes and jobs claims follow the same rule ("Recorded votes: 5 for, in 1 decision."). The helper is
`countClauses` in `web_app/src/utils/clauses.ts`.

### Statements along the way (#981)

The contested screens (Sites, Proposals, Promises, Concerns, Meetings, Agendas, Gatherings) each ask, under the headline, the statement their record is about, with **Agree**, **Disagree** and **Not sure**. A screen with no record for the place asks nothing. Answers are saved as before (`/api/stance/responses`, anonymous player id), and you can change one.

After you answer, **Where you sit** shows:
- **Readers:** one bar from Agree to Disagree with a **You** marker, for the most specific place that has reached the minimum sample (your community, then your state, then the country). Below it, the page says how many have answered and how many are needed, and shows no split.
- **Speakers at meetings:** shown only where agreeing clearly lines up with one side (for example "The jobs a data center brings are worth what it asks"). One bar from **Spoke for** through **asked a question or took no side** to **Spoke against**, from the real speaker counts for the place, with **You** on the side your answer lines up with, and the same in a sentence. Statements that don't lean (such as "Local officials discuss data centers enough") show no speaker bar, because mapping that answer onto speakers for or against data centers would be invented.

The separate Data Center Challenge is retired: `/challenge/data-centers` (and `/play`) open the story, keeping the place.

#### The minimum sample

A group's split is shown only when at least **30** people in that group have answered the statement (the API setting `STANCE_MIN_SAMPLE`). Below that the page says how many have answered so far and how many are needed, and never shows a split. **Where you sit** names the group its bar uses (your community, your state or the country), and the sentence under it says the same group.

#### Privacy

Your browser makes a random id and keeps it in local storage under `on_stance_player_id`. That is the only thing stored about you in the browser. The server stores your id, the statement, your answer and the state and community you chose. It does not store your IP address, name or email. The rate limiter keeps only a hash in memory.

## Sources and limits

Every chart has a caption that names its source and what it counts. The numbers are real counts from the Open Navigator warehouse through the `/api/data-centers/*` endpoints. If a chart has no data, the screen says "No data available" and asks no statement.

- **Meeting records are not a survey.** The charts count what appears in local meeting records (transcripts, agendas) and in news and company announcements. They do not measure what the public thinks.
- **Charts follow your place as far as their source allows.** With a state they are for that state; with a community they are for that community wherever the source can narrow to one. Data center sites are listed by state, so that chart stays at the state, and its sentence and caption say so. With no state they are national, and the caption says which.
- **Dot charts draw one dot per record,** up to 500. When there are more records than dots, the caption says "Showing the most recent 500 of N" and the group percentages are shares of the dots drawn. A dot with a link opens the source record (a meeting recording at the moment, an agenda document, an article, a site's source page).
- **Ranked bars show a count and a share of the counted total.**
- **Site data** comes from Epoch AI and the US Data Center Registry (both CC BY 4.0), each site credited to its own source. Sites no longer listed by their source stay in the list.
- The dots are small. Use the arrow keys to move between them and the data table under each chart for the group counts.

An old link to `?screen=turn` opens the last screen. An old link to `?screen=question` opens **Overview**.

### The question, after the record

The story does **not** open on its question. After the overview and the rest of the record, the last screen says "You've seen the record. Where do you stand now?" and asks the topic question, worded for the place. The answers are **Yes**, **No** and **Pause for now**; one line under them says a pause is a moratorium (no new approvals until the rules are settled).

There is no separate **Where?** screen any more ([#1134](https://github.com/getcommunityone/open-navigator/issues/1134)): the place picker is in the title sentence, and the Overview shows the question worded for the place and your answer before reading, if you gave one. An old `?screen=scope` link opens the Overview.

After you answer on the last screen it says whether your answer changed when a prior answer is on record ("You said No before. Now you say Pause for now.", "You said Yes both times.", or that you had no earlier answer). Then it shows how readers of the story answered for the country, your state and your community, as stacked bars: Yes in teal, No in amber, Pause for now in a neutral ink tone, each with its count and percentage written out and your own answer marked. Then it offers **See every data center record**.

- Answers are stored once per reader for the question (an optional earlier "before" if one exists, and "after" on the closing screen). Picking another answer replaces the stored one.
- An answer is stored with the place showing when you give it. Broadening back to the country changes nothing stored.
- A group with fewer than 30 answers shows "Not enough answers yet (N so far, 30 needed)" and no bars, exactly as the challenge does. Nothing is ever seeded: with no answers every group says so.
- The results are how readers of this story answered. It is not a poll, and the page says so next to the results.
- Nothing on these screens implies a right answer.
- If the question cannot be loaded the screen says so and the story can still be read.

The question and its answers come from the topic's pack (`question` in `api/stance_packs/data_centers.json`), so the wording and the option ids live in one place. The pure logic (the wording for a place, whether the answer changed, the bar maths for any number of options) is in `web_app/src/utils/storyQuestion.ts`, with its tests. The screens are `QuestionScreen`, `ScopeScreen` and `VerdictScreen` in `web_app/src/components/stance/StoryVoteScreens.tsx`, and the bars are `ChoiceBars.tsx`.

### How the screens move

The engine is the one the challenge uses (`web_app/src/components/stance/useActs.ts`). The story uses two of its modes (`data-mode` on the page), and a third way of showing them under reduced motion:

| Mode | When | What happens |
| --- | --- | --- |
| `pinned` | 768 pixels or wider, motion allowed | Each screen is pinned and scrubbed by the scroll: its word card slides in, the chart builds, the headline's words rise out of their masks one after another, and the screen dims and lifts as it leaves. The scroll glides to the next screen and one gesture never passes more than one. |
| `snap` | Narrower than 768 pixels, motion allowed | Each screen is exactly one frame tall (`100svh` less the two bars at the top and the story bar at the bottom) and the page uses the browser's own scroll snap with `scroll-snap-stop: always`, so a swipe lands on the next screen and stops there. As a screen arrives its headline's words rise out of their masks, its blocks rise in one after another and its chart draws; as it leaves they fade and lift; coming back plays the entrance again. |
| `snap` with `data-fade` | **prefers-reduced-motion** on, at any width | One screen at a time, as on a phone. A screen cross-fades in when it arrives and its dots appear one after another. Only opacity changes: nothing slides, scales or drifts, and nothing loops. Moving on is a jump, not a glide. |

Reduced motion is not only a setting people choose. On Android, battery saver and "Remove animations" both turn it on, so a phone in battery saver gets this version. Before #930 that version was a plain stacked page with nothing animated, which read as a page that was not working. The challenge still uses the plain `stacked` mode under reduced motion.

A phone gets scroll snap, not the pinned engine. Pinning with ScrollTrigger and Lenis depends on the page's own scroll position being rewritten every frame, which fights a phone's touch momentum and the address bar changing the window height. Scroll snap is the browser's own mechanism, so momentum and the address bar are its business, and the screens are sized in `svh` so they do not jump when the bar hides. A screen whose content cannot fit scrolls inside its own block, never the page inside a screen: you scroll to the bottom of that block first, and the next swipe goes on. With a mouse wheel or trackpad on a narrow window, one wheel gesture moves exactly one screen.

The story's motion is calm: rises, fades and a steady filled button, with no bounce. The challenge shares the same engine and layout and adds its own livelier touches (see its page).

### Progress, and the next step

A strip of segments along the lower edge of the top bar has one segment per screen. The one in view fills, the ones behind it stay filled, and the words beside it say what is left ("Seven to go", "One to go", "Last one").

Every screen has one primary action: the three answers on the question and the last screen (then **See every data center record** once you have answered), and **Next →** everywhere else. On a wide screen, when that control is not in view, because it is below the fold or inside a block that scrolls, a bar pinned to the bottom of the window shows the same action, with a quieter **Back** beside it from the second screen on. It presses the real control, so there is one behaviour and one name. The bar is left out of the tab order and hidden from screen readers, because the real control is still in the page for them. The bar is `FloatingNext.tsx`; a screen marks its primary action with `data-primary`. On the hub the same bar carries **Start** whenever the card's own button has scrolled out of view, for example when you are reading the counts.

### Story navigation: progress bar, numbered dots, the next story (#1102)

The story shows how far you are and where it goes next ([#1102](https://github.com/getcommunityone/open-navigator/issues/1102)). None of this changes a screen or a map: every control below moves with the story's own screen navigation (the same `goTo` as **Next →** and the keys), so landing on a screen from the address (`?screen=`) works as before.

| Where | What | Behaviour |
| --- | --- | --- |
| Wide screens (768 pixels or wider) | A thin teal bar fixed along the top of the story | Its width is the share of screens reached: the screen in view counts, so the last screen fills it. Decorative (hidden from screen readers). |
| Wide screens | A column of small numbered dots on the left edge, one per screen in the story | The screen in view is filled teal (`#0f766e`), those behind it are outlined teal. Clicking a dot goes to that screen. Each dot's accessible name is its number and the screen's name ("3. Where"), and it is a `nav` named "Story screens" (it replaced the unnumbered rail on the right). The dots step aside while the next-story card is in view. |
| After the last screen, every width | A full-width **Next story** card | It fades in as it comes into view (opacity and a short rise; opacity only under reduced motion). It reads "Next story: Short-term rentals →" while there is a following live story, and "All data stories →" (to `/stories`) at the end of the list; the list does not wrap. The link keeps the place (`?state=&city=`). Scrolling on past the last screen reaches it: the scroll no longer pulls back onto the last screen once you are past it. |
| Phones (narrower than 768 pixels) | A bar fixed to the bottom of the window, above the safe area | Compact progress dots with "N to go", and one prominent **Next**: it goes to the next screen, and on the last screen it becomes **Next story** (or **All stories**). Each screen is shortened by the bar's height and the page has bottom padding of the same height, so the bar never covers a screen's controls. On phones it replaces the floating bar and each screen's own **Next →** (Back and the answers stay in the screen). |

The order of live stories is the home page's: the stories registry (`STORIES` in `web_app/src/utils/dataStory.ts`), then the topic stories (`/stories/short-term-rentals`). Stories still "coming soon" are never linked. The pure helpers (next live story, the progress share, which dot is current) are in `web_app/src/utils/storyNav.ts`, with tests; the components are in `web_app/src/components/stance/StoryProgress.tsx`.

### Moving between screens

Every screen of the record ends with a quieter **Back** at the left and the primary **Next →** at the right, the same kind of button as the hub's **Start the story** ([#964](https://github.com/getcommunityone/open-navigator/issues/964)). The button shows only "Next": the next screen's name ("Next: Who spoke up") is its accessible name and tooltip, because as the visible label it read like a heading and confused readers. Every screen uses the one nav row (`ScreenNav.tsx`, [#1138](https://github.com/getcommunityone/open-navigator/issues/1138)), including the question and last screens. On a wide screen the row is pinned to the bottom of the left column, so **Back** and **Next →** sit at the same place and size on every screen whatever the text or chart height. The first screen has no Back and keeps Next in that spot; on the last screen **See every data center record** takes Next's spot (same right edge, top and height) once you have answered. Because the inline row is always in view there, the floating bar does not appear beside it. Phones keep the row in the flow, with the bottom bar as before. `web_app/e2e/story-nav.check.mjs` checks this at 1440×900 (run it against a running app: `node e2e/story-nav.check.mjs --base http://localhost:5173`). These keys also move: PageDown, Space, down arrow and right arrow go on; PageUp, Shift+Space, up arrow and left arrow go back; Home and End jump to the first and last screen. They do nothing while focus is in a field, a select, a table or a figure that scrolls on its own. Touch scrolling is never taken over (see "How the screens move" for the wheel). The address follows the screen in view (`?screen=sites`, replacing the entry), so a shared link opens on it.

### The place in scope

The page reads `?state=AL&city=Tuscaloosa` (a city only with a state). The sentence blank already names the place (**the United States**, a state, or a city). Under a state or city the bar also says **Showing:** that place, with one-click **All of [state]** and **National only**; under the United States it does not repeat **Showing: National** (#959). The label, the queries and the charts change together, and the place is carried to the hub and to every link at the end of the story. A screen with nothing in scope says "No data available for this place." and offers to show the state or the national data. Data center sites have no city in their source, so with a city chosen the sites screen shows the state and says so in its sentence and caption.

### The voice

Headlines and context lines come from pure functions in `web_app/src/utils/dataStory.ts`, tested in `dataStory.test.ts`.

- Use counts, rankings, shares, contrasts and change over time. Name the scope in the sentence.
- A share or a ranking is stated only from whole-scope counts the endpoint returned. A list that is capped says "most recent N" and never gives a share or a trend.
- A sentence that ends in a question leads to the next screen only when the next screen answers it.
- No sentence describes how the page is built ("one screen at a time", "each dot opens its source"). The reader gets what the record says and what comes next. The source of a "For context" screen stays on its card.
- No causes ("because", "due to", "driven by"), no forecasts, no judgments (good, bad, worrying, best, worst, should, problem, crisis) and no claim about what people in general think. The one exception is the story's question itself, which asks "Should ...?" and is not a finding. The records are meeting records, not a survey, and a concern count is a count of passages, not of people.
- A header never starts with a number, so a sentence that would start with a count starts with a word ("Of 26 data center sites in Alabama, 14 are operating, ...").
- Missing data gives a neutral description of the chart, never a filled-in number.

### Colours

The hub, the story and the challenge use the Open Navigator house theme from `web_app/src/utils/folioThemes.ts` (the one the Data explorer Matrix map defaults to), applied as custom properties on the page wrapper through `web_app/src/utils/houseTheme.ts`. The challenge's reveal bars are Agree in the teal accent, Disagree in amber and Not sure in neutral, each with a text label and count so colour is never the only cue. Dot groups use the theme's segment colours in order.

## What a chart shows

The charts are the challenge's (`ChartPanel`). The listed-record charts (meeting passages, agendas, decisions, jobs claims) are drawn as a unit matrix of squares (#1140, see the Meetings screen above); the others are dot charts, and one dot is one real record: a speaker, a meeting, an agenda, a site, a project, a jobs claim, a mention of a concern. Dots are grouped under a heading with the group's real count and share. They appear one after another when their screen arrives. Each chart has a FIG. caption with source and scope, an honest note when the list is capped, and **Show data table**. A long figure scrolls inside its own frame so the headline stays in view.

There are two kinds of dot chart, and the caption says which:

- **Listed records** (sites, projects, jobs claims, meeting passages, agendas, company-hosted meetings). The endpoint returns the records, up to 500, and each dot opens its source. When the endpoint also counts the whole scope, the heading states that count and its share and says how many are drawn ("Operating · 118 records · 60% · showing 24"). When it does not count per group (projects by status), the heading says only how many are drawn ("Planned · 5 shown") and gives no share. A share is never worked out from a capped list.
- **Counts** (who spoke up, concerns, meetings in the opener). The endpoint returns totals, not records. Up to 240 the chart draws one dot per record. Above that one dot stands for 2, 5, 10, 20, 50... records, the smallest that fits, and the caption says so ("Each dot is 10 meetings; the last dot of a group is what is left over."). The last dot of a group stands for the remainder and is drawn smaller, so the dots always add up to the real count. The arithmetic is `dotRatio` and `countDots` in `web_app/src/utils/stanceGame.ts`, with tests.

### Meetings screen: trend line, milestone track and period dumbbell (#1140)

The Meetings screen (chart `meeting-mentions`) opens with three figures, all for the place in scope:

- **Trend line.** Distinct meetings per year whose transcript discussed the topic, with the quoted passages in the tooltip. A toggle switches to the topic's **share of recorded meetings**: meetings on the topic divided by every recorded (transcribed) meeting in the same place and year (`recorded_meeting_year`). The line carries the note "Meetings in our record by year; recording coverage grew sharply in 2025–26, so the rise partly reflects coverage." A year with nothing recorded, or with no meetings on the topic and fewer than 25 recorded meetings, is a gap in the line, never a zero; the note names the gap years.
- **Milestone track.** Under the line, on the same year scale, one lane per kind of event: meetings where officials approved, denied, tabled or adopted a moratorium (an **AI reading** of the transcript, labelled as such on the card), and state bills enacted once `topic_legislation_bill` is served. Click a square, or select one and use the arrow keys, Home and End; the card below gives the date, place, what happened and a link to the meeting or bill. Under 560px wide the track becomes a tap list, newest first.
- **Period dumbbell.** Last year (hollow circle) against this year (filled dot) for each state in national scope, or each town in state scope, with a ±pp label and sort buttons (by this year, by change, by last year). Rows with too few recorded meetings are left out and the note says how many. In a city scope the dumbbell is not drawn (it compares places within the scope).

Every other topic story (`/stories/<topic>`, for example `/stories/water-fluoridation`) shows the same trend line, milestone track and period dumbbell under its map, in a **Meetings over time** section that follows the page's state filter. Topics other than data centers count meetings from `topic_transcript_link` (no passage counts) and read their milestones from `topic_meeting_lean`.

Below them, the passages are a **unit matrix**: one square per passage, regrouped by a toggle (All, By year, By state or By town, By outcome, By who spoke). The outcome and public-lean groupings are an AI reading and say so. The decisions, agenda and jobs-claim charts use the same matrix with their own grouping first. The design and thresholds: [Story charts: timeline, dumbbell and unit matrix](../development/story-charts-timeline-dumbbell.md).

The headline names the year with the most meetings when the passage list is complete ("Data centers came up in 71 meetings in Texas, most of them in 2026 (278 quoted passages)."); when years tie or the list is capped it keeps the plain count.

## Add a story

1. Add the screens to `web_app/src/utils/dataStory.ts` (a list like `DATA_CENTER_STORY`: an `id`, a short word, the dataset key and the kind; start with a `question` and a `scope` screen and end with a `verdict` screen) and a function per record screen that returns its headline and context from the endpoint's response. Add them to `screenText` and cover them in `dataStory.test.ts`, including the empty and failed cases and the banned wording.
2. If the story needs a dataset the charts do not have yet, add it to `chartSpec` in `web_app/src/utils/stanceGame.ts` and to `fetchChartData` in `web_app/src/api/stance.ts`, with its test.
3. Register the story in `STORIES` in `web_app/src/pages/DataStory.tsx` and add its card to the hub in `web_app/src/pages/DataStories.tsx`.
4. Add the pack (`api/stance_packs/<pack>.json`) with the story's `question` and its statements. Give each statement the story screen that asks it (`story_screen`) and, only when agreeing clearly lines up with one side of the meeting speakers, `speaker_lean` (`for` / `against`); see [Story statements and where you sit](../development/story-statements-where-you-sit.md).
5. Update this page.

## Moving to the next screen

When you stop on a screen that has a next step, the page draws your eye to it. After about six seconds with no scroll, tap or key, the main button gets a small cue: its arrow slides a few pixels and back and a light passes across it. If the button is not on screen, the bar at the bottom of the window is showing it, and the cue plays there. On a phone the story's own bottom bar (#1102) always shows **Next**, so the cue is not drawn on a phone story. This is the same on the hub (**Start**), in the story (**Next →**) and in the challenge.

- The cue repeats about every eight seconds, at most three times, then it rests.
- Anything you do (scroll, tap, type) starts the wait and the count again. So does arriving on a new screen, and there the wait begins only after the screen has finished arriving.
- It never plays while the place picker is open, while a data table is open, while you are typing in a field or selecting text, or while the tab is in the background.
- It is never shown on a group of answers: no answer is pushed.
- Focus does not move, nothing is announced to a screen reader, no control is added and nothing shifts.
- With reduced motion nothing moves: an outline inside the button shows and goes, once per cue.
- The hub cue is visual only. On the story, with **Sound on**, the first idle nudge also plays one soft page-turn cue, and advancing to a new screen plays the same soft cue (after your first click or key unlocks Web Audio). Answering still plays the lock cue. The challenge is louder: its arrow hops twice and the light is brighter, and its first idle cue plays a soft sound when sound is on (#966).

| Timing | Value | Constant |
| --- | --- | --- |
| Stillness before the first cue | 6 seconds | `NUDGE_IDLE_MS` |
| Between cues | 8 seconds | `NUDGE_REPEAT_MS` |
| Cues before it rests | 3 | `NUDGE_MAX` |
| One cue | 1.4 seconds | `NUDGE_CYCLE_MS` |
| A screen's arrival, before the wait starts | 1.2 seconds | `NUDGE_ENTRANCE_MS` |

The timing is a pure function, `shouldNudge` in `web_app/src/utils/idleNudge.ts`, with tests. The hook that runs it is `web_app/src/hooks/useIdleNudge.ts`: it adds the class `is-nudging` to the button or the bar for one cue, and `stance.css` draws it. This replaced the story's separate "Scroll" / "Swipe up" cue, so there is one cue at a time. (The Data explorer's Matrix page still uses that older cue, `ScrollCue.tsx`; it has no floating bar.)
