---
title: Data Center Challenge
description: How to play the Data Center Challenge, what the reveal means and does not mean, the minimum sample rule, privacy, keyboard keys, the sources and limits of each chart, and how to add a topic pack.
---

# Data Center Challenge

The challenge (earlier called the "Where Do You Stand?" game) is about questions that people openly disagreed about in local meetings. Each round first shows what the record says, and, where a source supplies them, what was said on both sides. Then one opinion statement asks where you stand. You answer **Agree**, **Disagree** or **Not sure**, then see how people who played answered. It is not a quiz: there is no right answer, no answer key and no score. The first topic is data centers, with seven statements. Open it at `/challenge/data-centers`, from the Data stories page (`/stories`), the end of the [Data Center Story](data-stories.md), the Data centers page or the Data explorer Matrix page. The old address `/play/data-centers` redirects to it and keeps the place in the address.

## How to play

1. The first screen says what the game is and shows large counts of what the public records cover. Each count comes straight from a national data-center endpoint. A count that is missing or zero is left out.
2. Each round is three full-viewport scroll stops in order (see [Pacing and sound](#pacing-and-sound)): the finding and chart, then the question (answers below the fold), then the reveal.
3. The headline is one sentence about the chart, computed from the chart's own data (for example a ranking, a count or a share). If the data cannot support a sentence, the headline describes the chart in neutral words.
4. Choose an answer. Your choice locks in, it is saved when the server confirms it, and the results land. The page carries you to the reveal. If saving fails you see the error with a Retry button and the page does not move on.
5. You can scroll ahead past a round without answering it (**Skip this one**, or the wheel). A skipped round shows no results. The end screen counts only the rounds you answered.
6. Come back to an answered round and you see your stored answer and the reveal, with **Change my answer**.

Pick your place with **Your place** in the bar at the top: it opens a dialog where one search box takes a city, county or ZIP code, with **National only**, **All of [state]** and a state list beside it. The label next to it always says what the results are filtered to ("National only", "Alabama", "Tuscaloosa, Alabama"). The place is kept in the address (`?state=AL&city=Tuscaloosa`), so a refresh, a shared link and the back button keep it. A county pick applies its state, since results are by city or state.

## Every statement sits beside meeting records

A challenge statement must sit beside a chart built from meeting recordings or transcripts (jobs claims, concerns, meeting passages, agendas, company-hosted meetings). The pack has seven statements; two of them ("My area already has enough data centers" and "A data center that meets the rules should be allowed near homes") are shown beside the concerns chart. If a round's chart ever comes from another source (sites, projects), the screen marks it "For context" with its source named. The "near homes" round also notes how often land and property concerns appear in the same data, when the data has them.

## Keyboard

| Key | Does |
| --- | --- |
| Space, Enter, PageDown, down arrow or right arrow | On the Finding stop: move to the Question stop (Ask me or the ask timer). On the Reveal stop: next round (or start the first round from the first screen) |
| A | Agree (only once the question is showing) |
| D | Disagree (only once the question is showing) |
| N | Not sure (only once the question is showing) |
| PageUp, Shift+Space, up arrow or left arrow | Previous round |
| Home, End | The first screen, the end screen |
| Arrow keys inside a unit chart | Move between dots |

Focus moves to **Ask me** when a round settles, then to the answer buttons once they show, and to **Next** once the results have landed. Keys that move between rounds do nothing while focus is in a field, a select, a table or a figure that scrolls on its own, and touch scrolling is never taken over. Each round ends with a **Next: ...** button that names the next category in words, and, after the first, a quieter **Back**. Nothing in the headers or the progress rail is a number: the category is the header and each stop in the rail is named after its screen.

## Pacing and sound

A round is three scroll stops (not three beats on one pinned panel). Each stop fills one viewport; the page scrolls between them, with smooth auto-scroll when motion is allowed. Full behaviour is in [Challenge scroll-to-answer and scroll reveal](../development/challenge-scroll-reveal-design.md).

| Stop | On screen | How you leave |
| --- | --- | --- |
| **Finding** | Category, record headline, chart, optional quotes; **Ask me** / **Skip this one**. Answer buttons are not visible yet. | **Ask me**, Space, or the ask timer → scroll to Question |
| **Question** | "Where do you stand?" and the statement fill the viewport; **Agree**, **Disagree** and **Not sure** as large stacked pills **below the fold** (scroll or auto-scroll to reach them). **Skip this one** is offered; **Next** is not. | Answer locks → short hold → scroll to Reveal |
| **Reveal** | Your choice (opinion only — never "right" or "wrong") → how people who played answered (national, state, place bars) → **Next: ...** | **Next** or keys → next round's Finding |

**Finding.** The category and finding sentence are the title, with the chart drawing in. Under them sit **Ask me** (Space) and **Skip this one**. If a source supplies verbatim quotes, "What was said for" and "What was said against" blocks sit here, each quote linked to its recording; nothing is shown unless both sides have real quotes. After the chart finishes and a pause of about two and a half seconds, the page scrolls to the Question stop unless you already pressed **Ask me**; a thin line under **Ask me** shows time left. The timer waits while focus is on the chart or its data table, while the table is open, while a menu is open, or while the tab is hidden.

**Question.** The statement is large at the top of the viewport; the three answers are a stacked column under it, so on a short screen you scroll (or are scrolled) to reach them. The chart may stay, quieter, or hide on a phone so the question stop stays readable.

**Reveal.** Your answer locks in; the other two step back. National, state and place results land one after another. A group with too few answers reads "Not enough answers yet (N so far, M needed)". **Next: ...** comes last. A round you already answered opens on the Reveal stop (you can still **Change my answer**).

Each stop is laid out for one viewport at 1366×768 and 390×844.

**Sound** is made in the browser (Web Audio), with no audio files: a short cue when a round opens, when the question arrives, when your answer locks in, as each result row lands (the pitch steps up for national, state and place, and a withheld split makes no sound), and on the end screen. The cues are neutral. None says right or wrong, and nothing is scored. Every cue has a visible counterpart, so nothing depends on sound. The **Sound on** / **Sound off** button is in the bar at the top of every screen of the challenge. Your choice is kept on this device (`stance.sound` in local storage; the default is on), and sound starts only after your first click or key press. Cues are quiet by design.

For a screen reader, a polite live region reads the finding, then the question, then the results.

## Motion

Within a round, scroll moves among the three stops (Finding → Question → Reveal). Between rounds, the challenge still follows the same pin-and-snap patterns as the data story ([How the screens move](data-stories.md#how-the-screens-move)):

- **768 pixels or wider:** rounds stay pinned and scrubbed by scroll; one gesture does not skip past more than one round. Inside a round, scroll (or auto-scroll after **Ask me**, the timer, or locking an answer) snaps to the next stop.
- **A phone:** the page snaps stop by stop inside each round, and one round per swipe between rounds. Entrances and exits on category, headline and chart match the data story; a tall chart scrolls inside its block on the Finding stop first.
- **prefers-reduced-motion on:** the same three stops in a plain stack with native scrolling and no animated auto-scroll — use buttons, keys, or an instant jump instead. **Ask me**, Space, and the timer still reach the Question stop; answering still reaches Reveal. Sound on/off and all controls work the same.

The challenge is the livelier of the two pages. Its main button (**Start the challenge**, **Ask me**, **Next: ...**) springs in when its round is in view and squashes when pressed. When you have been still for about six seconds its arrow hops twice and a light passes across it, at most three times, with one soft sound on the first if sound is on (the rules are in [Data stories](data-stories.md#moving-to-the-next-screen)). The answer you choose locks and throws a ring while the other two step back. The progress segments along the top bar pop as a round arrives or is answered (an answered round turns ink), and the words beside them say what is left ("Three to go"). None of it says right or wrong. The data story uses the same layout, palette and type with calmer motion; with **Sound on** it still plays soft page-turn cues when you advance or when the idle nudge first fires (#966).

One primary action is always on screen: **Start the challenge** on the first screen, then per stop **Ask me**, the three stacked answers, and **Next: ...**. When that control is out of view, a bar pinned to the bottom of the window shows the same action (the three answers as three buttons), with **Back** beside it.

## What the reveal means

The reveal shows, as a horizontal bar with counts and percentages, how **people who played** answered: nationally, in your state and in your community. It means that and no more.

- It is **not a poll**. Anyone can play, nobody is sampled, and the people who played are not a sample of any population.
- It does not say what any larger group of people thinks.
- A person can clear their browser data and answer again. Each browser has one answer per statement, and answering again replaces the earlier one. Each visitor is rate limited.
- "Not sure" is a real answer and is counted.

### The minimum sample

A group's split is shown only when at least **30** people in that group have answered the statement (the API setting `STANCE_MIN_SAMPLE`). Below that you see "Not enough answers yet (N so far, M needed)" and never a split. On an empty database every group says "Not enough answers yet (0 so far, 30 needed)".

## Privacy

Your browser makes a random id and keeps it in local storage under `on_stance_player_id`. That is the only thing stored about you in the browser. The server stores your id, the statement, your answer and the state and community you chose. It does not store your IP address, name or email. The rate limiter keeps only a hash in memory.

## Sources and limits

Every chart has a caption that names its source and what it counts. The numbers are real counts from the Open Navigator warehouse through the `/api/data-centers/*` endpoints. If a chart has no data, the round says "No data available for this chart" and you can still answer.

- **Meeting records are not a survey.** The charts count what appears in local meeting records (transcripts, agendas) and in news and company announcements. They do not measure what the public thinks.
- **Charts follow your place as far as their source allows.** With a state they are for that state; with a community they are for that community wherever the source can narrow to one. Data center sites have no community in their source, so that chart stays at the state and its sentence and caption say so. With no state they are national, and the caption says which.
- **Dot charts draw one dot per record,** up to 500. When there are more records than dots, the caption says "Showing the most recent 500 of N" and the group percentages are shares of the dots drawn. A dot with a link opens the source record (a meeting video at the moment, an agenda document, an article, a site's source page).
- **Ranked bars show a count and a share of the counted total.**
- **Site data** comes from Epoch AI (CC BY 4.0). Sites no longer listed by the source stay in the list.
- **Not available yet:** charts that split speakers into in favour, opposed and asking questions need public comment records, which are not loaded. They are not drawn and nothing stands in for them.
- The dots are small. Use the arrow keys to move between them and the data table under each chart for the group counts.

## Add a topic pack

A pack is a JSON file in `api/stance_packs/`, changed through a pull request. It holds `pack_id`, `title`, `version`, an optional `question` and a list of statements. The `question` is the one the topic's data story opens and closes on: `question_id`, `version`, `text` (for the whole country), `place_text` (with `{place}` where a place name goes) and `options` (each an `id` and a `label`, at least two). Rewording the question or changing its options means raising its `version`, which starts a fresh count. Each statement has `statement_id`, `version`, `order`, `category`, `statement` and `chart`. The `chart` value must be one of `job-claims`, `sites`, `concerns`, `meeting-mentions`, `agenda-items`, `community-events` or `projects`; a new kind of chart needs a new function in `web_app/src/utils/stanceGame.ts` and its test.

The API checks packs when it starts: ids must be unique, required fields present and orders distinct. Rewording a statement means raising its `version`, which starts a fresh count: results count only answers to the current version. The game lists other packs on its end screen and links to them. The design and the API contract are in `development/where-you-stand-game-design`.
