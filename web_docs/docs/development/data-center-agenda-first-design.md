---
sidebar_position: 36
title: Data center agenda-first design
description: Staged plan to cover agendas for data-center governments, then prefer agenda evidence over model decisions (2026-11-19).
---

# Data center agenda-first design

Decision recorded 2026-11-19 (amended same day). Parent epic:
[DC · Data Center Accountability](https://github.com/getcommunityone/open-navigator/issues/236).

## Problem

Transcript mentions and Gemini decision lists outpace official agenda coverage. Near Epoch
sites we have ~97 governments surveyed but almost no agendas in the warehouse; nationally
only a thin Legistar/SuiteOne slice feeds `data_center_agenda_item`. Agendas are where
**future** items appear before the vote. We should try harder to get those documents, and
treat official agenda text as the **default** for the **headline** (what was up for
decision), with a separate coded **outcome** that may stay unknown until minutes or
transcript phrase hits exist.

## Goal (staged)

**Both, staged:**

1. **Site belt** — governments linked to Epoch `data_center_site` (~97), using the #460 survey.
2. **Mention widen** — jurisdictions that already have `data_center_meeting_mention` rows and
   still lack agendas (~564 today, after Stage 1).

## Approach C (chosen)

1. Exhaust readable platforms we already have (Legistar API text, existing PDF/doctext).
2. Build CivicPlus Agenda Center and CivicClerk readers **only after** agenda-first evidence
   is proven on current agenda data (gate).
3. Prefer agenda evidence for **headlines** when a match exists; track **outcome** separately.
4. Widen to mention jurisdictions with a known document platform; do not boil the ocean on
   YouTube-only towns first.

**Not chosen:** PDF/Legistar-only forever (leaves CivicPlus/CivicClerk dark); or building
those readers before testing agenda↔Gemini alignment.

## Constraints

- **Respect robots.txt.** No user-agent spoofing, no VPN/browser routing around a block
  (same rule as #460 / meeting-platform-readers). Granicus page fetches remain
  `robots_disallowed`; Legistar Web API text is the allowed path where both exist.
- **No fabricated data.** Quotes and counts come from warehouse rows.
- **Agenda ≠ outcome.** An agenda says what was **up for decision**, not whether it passed.
  Outcomes come later from **minutes** (when ingested, including Legistar actions/votes when
  the API returns them — see issue 2) or **transcript phrase** hits that record the
  vote/action. Until then, `outcome_code` is `not_known`.

## Upcoming agendas

**Yes — agendas for meetings that have not happened yet become rows.** If
`event_meeting_document` has `document_type` agenda (and text where extracted), it flows
into serving tables the same as past agendas. `data_center_agenda_item` already ranks
upcoming (`doc_date` ≥ today) for the Data Centers UI. Issue 5’s Gemini↔agenda check is
about meetings that already have a Gemini decision list (typically past/analyzed); that
does not exclude storing or showing future agenda rows.

## Baseline (warehouse snapshot used in design)

Approximate at design time (Neon / public + bronze):

| Signal | Approx. |
|---|---|
| `data_center_agenda_item` | 84 rows, 19 jurisdictions (mostly `source=legistar`) |
| Site-linked jurisdictions | ~97; surveyed ~92; with any agenda ~2 |
| `data_center_meeting_mention` | ~1.9k videos, ~564 jurisdictions |
| Mention videos in agenda-covered jids | ~53 |
| Site-belt document platforms (survey) | Granicus 9, CivicPlus 8, CivicClerk 7, Legistar 4, SuiteOne 1, … |

Re-measure in the scoreboard issue; do not treat these as frozen product numbers.

## Issue order (one issue → one PR)

| Order | Issue | Work | Starts when |
|---|---|---|---|
| 1 | [#632](https://github.com/getcommunityone/open-navigator/issues/632) | Site-belt (+ platform) agenda coverage **scoreboard** | Immediately |
| 2 | [#633](https://github.com/getcommunityone/open-navigator/issues/633) | Re-run Legistar/platform ingest for site belt; **inspect Legistar actions/votes** | After 1 exists |
| 5 | [#634](https://github.com/getcommunityone/open-navigator/issues/634) | **Agenda-first evidence** + Gemini↔agenda check | After 2 (uses loaded agendas) |
| — | — | **Gate:** report #634 check against pass mark below; wait for explicit go | — |
| 3 | [#635](https://github.com/getcommunityone/open-navigator/issues/635) | CivicPlus Agenda Center reader (site-belt hosts) | After go |
| 4 | [#636](https://github.com/getcommunityone/open-navigator/issues/636) | CivicClerk reader (site-belt hosts) | After go |
| 6 | [#637](https://github.com/getcommunityone/open-navigator/issues/637) | Widen agenda ingest to mention jurisdictions | After 3/4 (or go allows parallel widen of already-readable platforms) |

SuiteOne portal 403s stay on existing issues (#442 / #394); they do not block the scoreboard.

### Issue 1 — Scoreboard

Report, for the site belt and (as context) mention set:

- **Per platform:** count of site-belt governments, mention jurisdictions, and data-center
  videos behind each platform — so reader priority is decided by numbers, not guesswork.
- **Per government:** meetings with an agenda out of meetings we know of, over the
  **transcript date range** for that jurisdiction (not an unbounded calendar).
- **Blocked governments:** HTTP status and reason; robots-disallowed called out; no bypass.

Done when the report is in-repo (under `web_docs` or `data/cache/data_center_survey/`) and
each site-belt government is classified: `has_agenda` / `blocked` / `unreachable` /
`no_document_platform` / `reader_needed`.

**Delivered:** [data-center-agenda-scoreboard](./data-center-agenda-scoreboard.md)
(`python -m scrapers.discovery.data_center_agenda_scoreboard`).

### Issue 2 — Exhaust Legistar / existing ingest

Run `python -m scrapers.platforms.run --data-center --pattern-target 20 --apply` (and PDF
doctext backfill where site-belt manifests already exist). Rebuild
`event_meeting_document` → `data_center_agenda_item`. Re-score against issue 1.

**Also:** inspect whether the Legistar Web API event-items feed returns **action taken** and
**roll-call votes** per item. If yes, load them into bronze (and document the columns).
**Report what fields are present** even when empty (so issue 5 knows whether minutes/votes
can fill `outcome_code` without transcript).

### Issue 5 — Agenda-first evidence (before new readers)

**Headline vs outcome (separate codes):**

| Field | Values |
|---|---|
| `headline_source_code` | `agenda` \| `transcript_phrase` \| `model` |
| `outcome_source_code` | `minutes` \| `transcript_phrase` \| `model` \| null when unknown |
| `outcome_code` | `passed` \| `failed` \| `not_known` |
| `agenda_match_basis_code` | `meeting_id` \| `date_and_title` \| null |
| `agenda_document_id` | FK → `event_meeting_document` when matched |

**Ranking for headline:** agenda match → transcript phrase → model.

**`date_and_title` matching:** same jurisdiction + date + normalized body/title. If **more
than one** meeting is a candidate, record **no match** (`agenda_match_basis_code` null,
do not pick arbitrarily).

UI/API show the coded sources. Agenda-backed headlines quote real agenda text (site-wide
match-evidence rule). Copy states: agenda = what was up for decision; outcome may be
`not_known` until minutes or transcript phrase hits.

#### Gate pass mark (stated before the check runs)

Draft numbers — **maintainer will confirm** before “go”:

- **Go** if, among Gemini decisions on meetings that have an agenda, **at least 60%** match
  an agenda item, **and** no more than **2 of 10** sampled matches are wrong.
- The issue 5 report **starts with** the count of meetings that have **both** an agenda and
  a Gemini decision list. If that count is **under 30**, the check **cannot decide**; the
  report must say so and propose how to get more (e.g. finish issue 2 ingest, widen
  Legistar, or temporarily include more non–data-center meetings in agenda-covered
  jurisdictions for the alignment sample only).

#### Check report contents

1. Meetings with both an agenda and a Gemini decision list (n); stop-decision path if n &lt; 30.
2. Share of Gemini decisions with a matching agenda item (vs pass mark).
3. Wrong matches among a sample of 10 claimed matches (vs ≤2).
4. Missing: Gemini with no agenda item — count + **10 examples**.
5. Missing: agenda items with no Gemini decision — count + **10 examples**.
6. Match-method mix: `meeting_id` vs `date_and_title` (and no-match-due-to-ambiguous-title).

**Issues 3 and 4 do not start until that report is posted and the maintainer says go.**

### Issues 3 and 4 — CivicPlus / CivicClerk

Site-belt surveyed hosts only at first. Same bronze → `stg_platform_meeting_documents` →
`event_meeting_document` path as Legistar. Obey robots.txt; record blocked portals.

### Issue 6 — Mention widen

Diff mention jurisdictions with zero agendas → lightweight survey (reuse #460 tooling) →
ingest only where platform is already readable. YouTube-only stays “no agenda yet.”

## Out of scope

- Full national CivicPlus/CivicClerk product before the gate.
- Circumventing robots or bot protection.
- Treating agenda items alone as vote outcomes (`outcome_code` stays `not_known` until
  minutes/votes or transcript support it).
- Large Gemini browser batches for coverage (API/agenda path preferred).

## Read first

- [Data center meeting sources](./data-center-meeting-sources.md) (#460)
- [Meeting platform readers](./meeting-platform-readers.md) (#536)
- [Data center items on agendas](./data-center-agenda-items.md) (#250)
- `packages/scrapers/src/scrapers/platforms/run.py`
- `dbt_project/models/marts/data_center_agenda_item.sql`
- `dbt_project/models/marts/event_decision.sql`
- `AGENTS.md` / `CLAUDE.md` (No Fabricated Data; prefer packages over `scripts/`)

## Spec self-review

- Gate pass mark and under-30 stop rule are written before the check runs.
- Headline/outcome codes are separate (`*_code`); ambiguous `date_and_title` ⇒ no match.
- Issue 2 includes Legistar action/vote inspection; upcoming agendas are explicitly rows.
- Issue order remains 1 → 2 → 5 → gate → 3/4 → 6.
