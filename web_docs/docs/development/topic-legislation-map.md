---
title: Topic legislation map, positions and local actions
description: How a topic story's state legislation map, public-position breakdown and local-actions tracker are built from our OpenStates bills and meeting readings (#1274), the keyword and status rules, the colours, and what is left out.
---

# Topic legislation map, positions and local actions

**Issue:** [#1274](https://github.com/getcommunityone/open-navigator/issues/1274) · **Epic:**
[#1273](https://github.com/getcommunityone/open-navigator/issues/1273)

A topic story shows where policy is moving on its topic in three charts, each built only from our own records:

| Chart | Component | Endpoint | Source |
|---|---|---|---|
| State legislation map | `LegislationMap.tsx` | `GET /api/topics/{topic}/legislation` (counts per state, category, year, status) and `GET /api/topics/{topic}/legislation/{state}` (one state's bills, at most 200) | `public.topic_legislation_bill`, `public.topic_legislation_category` (OpenStates bills) |
| What the public said in meetings | `PositionBreakdown.tsx` | `GET /api/topics/{topic}/positions?state=` | `public.topic_meeting_lean` (AI reading, Jev) |
| Where local bodies acted | `LocalActionsTracker.tsx` | `GET /api/topics/{topic}/local-actions?state=` | `public.topic_meeting_lean.outcome_group` (AI reading, Jev) |

The components live in `web_app/src/components/stance/` and take `topic`, `stateCode`, `scopeLabel` and `subject`, so
any curated topic can use them. They sit in the **Where policy is moving** section of `/stories/<topic>`
(`TopicStory.tsx`), which follows the page's `?state=`. Moving them onto story screens once the screen-by-screen topic
story (#1244) lands is [#1279](https://github.com/getcommunityone/open-navigator/issues/1279).

Ballot measures are not shown: we hold no ballot-measure data on these topics (checked 2026-11-27; 0 of 10,500 Power BI
rows and 0 of 112 `gold.civic_ballotmeasure` rows mention fluoride). The source needed is
[#1275](https://github.com/getcommunityone/open-navigator/issues/1275). Nothing stands in for it.

## Data: `topic_legislation_bill`

Grain: one row per (topic_id, bill_id). PK (topic_id, bill_id); FK topic_id → `civicsearch_topic`, bill_id →
`bills.bill_uid`, (topic_id, category) → `topic_legislation_category`. Built in dbt from `bills`,
`stg_openstates__bill_abstract` (abstracts flattened from `bronze_bills_openstates`), `stg_openstates__bill` (passage date,
chapter citations) and `int_bills__session_span` (whether a session is over). Every topic in the `curated_topics` seed is
covered with no code change.

1. **Match.** A state bill (federal bills and Hawaii's "GM" governor's nominations are left out) whose lowercased OpenStates subject tags, title and abstract
   contain one of the topic's keywords as a whole word, minus the topic's `drop_keywords`.
2. **Scope** (seed `topic_legislation_scope`). The topic's `require_pattern` must match the same text, and its
   `exclude_pattern` and the `'*'` exclude must not match the title and abstract. For water fluoridation the require
   pattern keeps fluoride **in water** (fluoridation, or fluoride within a dozen words of water / supply), and the exclude
   drops refinery hydrogen fluoride, contaminant-level omnibus bills and dental varnish bills. Subject tags come first in
   the text so a short title such as Utah's "Fluoride Amendments" sits next to its "Water" tag.
3. **Direction** (seed `topic_legislation_rule`, vocabulary in `topic_legislation_vocabulary`). Matched on the title and
   abstract only, never the subject tags (an index word like "environmental protection" would trip the rules). The first
   rule by `rule_order` wins. Water fluoridation's categories:
   - **Study** — study, task force or working-group requests;
   - **Protection** — notice or health information before stopping fluoridation, or requiring / maintaining it;
   - **Restriction** — local choice to drop it (allowing a town to prohibit, opt-outs, "shall not require"), notices,
     labels, dosage limits, local votes, repeal of a mandate;
   - **Ban** — a statewide prohibition;
   - **Direction not stated** (`unclear`) — about fluoride in water, but the title and abstract don't say which way. These
     bills are kept and shown **by status only**: many titles are only "An act relating to water fluoridation programs".
   Other topics use their own vocabulary (data centers: restrict / incentive / protect) or the generic restrict / support
   / other set.
4. **Status**, from the bill's own OpenStates fields:
   - `enacted` — a chapter citation, or the latest action says signed by the governor (New Mexico writes a bare
     "Signed") / approved by governor / chaptered / became law / effective / filed with the secretary of state. A
     Speaker's or Senate President's signature is not enactment: it comes at enrollment, before the governor acts;
   - `failed` — the latest action ends the bill: died, failed to pass (a failed amendment or motion does not count),
     sine die, inexpedient, withdrawn by its sponsor (North Carolina's "Withdrawn From Com/Cal" only moves a bill and
     does not count), left in committee, laid on the table, study order (and similar); or its session is over in our
     data without enactment;
   - `passed_chamber` — neither, but OpenStates records a passage vote (`latest_passage_date`);
   - `pending` — introduced, with no passage or final action yet.
   `passed_a_chamber` is also true for a bill that passed one chamber and then died.

**Known gaps.** We hold each bill's latest action and passage date, not its full action history, so "passed one chamber"
rests on the passage date. An omnibus bill that never names the topic in its subject tags, title or abstract is missed:
Florida's 2025 agriculture bill (SB 700), whose abstract in our copy doesn't mention fluoride, is not on the map.

### Counts on 2026-11-27 (local warehouse)

Water fluoridation: 189 bills in 37 states, with latest actions from 1991 to 2026. By status: 11 enacted, 5 passed one
chamber, 45 introduced and pending, 128 failed. By direction: 43 ban, 59 restriction, 38 protection, 13 study and 36
direction not stated. The map opens on 2025–2026: 87 bills in 31 states, coloured enacted in 1 (Utah), passed one
chamber in 5 (KY, LA, MA, NY, TN), pending in 14 and failed in 11. *(The build of 2026-11-27; every `dbt build` refreshes
it, and the chart always reads the live table.)*

## The map

- **Colour = the furthest any of the state's bills got**, in the period and direction selected: enacted (darkest
  violet), passed one chamber (violet), introduced and pending (light violet), failed or died (grey). A state with no bill
  in the view stays paper with an outline. One hue for the ordered statuses, grey for the dead end, so the order reads
  without a legend and survives colour-blind viewing; the legend lists every status with its count of states.
- **Period.** The last two years with bills (default) or every year. **Direction.** Every direction, or one category.
  Both recolour the map and the counts line.
- The map loads counts only (per state, category, year and status), so a topic with thousands of bills (guns: about
  17,000) stays small. **A state** (click, tap, or Tab + Enter) loads its bills for the period and direction selected,
  at most 200, furthest along first and then newest, and says when there are more: status and direction tags, the bill number linked to its
  OpenStates page, session, title and last action. **Every state with a bill** is also listed under the map, so nothing
  depends on colour or pointer alone. The page's `?state=` opens that state by default.
- Shapes are us-atlas Albers states (`STATES_ALBERS_TOPO`); if they fail, the note says so and the list still works.

## Positions in meetings

One bar per position, counting meetings whose AI reading put the public who spoke closest to it, out of the meetings
where the public spoke on the topic. Water fluoridation's reading has five positions, named plainly:

| Stored label | Shown as |
|---|---|
| `support_require_all` | Support, require everywhere |
| `support_local_choice` | Support, each community decides |
| `no_opinion` | No opinion |
| `oppose_local_choice` | Oppose, each community decides |
| `oppose_ban_all` | Oppose, ban everywhere |

Other topics show their shared labels (mostly for / split / mostly against). Support is violet, opposition vermilion
(the stronger end darker), no opinion grey. Meetings flagged `excluded_no_item` (a keyword false hit) are left out, and
meetings where the public didn't speak are stated in the note, not drawn. It counts meetings, never speakers.

National, 2026-11-27: 112 meetings where the public spoke, in 22 states: 0 support, require everywhere; 22 support, each
community decides; 7 no opinion; 74 oppose, each community decides; 9 oppose, ban everywhere. In 204 more read meetings
the public didn't speak on it (another 210 readings are keyword false hits with no fluoridation item, left out).

## Local actions

Meetings whose AI reading of what the body did is `outcome_group` advanced, blocked or tabled_or_deferred. For water
fluoridation: voted to keep or start fluoridation (61), voted to end it (4), tabled, deferred or sent to voters (23), in
25 states, 2010–2026, as of 2026-11-27. The tracker shows the three totals (each a filter), a stacked column per year,
the states with most actions (national scope) and the meetings, newest first, each linked to its recording with how sure
the reading was. It is the action of a council, board or commission, never of a person.

## Related

- [Topic meeting lean](topic-meeting-lean.md) — how the meeting readings are made.
- [Story charts: timeline, dumbbell and unit matrix](story-charts-timeline-dumbbell.md) — the Meetings over time section,
  whose milestone track reads enacted bills from the same table (its vote lanes for non-data-center topics:
  [#1278](https://github.com/getcommunityone/open-navigator/issues/1278)).
