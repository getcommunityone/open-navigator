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
