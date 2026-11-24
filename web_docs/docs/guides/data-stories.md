---
title: Data stories
description: What the data stories hub and the Data Center Story are, how a story screen is built, the voice rules for its sentences, how the place in scope is carried, and how to add a story.
---

# Data stories

A data story tells one topic from public records as a short run of scrolling screens. Each screen has a bold sentence computed from the data, one line of context, and a chart on the other side where every dot is a record you can open. Each story ends by handing you to a challenge on the same topic, the [Data Center Challenge](data-center-challenge.md) for data centers.

Open the hub at `/stories` (the **Data Stories** item in the header). The first story is the Data Center Story at `/stories/data-centers`.

## Which topics get a story

A story or a challenge needs meeting recordings or transcripts behind it. Figure-only data, such as census measures, is shown under Explore. Today that means data centers. Within a story, a screen whose figures are not from recordings or transcripts (for the Data Center Story, sites on record and projects on record) is marked "For context" with its source named, and is never the story's headline claim. The opener's large counts lead with the transcript-based ones and show counts from other sources after them with their source.

## The heading is a sentence

The hub and the story are headed by one sentence, "What did [place] say about [topic]?", and its two blanks are the controls: the place blank takes a state and a community ("the United States" clears both and the address keeps `state` and `city`), the topic blank lists the topics that have a story (today only data centers). They are underlined inline controls you can reach with the keyboard, named "Place" and "Topic", and at least 44 pixels tall on a phone. Because the story is built from meeting records, the screens that are things said in meetings (concerns, job claims, passages, agendas, company-hosted meetings) carry the sentence; sites and projects are marked "For context". The component is `web_app/src/components/stance/SentenceHeading.tsx`; it has the same props as the shared story component being built elsewhere, and the two should be merged.

## The hub

The hub is one card per topic. Today there is one, Data centers, with two actions: **Read the story** and **Take the challenge**. The card shows a row of large counts for the place in scope: meetings where a data center came up, meeting passages quoted, agendas that name one, sites on record, projects on record and jobs claims. Every count is the endpoint's own whole-scope total. A count that is missing or zero is left out. Under a city, a count the source cannot narrow to a city (sites) is labelled with its own, wider place ("data center sites on record in Alabama") and the note under the row says which counts are city-level and which are state-level; the story's opener does the same. If the data cannot be loaded the card says so and offers **Try again**; the two links still work. If nothing is on record for the place it says "No data available for this place."

## The Data Center Story

Nine screens, in this order. Each has a short word as its header (never a number), and the progress rail names each stop after its screen.

| Screen | Word | Chart |
| --- | --- | --- |
| Opener | Overview | A row of large real counts |
| Where they are | Sites | Data center sites by status (one dot per site) |
| What is proposed | Proposals | Projects by status |
| What is promised | Promises | Jobs claims by phase |
| What is raised | Concerns | Concerns ranked, with count and share |
| When it comes up | Meetings | Meeting passages by year (one dot per passage) |
| What is on the agenda | Agendas | Agendas for upcoming and past meetings |
| Where people gather | Gatherings | Company-hosted meetings by kind |
| Closing | Your turn | Links to the challenge, the Data centers page and decisions for the same place |

On a screen wider than 768 pixels, with motion allowed, the screens are pinned and driven by the scroll, settling on a hold where the sentence and chart are in place. On a narrower screen, or with **prefers-reduced-motion** on, they are a plain stack with native scrolling and everything already in its final state. The engine is the same one the challenge uses (`web_app/src/components/stance/useActs.ts`).

### Moving between screens

Every screen ends with **Continue to ...** naming the next screen in words and, after the first, a quieter **Back**. These keys also move: PageDown, Space, down arrow and right arrow go on; PageUp, Shift+Space, up arrow and left arrow go back; Home and End jump to the first and last screen. They do nothing while focus is in a field, a select, a table or a figure that scrolls on its own. Wheel and touch scrolling are never taken over. The address follows the screen in view (`?screen=sites`, replacing the entry), so a shared link opens on it.

### The place in scope

The page reads `?state=AL&city=Tuscaloosa` (a city only with a state). The bar at the top says exactly what is shown: **National**, **Alabama** or **Tuscaloosa, Alabama**, with one-click **All of Alabama** and **National only** and the **Your place** control. The label, the queries and the charts change together, and the place is carried to the hub and to every link at the end of the story. A screen with nothing in scope says "No data available for this place." and offers to show the state or the national data. Data center sites have no city in their source, so with a city chosen the sites screen shows the state and says so in its sentence and caption.

### The voice

Headlines and context lines come from pure functions in `web_app/src/utils/dataStory.ts`, tested in `dataStory.test.ts`.

- Use counts, rankings, shares, contrasts and change over time. Name the scope in the sentence.
- A share or a ranking is stated only from whole-scope counts the endpoint returned. A list that is capped says "most recent N" and never gives a share or a trend.
- A sentence that ends in a question leads to the next screen only when the next screen answers it.
- No causes ("because", "due to", "driven by"), no forecasts, no judgments (good, bad, worrying, best, worst, should, problem, crisis) and no claim about what people in general think. The records are meeting records, not a survey, and a concern count is a count of passages, not of people.
- A header never starts with a number, so a sentence that would start with a count starts with a word ("Of 26 data center sites in Alabama, 14 are operating, ...").
- Missing data gives a neutral description of the chart, never a filled-in number.

### Colours

The hub, the story and the challenge use the Open Navigator house theme from `web_app/src/utils/folioThemes.ts` (the one the Data explorer Matrix map defaults to), applied as custom properties on the page wrapper through `web_app/src/utils/houseTheme.ts`. The challenge's reveal bars are Agree in the teal accent, Disagree in amber and Not sure in neutral, each with a text label and count so colour is never the only cue. Dot groups use the theme's segment colours in order.

## What a chart shows

The charts are the challenge's (`ChartPanel`): dots for individual records (each dot focusable, opening its source, with arrow-key movement), ranked bars with count and share, an honest note when the list is capped, a FIG. caption with source and scope, and **Show data table**. A long figure scrolls inside its own frame so the headline stays in view.

## Add a story

1. Add the screens to `web_app/src/utils/dataStory.ts` (a list like `DATA_CENTER_STORY`: an `id`, a short word, the dataset key and the kind) and a function per screen that returns its headline and context from the endpoint's response. Add them to `screenText` and cover them in `dataStory.test.ts`, including the empty and failed cases and the banned wording.
2. If the story needs a dataset the charts do not have yet, add it to `chartSpec` in `web_app/src/utils/stanceGame.ts` and to `fetchChartData` in `web_app/src/api/stance.ts`, with its test.
3. Register the story in `STORIES` in `web_app/src/pages/DataStory.tsx` and add its card to the hub in `web_app/src/pages/DataStories.tsx`.
4. If it has a challenge, add the pack as described in [Data Center Challenge](data-center-challenge.md).
5. Update this page.

## Moving to the next screen

When you have been still for a couple of seconds on a screen that has another one after it, a small cue appears at the bottom of the window with a chevron that moves downward. It says "Scroll" with a mouse or trackpad and "Swipe up" on a touch screen. Pressing it goes to the next screen, the same as Continue. It hides while the page is moving and does not appear on the last screen. With reduced motion turned on in your device settings, the chevron is still.
