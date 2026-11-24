---
title: Where Do You Stand? game
description: How to play the Where Do You Stand? game, what the reveal means and does not mean, the minimum sample rule, privacy, keyboard keys, the sources and limits of each chart, and how to add a topic pack.
---

# Where Do You Stand? game

The game puts one opinion statement to you at a time. You answer **Agree**, **Disagree** or **Not sure**, then see how people who played answered. There is no answer key. The first topic is data centers, with eight statements. Open it at `/play/data-centers`, or from the Data centers page and the Data explorer Matrix page.

## How to play

1. The first screen says what the game is and shows large counts of what the public records cover. Each count comes straight from a national data-center endpoint. A count that is missing or zero is left out.
2. Each round is one screen. A category card and a large round word arrive, then the chart builds as you scroll, then the headline, the statement and the three answers settle into place.
3. The headline is one sentence about the chart, computed from the chart's own data (for example a ranking, a count or a share). If the data cannot support a sentence, the headline describes the chart in neutral words.
4. Choose an answer. It is saved when the server confirms it, and the page carries you to the reveal. If saving fails you see the error with a Retry button and the page does not move on.
5. You can scroll ahead to look at a round before you answer it. An unanswered round shows its answers and no results. The end screen counts only the rounds you answered.
6. Come back to an answered round and you see your stored answer and the reveal, with **Change my answer**.

Pick your place with **Your place** in the bar at the top: a state and a community. The label next to it always says what the results are filtered to ("National only", "Alabama", "Tuscaloosa, Alabama"). The place is kept in the address (`?state=AL&city=Tuscaloosa`), so a refresh, a shared link and the back button keep it. Community suggestions come from a place lookup; results match the community name you enter exactly, ignoring capital letters.

## Keyboard

| Key | Does |
| --- | --- |
| A | Agree |
| D | Disagree |
| N | Not sure |
| Enter or right arrow | Next round (or start round one from the first screen) |
| Left arrow | Previous round |
| Arrow keys inside a unit chart | Move between dots |

Focus moves to the answer buttons when a round settles, and to **Next round** after you answer.

## Motion

With **prefers-reduced-motion** on, or on a screen narrower than 768 pixels, the game is a plain stack of panels with native scrolling and everything already in its final state. There is no smooth scrolling, pinning or scroll-driven animation. All buttons and keys work the same.

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

- **Meeting records are not a survey.** The charts count what appears in public meeting records (transcripts, agendas) and in news and company announcements. They do not measure what the public thinks.
- **A state filter narrows the chart; a community filter does not.** Charts are scoped to your state when you pick one, otherwise they are national, and the caption says which. Data center sites cannot be narrowed below a state.
- **Dot charts draw one dot per record,** up to 500. When there are more records than dots, the caption says "Showing the most recent 500 of N" and the group percentages are shares of the dots drawn. A dot with a link opens the source record (a meeting video at the moment, an agenda document, an article, a site's source page).
- **Ranked bars show a count and a share of the counted total.**
- **Site data** comes from Epoch AI (CC BY 4.0). Sites no longer listed by the source stay in the list.
- **Not available yet:** charts that split speakers into in favour, opposed and asking questions need public comment records, which are not loaded. They are not drawn and nothing stands in for them.
- The dots are small. Use the arrow keys to move between them and the data table under each chart for the group counts.

## Add a topic pack

A pack is a JSON file in `api/stance_packs/`, changed through a pull request. It holds `pack_id`, `title`, `version` and a list of statements. Each statement has `statement_id`, `version`, `order`, `category`, `statement` and `chart`. The `chart` value must be one of `job-claims`, `sites`, `concerns`, `meeting-mentions`, `agenda-items`, `community-events` or `projects`; a new kind of chart needs a new function in `web_app/src/utils/stanceGame.ts` and its test.

The API checks packs when it starts: ids must be unique, required fields present and orders distinct. Rewording a statement means raising its `version`, which starts a fresh count: results count only answers to the current version. The game lists other packs on its end screen and links to them. The design and the API contract are in `development/where-you-stand-game-design`.
