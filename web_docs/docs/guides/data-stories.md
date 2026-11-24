---
title: Data stories
description: What the data stories hub and the Data Center Story are, the question a story opens and closes on, how a story screen is built, how screens move on a phone and on a wide screen, the voice rules for its sentences, how the place in scope is carried, and how to add a story.
---

# Data stories

A data story opens on one question, asks where, shows what public records say one screen at a time, and then asks the same question again. Each screen of the record has a bold sentence computed from the data, one line of context, and a chart where every dot is a record you can open. The story ends by showing how other readers answered before and after, and hands you to a challenge on the same topic, the [Data Center Challenge](data-center-challenge.md) for data centers.

Open the hub at `/stories` (the **Data Stories** item in the header). The first story is the Data Center Story at `/stories/data-centers`.

## Which topics get a story

A story or a challenge needs meeting recordings or transcripts behind it. Figure-only data, such as census measures, is shown under Explore. Today that means data centers. Within a story, a screen whose figures are not from recordings or transcripts (for the Data Center Story, sites on record and projects on record) is marked "For context" with its source named, and is never the story's headline claim. The opener's large counts lead with the transcript-based ones and show counts from other sources after them with their source.

## The heading is a sentence

The hub and the story are headed by one sentence, "What did local meetings in [place] say about [topic]?", and its two blanks are the controls: the place blank opens a dialog with one search box for a city, county or ZIP code (pick a suggestion and it applies and closes), one-click **The United States** and **All of [state]**, **Use my location**, and an "Or pick a state" list. It has a close button, and Escape or a click outside closes it too; on a phone it is a bottom sheet. A county has no city grain here, so picking one applies its state and the dialog says "Stories are told by city or state; showing all of [state]". The lookup uses the same geocoder helpers as the home page location search (`web_app/src/utils/resolvePlace.ts`), picks carry the geocoder's own city name so nothing has to be typed exactly, and the choice is kept only in the address (`state` and `city`), never in the saved site-wide location, the topic blank lists the topics that have a story (today only data centers). They are underlined inline controls you can reach with the keyboard, named "Place" and "Topic", and at least 44 pixels tall on a phone. Because the story is built from meeting records, the screens that are things said in meetings (concerns, job claims, passages, agendas, company-hosted meetings) carry the sentence; sites and projects are marked "For context". The component is `web_app/src/components/stance/SentenceHeading.tsx`; it has the same props as the shared story component being built elsewhere, and the two should be merged.

## The hub

The hub is one card per topic. Today there is one, Data centers. The card leads with the topic's question, worded for the place in scope ("Should we allow new data centers?", "Should Tuscaloosa allow new data centers?"), and one short line. Its main button is **Start: [the question]**, which opens the story on its question screen; **Take the challenge** is the quieter link beside it. The question comes from the topic's pack; until it has loaded the card is titled "Data centers". Below the buttons the card shows a row of large counts for the place in scope: meetings where a data center came up, meeting passages quoted, agendas that name one, sites on record, projects on record and jobs claims. Every count is the endpoint's own whole-scope total. A count that is missing or zero is left out. Under a city, a count the source cannot narrow to a city (sites) is labelled with its own, wider place ("data center sites on record in Alabama") and the note under the row says which counts are city-level and which are state-level; the story's opener does the same. If the data cannot be loaded the card says so and offers **Try again**; the two links still work. On a phone the question and the main button are on the first screen (checked at 390 by 844 and 360 by 640). If nothing is on record for the place it says "No data available for this place."

## The Data Center Story

Eleven screens, in this order. Each has a short word as its header (never a number), and the progress rail names each stop after its screen. The id is what `?screen=` carries.

| Screen | Word | Id | What it shows |
| --- | --- | --- | --- |
| The question | The question | `question` | "Should we allow new data centers?" with **Yes**, **No** and **Pause for now** |
| The place | Where | `scope` | The place picker, with the United States chosen, and the question worded for the place |
| Opener | Overview | `overview` | A row of large real counts |
| Where they are | Sites | `sites` | Data center sites by status (one dot per site) |
| What is proposed | Proposals | `projects` | Projects by status |
| What is promised | Promises | `jobs` | Jobs claims by phase |
| What is raised | Concerns | `concerns` | Concerns ranked, with count and share |
| When it comes up | Meetings | `meetings` | Meeting passages by year (one dot per passage) |
| What is on the agenda | Agendas | `agendas` | Agendas for upcoming and past meetings |
| Where people gather | Gatherings | `gatherings` | Company-hosted meetings by kind |
| The question again | Your answer | `verdict` | The same question, then how readers answered before and after, then the challenge |

An old link to `?screen=turn` (the closing screen this replaced) opens the last screen.

### The question, before and after

The story opens on its question, large, with three answers and nothing before it. The answers are **Yes**, **No** and **Pause for now**; one line under them says a pause is a moratorium (no new approvals until the rules are settled). **Skip, I'd rather read first** moves on and stores nothing.

The second screen asks "Where?". The place picker sits in the sentence "Show me [the United States]", and the question under it is worded for the place it shows. **Next: Overview** is the default, so a reader who wants the whole country just goes on.

The last screen says "You've seen the record. Where do you stand now?" and asks the same question, worded for the place. After you answer it says whether your answer changed ("You said No before. Now you say Pause for now.", "You said Yes both times.", or "You said No. You skipped the question at the start."). Then it shows how readers of the story answered **before reading** and **after reading**, for the country, your state and your community, as stacked bars: Yes in teal, No in amber, Pause for now in a neutral ink tone, each with its count and percentage written out and your own answer marked. Then it offers the Data Center Challenge.

- Both answers are stored once per reader for the question (one before, one after). Picking another answer replaces the stored one.
- An answer is stored with the place showing when you give it. Because the question comes before the place, an answer you have already given is stored again with the place you then name, so it can count in that state's and community's results. Broadening back to the country changes nothing stored.
- A group with fewer than 30 answers shows "Not enough answers yet (N so far, 30 needed)" and no bars, exactly as the challenge does. Nothing is ever seeded: with no answers every group says so.
- The results are how readers of this story answered. It is not a poll, and the page says so next to the results.
- Nothing on these screens implies a right answer.
- If the question cannot be loaded the screen says so and the story can still be read.

The question and its answers come from the topic's pack (`question` in `api/stance_packs/data_centers.json`), so the wording and the option ids live in one place. The pure logic (the wording for a place, whether the answer changed, the bar maths for any number of options) is in `web_app/src/utils/storyQuestion.ts`, with its tests. The screens are `QuestionScreen`, `ScopeScreen` and `VerdictScreen` in `web_app/src/components/stance/StoryVoteScreens.tsx`, and the bars are `ChoiceBars.tsx`.

### How the screens move

The engine is the one the challenge uses (`web_app/src/components/stance/useActs.ts`), in one of three modes (`data-mode` on the page):

| Mode | When | What happens |
| --- | --- | --- |
| `pinned` | 768 pixels or wider, motion allowed | Each screen is pinned and scrubbed by the scroll: its word card slides in, the chart builds, the headline's words rise out of their masks one after another, and the screen dims and lifts as it leaves. The scroll glides to the next screen and one gesture never passes more than one. |
| `snap` | Narrower than 768 pixels, motion allowed | Each screen is exactly one frame tall (`100svh` less the two bars) and the page uses the browser's own scroll snap with `scroll-snap-stop: always`, so a swipe lands on the next screen and stops there. As a screen arrives its headline's words rise out of their masks, its blocks rise in one after another and its chart draws; as it leaves they fade and lift; coming back plays the entrance again. |
| `stacked` | **prefers-reduced-motion** on, at any width | A plain stack with native scrolling. Nothing moves and everything is in its final state. |

A phone gets scroll snap, not the pinned engine. Pinning with ScrollTrigger and Lenis depends on the page's own scroll position being rewritten every frame, which fights a phone's touch momentum and the address bar changing the window height. Scroll snap is the browser's own mechanism, so momentum and the address bar are its business, and the screens are sized in `svh` so they do not jump when the bar hides. A screen whose content cannot fit scrolls inside its own block, never the page inside a screen: you scroll to the bottom of that block first, and the next swipe goes on. With a mouse wheel or trackpad on a narrow window, one wheel gesture moves exactly one screen.

The story's motion is calm: rises, fades and a steady filled button, with no bounce. The challenge shares the same engine and layout and adds its own livelier touches (see its page).

### Progress, and the next step

A strip of segments along the lower edge of the top bar has one segment per screen. The one in view fills, the ones behind it stay filled, and the words beside it say what is left ("Seven to go", "One to go", "Last one").

Every screen has one primary action: the three answers on the question and the last screen (then **Take the Data Center Challenge** once you have answered), and **Next: ...** naming the next screen everywhere else. When that control is not in view, because it is below the fold or inside a block that scrolls, a bar pinned to the bottom of the window shows the same action, full width on a phone, with a quieter **Back** beside it from the second screen on. It presses the real control, so there is one behaviour and one name. The bar is left out of the tab order and hidden from screen readers, because the real control is still in the page for them. The bar is `FloatingNext.tsx`; a screen marks its primary action with `data-primary`. While the bar shows, the scroll cue (below) stays hidden.

### Moving between screens

Every screen of the record ends with **Next: ...** naming the next screen in words and a quieter **Back**. These keys also move: PageDown, Space, down arrow and right arrow go on; PageUp, Shift+Space, up arrow and left arrow go back; Home and End jump to the first and last screen. They do nothing while focus is in a field, a select, a table or a figure that scrolls on its own. Touch scrolling is never taken over (see "How the screens move" for the wheel). The address follows the screen in view (`?screen=sites`, replacing the entry), so a shared link opens on it.

### The place in scope

The page reads `?state=AL&city=Tuscaloosa` (a city only with a state). The bar at the top says exactly what is shown: **National**, **Alabama** or **Tuscaloosa, Alabama**, with one-click **All of Alabama** and **National only** and the **Your place** control. The label, the queries and the charts change together, and the place is carried to the hub and to every link at the end of the story. A screen with nothing in scope says "No data available for this place." and offers to show the state or the national data. Data center sites have no city in their source, so with a city chosen the sites screen shows the state and says so in its sentence and caption.

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

The charts are the challenge's (`ChartPanel`): dots for individual records (each dot focusable, opening its source, with arrow-key movement), ranked bars with count and share, an honest note when the list is capped, a FIG. caption with source and scope, and **Show data table**. A long figure scrolls inside its own frame so the headline stays in view.

## Add a story

1. Add the screens to `web_app/src/utils/dataStory.ts` (a list like `DATA_CENTER_STORY`: an `id`, a short word, the dataset key and the kind; start with a `question` and a `scope` screen and end with a `verdict` screen) and a function per record screen that returns its headline and context from the endpoint's response. Add them to `screenText` and cover them in `dataStory.test.ts`, including the empty and failed cases and the banned wording.
2. If the story needs a dataset the charts do not have yet, add it to `chartSpec` in `web_app/src/utils/stanceGame.ts` and to `fetchChartData` in `web_app/src/api/stance.ts`, with its test.
3. Register the story in `STORIES` in `web_app/src/pages/DataStory.tsx` and add its card to the hub in `web_app/src/pages/DataStories.tsx`.
4. Add the pack, with the story's `question`, as described in [Data Center Challenge](data-center-challenge.md).
5. Update this page.

## Moving to the next screen

When you have been still for a couple of seconds on a screen that has another one after it, a small cue appears at the bottom of the window with a chevron that moves downward. It says "Scroll" with a mouse or trackpad and "Swipe up" on a touch screen. Pressing it goes to the next screen, the same as **Next**. It hides while the page is moving, does not appear on the last screen, and stays hidden while the floating bar is showing. With reduced motion turned on in your device settings, the chevron is still.
