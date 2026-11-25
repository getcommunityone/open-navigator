---
title: Data stories
description: What the data stories hub and the Data Center Story are, who spoke for and against, how the story opens on an overview then asks its question after the record, how a story screen is built, how screens move on a phone, on a wide screen and with reduced motion, the cue on the next step, the voice rules for its sentences, how the place in scope is carried, and how to add a story.
---

# Data stories

A data story opens on an **overview of the record**, shows what public meetings said one screen at a time, and only then asks its topic question so you can agree or disagree and see how other readers answered. Each screen of the record has a bold sentence computed from the data, one line of context, and a chart where every dot is a record you can open. Along the way, each contested screen asks the statement its record is about (Agree / Disagree / Not sure) and shows **where you sit** once you answer ([#981](https://github.com/getcommunityone/open-navigator/issues/981)); there is no separate challenge any more. The hub never leads with the question (#950).

The **Data Stories** item in the header scrolls to the Data stories section of the home page (`/#data-stories`), which shows the story's real counts and opens the story, the challenge and the full hub at `/stories` ([#975](https://github.com/getcommunityone/open-navigator/issues/975)). The first story is the Data Center Story at `/stories/data-centers`.

## Which topics get a story

A story or a challenge needs meeting recordings or transcripts behind it. Figure-only data, such as census measures, is shown under Explore. Today that means data centers. Within a story, a screen whose figures are not from recordings or transcripts (for the Data Center Story, sites on record and projects on record) is marked "For context" with its source named, and is never the story's headline claim. The opener's large counts lead with the transcript-based ones and show counts from other sources after them with their source.

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

Twelve screens, in this order. Each has a short word as its header (never a number), and the progress rail names each stop after its screen. The id is what `?screen=` carries. The story opens on the record, not on the question (#950).

| Screen | Word | Id | What it shows |
| --- | --- | --- | --- |
| Opener | Overview | `overview` | A dot map of the country: each state's dots shaded by its real number of meetings where a data center came up, nationally (none stays grey). Hover or choose a state to read its count; clicking a state narrows the whole story to it (`?state=`). In a state or city scope that state stands out and the rest are muted but keep their own counts; clicking it again broadens (city → state → country), and **United States** goes straight to the country. A data table lists every state with a count. Then the row of large real counts ([#970](https://github.com/getcommunityone/open-navigator/issues/970)) |
| Who spoke up | Who spoke up | `voices` | The five figures, one dot per speaker, and up to three of the speakers' own words on each side, each linked to the moment in the recording |
| The place | Where | `scope` | The place picker, with the United States chosen, and the question worded for the place |
| Where they are | Sites | `sites` | Data center sites by status (one dot per site) |
| What is proposed | Proposals | `projects` | Projects by status (one dot per project) |
| What is promised | Promises | `jobs` | Jobs claims by phase (one dot per claim) |
| What is raised | Concerns | `concerns` | Concerns ranked, with count and share (one dot per mention) |
| When it comes up | Meetings | `meetings` | Meeting passages by year (one dot per passage). Hovering or focusing a dot previews the recording's thumbnail, title, place and date; clicking it (or Enter / Space) plays the recording in a dialog from the quoted moment. Nothing loads from YouTube before the hover, and the player exists only while the dialog is open: Escape, Close or a click outside removes it and returns focus to the dot ([#972](https://github.com/getcommunityone/open-navigator/issues/972)) |
| What is on the agenda | Agendas | `agendas` | Agendas for upcoming and past meetings |
| What was decided | Decisions | `decisions` | Decisions on data center items, debated or taken up without debate (one dot per decision, titled with its outcome as recorded); a debated one links to its page, one without debate to the meeting recording. "Not loaded yet" when the table isn't in the database ([#933](https://github.com/getcommunityone/open-navigator/issues/933)) |
| Where people gather | Gatherings | `gatherings` | Company-hosted meetings by kind |
| Your answer | Your answer | `verdict` | After the record: the topic question, how readers answered, then the challenge |

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

A **Where?** screen sits after Who spoke up so you can narrow the place before the chart screens. The place picker also stays in the top sentence. **Next** from Where continues through the record.

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
| `snap` | Narrower than 768 pixels, motion allowed | Each screen is exactly one frame tall (`100svh` less the two bars) and the page uses the browser's own scroll snap with `scroll-snap-stop: always`, so a swipe lands on the next screen and stops there. As a screen arrives its headline's words rise out of their masks, its blocks rise in one after another and its chart draws; as it leaves they fade and lift; coming back plays the entrance again. |
| `snap` with `data-fade` | **prefers-reduced-motion** on, at any width | One screen at a time, as on a phone. A screen cross-fades in when it arrives and its dots appear one after another. Only opacity changes: nothing slides, scales or drifts, and nothing loops. Moving on is a jump, not a glide. |

Reduced motion is not only a setting people choose. On Android, battery saver and "Remove animations" both turn it on, so a phone in battery saver gets this version. Before #930 that version was a plain stacked page with nothing animated, which read as a page that was not working. The challenge still uses the plain `stacked` mode under reduced motion.

A phone gets scroll snap, not the pinned engine. Pinning with ScrollTrigger and Lenis depends on the page's own scroll position being rewritten every frame, which fights a phone's touch momentum and the address bar changing the window height. Scroll snap is the browser's own mechanism, so momentum and the address bar are its business, and the screens are sized in `svh` so they do not jump when the bar hides. A screen whose content cannot fit scrolls inside its own block, never the page inside a screen: you scroll to the bottom of that block first, and the next swipe goes on. With a mouse wheel or trackpad on a narrow window, one wheel gesture moves exactly one screen.

The story's motion is calm: rises, fades and a steady filled button, with no bounce. The challenge shares the same engine and layout and adds its own livelier touches (see its page).

### Progress, and the next step

A strip of segments along the lower edge of the top bar has one segment per screen. The one in view fills, the ones behind it stay filled, and the words beside it say what is left ("Seven to go", "One to go", "Last one").

Every screen has one primary action: the three answers on the question and the last screen (then **See every data center record** once you have answered), and **Next →** everywhere else. When that control is not in view, because it is below the fold or inside a block that scrolls, a bar pinned to the bottom of the window shows the same action, full width on a phone, with a quieter **Back** beside it from the second screen on. It presses the real control, so there is one behaviour and one name. The bar is left out of the tab order and hidden from screen readers, because the real control is still in the page for them. The bar is `FloatingNext.tsx`; a screen marks its primary action with `data-primary`. On the hub the same bar carries **Start** whenever the card's own button has scrolled out of view, for example when you are reading the counts.

### Moving between screens

Every screen of the record ends with a quieter **Back** at the left and the primary **Next →** at the right, the same kind of button as the hub's **Start the story** ([#964](https://github.com/getcommunityone/open-navigator/issues/964)). The button shows only "Next": the next screen's name ("Next: Who spoke up") is its accessible name and tooltip, because as the visible label it read like a heading and confused readers. These keys also move: PageDown, Space, down arrow and right arrow go on; PageUp, Shift+Space, up arrow and left arrow go back; Home and End jump to the first and last screen. They do nothing while focus is in a field, a select, a table or a figure that scrolls on its own. Touch scrolling is never taken over (see "How the screens move" for the wheel). The address follows the screen in view (`?screen=sites`, replacing the entry), so a shared link opens on it.

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

The charts are the challenge's (`ChartPanel`). Every figure is a dot chart, and one dot is one real record: a speaker, a meeting, an agenda, a site, a project, a jobs claim, a mention of a concern. Dots are grouped under a heading with the group's real count and share. They appear one after another when their screen arrives. Each chart has a FIG. caption with source and scope, an honest note when the list is capped, and **Show data table**. A long figure scrolls inside its own frame so the headline stays in view.

There are two kinds of dot chart, and the caption says which:

- **Listed records** (sites, projects, jobs claims, meeting passages, agendas, company-hosted meetings). The endpoint returns the records, up to 500, and each dot opens its source. When the endpoint also counts the whole scope, the heading states that count and its share and says how many are drawn ("Operating · 118 records · 60% · showing 24"). When it does not count per group (projects by status), the heading says only how many are drawn ("Planned · 5 shown") and gives no share. A share is never worked out from a capped list.
- **Counts** (who spoke up, concerns, meetings in the opener). The endpoint returns totals, not records. Up to 240 the chart draws one dot per record. Above that one dot stands for 2, 5, 10, 20, 50... records, the smallest that fits, and the caption says so ("Each dot is 10 meetings; the last dot of a group is what is left over."). The last dot of a group stands for the remainder and is drawn smaller, so the dots always add up to the real count. The arithmetic is `dotRatio` and `countDots` in `web_app/src/utils/stanceGame.ts`, with tests.

## Add a story

1. Add the screens to `web_app/src/utils/dataStory.ts` (a list like `DATA_CENTER_STORY`: an `id`, a short word, the dataset key and the kind; start with a `question` and a `scope` screen and end with a `verdict` screen) and a function per record screen that returns its headline and context from the endpoint's response. Add them to `screenText` and cover them in `dataStory.test.ts`, including the empty and failed cases and the banned wording.
2. If the story needs a dataset the charts do not have yet, add it to `chartSpec` in `web_app/src/utils/stanceGame.ts` and to `fetchChartData` in `web_app/src/api/stance.ts`, with its test.
3. Register the story in `STORIES` in `web_app/src/pages/DataStory.tsx` and add its card to the hub in `web_app/src/pages/DataStories.tsx`.
4. Add the pack (`api/stance_packs/<pack>.json`) with the story's `question` and its statements. Give each statement the story screen that asks it (`story_screen`) and, only when agreeing clearly lines up with one side of the meeting speakers, `speaker_lean` (`for` / `against`); see [Story statements and where you sit](../development/story-statements-where-you-sit.md).
5. Update this page.

## Moving to the next screen

When you stop on a screen that has a next step, the page draws your eye to it. After about six seconds with no scroll, tap or key, the main button gets a small cue: its arrow slides a few pixels and back and a light passes across it. If the button is not on screen, the bar at the bottom of the window is showing it, and the cue plays there. This is the same on the hub (**Start**), in the story (**Next →**) and in the challenge.

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
