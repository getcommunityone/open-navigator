---
sidebar_position: 38
title: Legistar actions and roll-call votes
description: What the Legistar Web API returns for actions and votes, and what we load into bronze (#633).
---

# Legistar actions and roll-call votes

Issue [#633](https://github.com/getcommunityone/open-navigator/issues/633) (design:
[agenda-first](./data-center-agenda-first-design.md)). Checked against the public
Legistar Web API (`webapi.legistar.com`) using the Dakota County client, 2026-11-19.

## Event-items feed (`/v1/<client>/events/<id>/eventitems`)

Already fetched with `AgendaNote=1&MinutesNote=1`. Per item, **action / result fields
present on the JSON** (may be null until minutes are taken):

| Field | Meaning |
|---|---|
| `EventItemActionId` | Action type id (nullable) |
| `EventItemActionName` | Short action label (e.g. `Approved at Committee`) |
| `EventItemActionText` | Narrative of the motion / result |
| `EventItemPassedFlag` | Numeric pass/fail flag (nullable) |
| `EventItemPassedFlagName` | e.g. `Pass` |
| `EventItemMinutesNote` | RTF/plain minutes note |

**We already load** action name, action text, passed flag name, and minutes notes into
`bronze.bronze_platform_meeting.minutes_text` (plain text, RTF stripped).

A passed flag **alone** (no note and no action text) is **not** treated as minutes.

## Roll-call votes (separate endpoint)

**Not** embedded on the event-item object. Available at:

```text
GET /v1/<client>/eventitems/<EventItemId>/votes
```

Example row keys observed: `VoteId`, `VotePersonId`, `VotePersonName`, `VoteValueId`,
`VoteValueName` (e.g. `Ayes`), `VoteResult`, `VoteSort`, `VoteEventItemId`, …

Empty list `[]` when there was no recorded roll call.

**As of #633 we load these** when an item already shows an action / passed flag:

- Appended into `minutes_text` as `Roll call: Name: Value; …`
- Stored structured on `bronze.bronze_platform_meeting.votes_json` as an array of
  `{ event_item_id, title, action_name, passed_flag_name, votes: [{ vote_id, person_id,
  person_name, value_id, value_name, result, sort }] }`

## Product implication (agenda-first)

- **Headline** can come from the agenda item (`agenda_text` / event items).
- **Outcome** (`outcome_code` = passed / failed / not_known) can later use
  `EventItemPassedFlagName` and/or roll-call `VoteValueName` from `votes_json` /
  `minutes_text`, without inventing a result from the agenda alone.

## Warehouse check (2026-11-19 / #633 run)

Site-belt Legistar after `--full` on survey clients (then incremental pattern discovery):

| Portal | Meetings | With `votes_json` / roll call in `minutes_text` |
|---|---:|---:|
| `dakota` | 193 | 144 |
| `fulton` | 53 | 48 |
| `atlantaga` / `goodyear` | 0 events since 2025-01-01 | — |

National Legistar after the run: **3,862** meetings; **203** with `votes_json` (mostly Dakota/Fulton —
pattern portals landed earlier without a `--full` vote backfill). A full national `--full` vote
pass is slow (per-item `/votes` + VPN retry on timeouts); treat site-belt backfill as done and
pattern-portal vote fill as a follow-up ops pass.

`dbt run --select stg_platform_meeting_documents event_meeting_document data_center_agenda_item`
completed (7,275 document rows; **84** `data_center_agenda_item` rows — still thin outside
Legistar text that matches the DC regex).

## Regenerating

```bash
# Site belt + find more Legistar clients (incremental)
python -m scrapers.platforms.run --data-center --pattern-target 20 --apply
# Re-fetch items+votes for already-landed meetings (expensive)
python -m scrapers.platforms.run --data-center --full --apply
```

`--full` re-reads meetings already landed so vote rows backfill; incremental runs only
pick up meetings whose `EventLastModifiedUtc` changed.
