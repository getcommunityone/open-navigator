---
title: Where Do You Stand? game design
description: Design and API contract for the agree/disagree game that shows a player where they stand against the nation, their state and their community.
---

# Where Do You Stand? game design

Issue #851 builds the API and storage. The game screens are separate work.

## What the game is

The game is played in rounds. Each round shows a chart about a topic (the first topic is data centers) and puts one opinion statement to the player. The player answers **agree**, **disagree** or **not sure**. There is no right or wrong answer.

After the answer, the reveal shows how everyone who played answered: nationally, in the player's state and in their community. A group is shown only when enough people have answered (see decision 4).

## Decisions and reasons

### 1. The name and the look are original

The working name is "Where Do You Stand?". The owner pointed to a 1990s quiz-show computer game as the pace to aim for. We take the genre's mechanics: one question at a time, big animated round numbers, category cards and a punchy reveal. We do not take that game's name, artwork, audio or jokes. Everything the player sees and hears is our own.

### 2. Three answers, not two

Some people are neither for nor against. A forced two-way choice would push them into an answer they do not hold and distort the split. "Not sure" is a real answer and is counted and shown.

### 3. Anonymous play

A player has a random id made in the browser. There is no login. We do not store the IP address.

What this means for ballot stuffing: a person can clear their browser data and answer again. We limit it as far as we reasonably can. Each id has one answer per statement, and answering again replaces the earlier answer. Each visitor is rate limited in memory. We do not claim more than that. This is **not a scientific poll**. The reveal must say "of people who played", never "of residents".

### 4. Minimum sample of 30

A group's split is shown only when at least 30 people in that group have answered the statement. Below that, a small group can reveal one person's answer, and a handful of answers says little. Below the minimum the count `n` is still shown, but the agree / disagree / not sure split is withheld. The minimum is set with `STANCE_MIN_SAMPLE` (default 30, never below 1).

### 5. Statements are ours, versioned in git

We write the statements. They live as JSON packs in `api/stance_packs/` and change through pull requests. Each statement has a `version`. Every answer records the version it answered. Results count only answers to the statement's current version, so rewording a statement starts a fresh count and never mixes answers to different wording.

### 6. No foreign keys

The statements live in git, not in a table, so `pack_id` and `statement_id` have nothing to point at. Places are free text matched within a state, and `public.jurisdictions` is a view, which cannot be the target of a foreign key. The table has a primary key and a unique key on one answer per player per statement.

### 7. Runtime-owned, excluded from the production copy

`public.stance_response` is created by the API when it first runs and is written by the running production app. It is in `RUNTIME_OWNED` in `sync_public_to_neon.py` and in `PII_EXCLUDE_TABLES` in the Makefile, so a deploy or a local mirror never overwrites production answers.

## Contract

### Table `public.stance_response`

One row per player per statement. The API creates it with `CREATE TABLE IF NOT EXISTS`.

| Column | Type | Notes |
| --- | --- | --- |
| `stance_response_id` | bigserial | Primary key |
| `player_id` | uuid, not null | Random id from the browser |
| `pack_id` | text, not null | |
| `statement_id` | text, not null | |
| `statement_version` | integer, not null | The version answered |
| `answer` | text, not null | `agree`, `disagree` or `unsure` |
| `state_code` | char(2) | Two-letter code |
| `state` | text | Full name, derived by the server from `state_code` |
| `place_name` | text | Trimmed, up to 120 characters |
| `created_at` | timestamptz, not null | Default now() |
| `updated_at` | timestamptz, not null | Default now(), set on each re-answer |

Unique on `(player_id, pack_id, statement_id)`. Index on `(pack_id, statement_id, state_code)`. Nothing else is stored: no IP address, no name, no email.

### Pack file

`api/stance_packs/data_centers.json` holds `pack_id`, `title`, `version` and a list of statements. Each statement has `statement_id`, `version`, `order`, `category`, `statement` and `chart`. The `chart` value is the key of an existing `/api/data-centers/*` endpoint (`job-claims`, `sites`, `agenda-items`, `concerns`, `meeting-mentions`, `community-events` or `projects`) whose data the round shows. Packs are checked when the API starts: ids must be unique, required fields present and orders distinct.

### Endpoints

- `GET /api/stance/packs` returns `[{pack_id, title, version, statement_count}]`.
- `GET /api/stance/packs/{pack_id}` returns the pack, or 404.
- `POST /api/stance/responses` takes `{player_id, pack_id, statement_id, answer, state_code?, place_name?}`. It saves the answer, replacing an earlier answer by the same player (and updating the place), and returns `{stance_response, results}` where `results` is that statement's results. It returns 404 for an unknown pack or statement, 422 for a bad answer or id, 400 for an unknown state code, a place name over 120 characters, or a place without a state, and 429 when the rate limit is exceeded.
- `GET /api/stance/packs/{pack_id}/results?state_code=&place_name=&player_id=` returns `{min_sample, statements: [{statement_id, statement_version, your_answer, national, state, place}]}`. Each group is `{available, n, agree, disagree, unsure}`. `available` is true only when `n` is at least `min_sample`; otherwise the three counts are null and only `n` is given. `state` and `place` are null when the request names none. `your_answer` is null without a `player_id` or without an answer. Place matching ignores case and surrounding spaces and works within the same state. An empty table gives `n: 0, available: false` for every group.

### Settings

- `STANCE_MIN_SAMPLE` (default 30, minimum 1).
- `STANCE_RATE_PER_HOUR` (default 120). The limiter keeps a hash of the visitor's IP and player id in memory only. The hash is never written to the table or to logs.

## Not done yet

- The game screens. Issue #847 gives the chart sections; a follow-up issue builds the rounds.
- More topic packs.
- Answers linked to a login.

## Update, November 24, 2026

The game screens were built in #852 (`/play/data-centers`; guide: [Data Center Challenge](../guides/data-center-challenge.md)).
Still not done: more topic packs, login-linked answers, and the charts of stance by speaker, which wait for the
public comment data to be loaded.

## Update, November 24, 2026 (#884): names, routes, data stories

The game is now the **Data Center Challenge** (`title` in `api/stance_packs/data_centers.json`). Its address is
`/challenge/:packId` (`/challenge` goes to `/challenge/data-centers`); `/play` and `/play/:packId` redirect to it and keep
the query string. A new family of scrolling **data stories** lives at `/stories` (the hub) and `/stories/:storyId`
(first story: `data-centers`); the story reads the same data-center endpoints and uses the same scroll engine
(`web_app/src/components/stance/useActs.ts`, which the challenge and the story share). The challenge's headers no longer carry
numbers ("Round 1 of 8", "01 / 08" are gone): the category word is the header, and each screen ends with **Continue to ...**
and, after the first, **Back**. Guide: [Data stories](../guides/data-stories.md) and
[Data Center Challenge](../guides/data-center-challenge.md).

On November 24, 2026 the owner set the rule that a challenge statement must sit beside a chart built from meeting recordings or
transcripts. Two statements (`enough-already`, `near-homes-ok`) were re-paired with the concerns chart, and "Tax breaks for data
centers are a fair trade for the investment they bring." (`tax-breaks-fair`) was removed until transcript-based data on incentives
exists. Wording and statement versions are unchanged; the pack version went from 1 to 2 and `order` now runs 1 to 7. No answers had
been recorded. A story or a challenge needs recordings or transcripts behind it; figure-only data, such as census measures, is shown
under Explore.

## Update, November 24, 2026 (#899): pacing in three beats, and sound

The owner's feedback was that a round showed everything at once, and that it should show the data and its conclusion first, then
ask the player where they stand, with sound to give it energy. Later the same day the owner said what the challenge is: not a
quiz on facts, but questions where there were open, documented disagreements in meetings, with facts on both sides. That shapes
the design.

- **Three beats.** `roundBeat(state)` in `web_app/src/utils/stanceGame.ts` returns `finding`, `question` or `results` from
  whether the round is answered, asked or being changed. Beat 1 is "what the record shows": the finding sentence as the title and
  the chart drawing in. The question arrives on **Ask me** or Space, or by itself once the chart has finished and a pause (2.5 s)
  has passed; the timer never runs while the player is on the chart or its table, while a menu is open, or while the tab is hidden.
  The answer buttons are not rendered before the question, so they cannot be focused or hit by the A, D and N keys. A round
  already answered goes straight to the results.
- **No right answers.** Nothing in the words, the sounds or the visuals implies a right or wrong answer or a score. The prompt
  is "Where do you stand?". The `lock` cue is one pitch, so it cannot sound like a verdict. The results copy still says how people
  who played answered and that it is not a poll.
- **Both sides.** `RoundPanel` accepts an optional `sides` prop (`for` and `against` lists of verbatim passages, each with its
  speaker role, jurisdiction, meeting date and a recording link at the timestamp). It shows them in beat 1 only when both sides
  have at least one real passage; otherwise nothing renders. No endpoint feeds it yet; a separate issue adds one.
- **Sound.** `web_app/src/utils/stanceSound.ts` makes five cues from oscillators and gain envelopes (`open`, `question`, `lock`,
  `bar`, `finish`); `cueNotes(cue, step)` is the pure note list and is unit tested. One shared AudioContext is made lazily, only
  after the first pointer or key press and only when sound is on, through a master gain of 0.15. The setting `stance.sound`
  (`on` or `off`) is read and written through guarded `localStorage` calls. A browser without Web Audio stays silent. Every cue has
  a visible counterpart, so sound is never the only signal. The cues are our own short motifs; nothing is taken from any
  existing game or show.
- **Scroll.** The pinned, scroll-scrubbed acts (`useActs.ts`) stay. With the `beats` option the timeline no longer scrubs the
  chart draw, the question block or the reveal; the round plays those on a clock. Scrolling past an unanswered round still counts
  as skipping it.

## Update, November 24, 2026 (#915): the story opens on a question, and phones get kinetic screens

The owner's feedback on the live `/stories` page was that the two introductory paragraphs were awful, that the story should start
with a question ("should we allow new data center", with yes, no or a moratorium), then the scope, that the last screen should
challenge the reader on their opinion and record their votes, and that the story and the challenge should have kinetic scrolling.
Later feedback from a phone added: scrolling should stop on the next screen, screens and titles should animate in and out, one
obvious next step should always be on screen, and the quiz-show energy belongs to the challenge only.

### Decisions and reasons

- **One question per pack, in the pack file.** The question, its place wording and its options live beside the statements in
  `api/stance_packs/`, so the hub, the story's three vote screens and the API all read one source. The pack `version` is 3.
- **A second table, not more rows in `stance_response`.** `stance_response.answer` is checked against agree / disagree / unsure
  and is unique per reader and statement. The question has its own options and two answers per reader (before and after), so it
  gets `public.stance_choice_response`, unique per reader, question version and moment.
- **The answer follows the place the reader names.** The owner's order is question first, place second, so a first answer is
  usually given with no place. When the reader then names a state or community, the story stores the answers they have already
  given again with that place (same row, updated). Without that the "before" split for a state or community could only ever
  count readers who arrived with a place already in the link. Broadening to the country never removes a place from a stored
  answer.
- **Same withholding as the challenge.** A group below `STANCE_MIN_SAMPLE` returns `available: false`, its real `n` and
  `counts: null`. Counts for an option id that is no longer in the pack are left out. Nothing is seeded.
- **Phones use CSS scroll snap, not the pinned engine.** Pinning with GSAP ScrollTrigger and Lenis on touch fights the phone's
  momentum scrolling and the address bar resizing the window. Scroll snap with `scroll-snap-stop: always` on full-height screens
  (`svh`) is the browser's own mechanism and lands one screen per swipe. `useActs` marks each screen `data-state="in"`, `above`
  or `below` (and `data-leaving` while it is going), and `stance.css` plays the entrance, the exit and the word-by-word titles from
  those states with transitions, so re-entering a screen replays them. Modes: `pinned` (wide), `snap` (phone), `stacked` (reduced
  motion).
- **One wheel gesture, one screen.** In `snap` mode a wheel or trackpad gesture is turned into exactly one screen, because scroll
  snap alone lets one hard flick pass several. In `pinned` mode the scroll is held at the hold next to the one the reader was
  on. A block that still scrolls inside a screen keeps the wheel.
- **Scrubbed values are written from the timeline.** `--draw`, `--reveal` and the new `--title` are written from the timeline's
  own update and refresh, not from each tween: a timeline that starts part-way through (a deep link) renders without firing its
  tweens' callbacks, which left charts undrawn.
- **Always one primary action in view.** A screen marks its primary control with `data-primary`. `FloatingNext` watches it with
  an IntersectionObserver and, only while it is out of view, shows the same action in a bar at the bottom of the window. The bar
  presses the real control and is hidden from assistive technology, so there is one focus stop and one name.
- **Two energies, one family.** The story and the hub are calm (rises, fades, a steady button). The challenge (`data-beats`) adds
  the spring, the arrow nudge, the light sweep, the ring on the chosen answer and popping progress segments. All of it is off
  under `prefers-reduced-motion`. Every motif is our own; nothing is taken from any existing game or show.

### Contract

Pack file: `question` is `{ question_id, version, text, place_text, options: [{ id, label }] }`. `place_text` must contain
`{place}`; there are at least two options with distinct ids. For data centers: `allow-new`, version 1, "Should we allow new data
centers?", `Should {place} allow new data centers?`, options `yes` (Yes), `no` (No), `moratorium` (Pause for now).

Table `public.stance_choice_response` (runtime-owned, created by the API on first use like `stance_response`; grain: one row
per reader, pack, question, question version and moment):

| Column | Type | Notes |
| --- | --- | --- |
| `stance_choice_response_id` | bigserial | Primary key |
| `player_id` | uuid | The anonymous browser id |
| `pack_id` | text | |
| `question_id` | text | |
| `question_version` | integer | The question's version when answered |
| `moment` | text | `before` or `after` |
| `choice` | text | One of the pack's option ids (checked by the API against the pack) |
| `state_code` | char(2) | Nullable |
| `state` | text | Full name, nullable |
| `place_name` | text | Nullable; only with a state |
| `created_at`, `updated_at` | timestamptz | |

Unique on (`player_id`, `pack_id`, `question_id`, `question_version`, `moment`). No foreign keys, for the reason in decision 6.

Endpoints:

- `GET /api/stance/packs/{pack_id}` returns the pack with its `question`.
- `POST /api/stance/choices` with `{ player_id, pack_id, question_id, moment, choice, state_code?, place_name? }` stores or
  replaces the answer and returns `{ stance_choice_response, results }`. It shares the rate limit of `/api/stance/responses`.
  404 for an unknown pack or question, 422 for a choice that is not one of the pack's options or a moment that is not `before`
  or `after`, 400 for an unknown state or a place without a state.
- `GET /api/stance/packs/{pack_id}/choice-results?player_id=&state_code=&place_name=` returns
  `{ min_sample, question_id, question_version, your: { before, after }, before: { national, state, place }, after: { national, state, place } }`.
  Each group is `{ available, n, counts }`, with `counts` an object of option id to count, or null below the minimum sample.
  `state` and `place` are null when no state or community is asked for.

Front end: the story's `?screen=` takes `question` (first), `scope` (second) and `verdict` (last). `turn` still opens the last
screen.

### Not done

- The Analysis page (`DataExplorerMatrixPage`) does not use this engine and was not changed.
- The motion was checked in headless Chromium with touch emulation at 390 by 844 and 360 by 640, not on a physical phone.
