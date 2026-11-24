---
title: Meeting and decision metrics for the Matrix map
sidebar_label: Meeting metrics for Matrix map
description: Which meaningful metrics to derive from meeting and decision data, how to model them, and which Matrix map layout each one fits.
---

# Meeting and decision metrics for the Matrix map

Status: **proposal** (not yet built). Context: the Data explorer **Matrix map** tab
(`web_app/src/pages/DataExplorerMatrixPage.tsx`) renders ACS state and county values in six layouts
(Tiles, Pivot, Compare, Scatter, Diverging, Share). The goal is to let the same layouts show our
meeting and decision data. Reference for the chart forms: <https://github.com/jcbowyer/vizjb12>.

## What we have to work with

| Source (public schema) | Grain | Useful for |
| --- | --- | --- |
| `event` | one row per meeting (state, city, jurisdiction, date, `duration_minutes`, `view_count`) | meeting volume, cadence, length |
| `event_documents` (transcripts) | one row per transcript | coverage, words, searchable evidence |
| `event_decision` (AI-extracted) | one row per decision: `primary_theme`, `outcome`, `vote_tally`, `competing_views`, place refs | what was decided and how |
| `item_interestingness` | one row per decision, typed signals: `votes_yes`, `votes_no`, `public_comment_speaker_count`, `net_dollar_impact`, `has_competing_views`, `is_reversal`, `is_revisit` | contested, money, engagement, reversals |
| `decision_speakers` | one row per decision, `speaker_count` | public participation |
| `topic_money_and_talk` | jurisdiction × theme × month: `decision_count`, `spend_amount` | talk vs money |
| `jurisdiction_minutes_publish_lag` | one row per jurisdiction: median, mean, p90 lag days | transparency |
| `data_center_*`, `decision_company_mention` | decision or meeting level | topical deep dives |

## The one rule that makes these metrics meaningful: show coverage

ACS covers every state and county. **Our meetings do not.** We only have transcripts and extractions
for jurisdictions we crawl, so a raw state count mostly measures crawl coverage, not civic activity.
Every metric below therefore ships with:

- `coverage_n`: how many jurisdictions and meetings contributed (always shown beside the value),
- a **minimum-sample rule** (for example fewer than 10 decisions): show `—`, never `0` or a noisy rate,
- `null` for "no data", `0` only for a measured zero (see "No Fabricated Data" in `CLAUDE.md`).

## Recommended metrics

### Additive (counts and sums): eligible for the Share layout

Part of whole works only here, because the parts sum to a meaningful whole.

| Slug | Definition | Whole for Share |
| --- | --- | --- |
| `meetings_total` | meetings in `event` | states of U.S., counties of a state |
| `meetings_with_transcript` | meetings with an `event_documents` transcript | same |
| `decisions_total` | rows in `event_decision` | same |
| `decisions_theme_<theme>` | decisions per `primary_theme` (one slug per canonical COFOG theme) | themes of a jurisdiction, or states of one theme |
| `decisions_money_flagged` | decisions with a dollar impact | same |
| `net_dollar_impact` | sum of `ABS(net_dollar_impact)` (same definition as `topic_money_and_talk.spend_amount`) | same |
| `public_comment_speakers` | sum of `decision_speakers.speaker_count` | same |
| `meeting_hours` | sum of `duration_minutes` / 60 | same |

Money is the dollar impact of money-flagged decisions, **not a budget**; keep the existing disclaimer.

### Rates and medians: Tiles, Pivot, Compare, Scatter, Diverging (never Share)

Store numerator and denominator next to the value so any roll-up recomputes rather than averages.

| Slug | Value | Notes |
| --- | --- | --- |
| `decisions_per_meeting` | decisions / meetings with extraction | depth of agendas |
| `contested_rate` | decisions with `has_competing_views` / decisions | how often views split |
| `split_vote_rate` | decisions with `votes_no > 0` / decisions with a tally | only where a tally exists |
| `public_comment_rate` | decisions with `speaker_count > 0` / decisions | participation |
| `money_flag_rate` | money-flagged decisions / decisions | |
| `reversal_rate` | `is_reversal` decisions / decisions | |
| `transcript_coverage` | meetings with transcript / meetings | doubles as the data-quality column |
| `median_minutes_lag_days` | median of jurisdiction medians, weighted by `sample_n` | transparency |
| `mean_interestingness` | mean of `interestingness_score` | optional, explain the score |

`outcome` values must be confirmed against the extraction vocabulary before a `pass_rate` is defined;
do not ship one on a guessed mapping.

### Joined with ACS: the most useful comparisons

Per-capita and context metrics divide a meeting metric by an ACS count at the same geography
(`total_population`, `housing_units`, `labor_force`):

- `decisions_per_100k`, `public_comment_speakers_per_100k`, `net_dollar_impact_per_capita`
- Scatter: `public_comment_rate` against poverty or education metrics, `decisions_per_100k` against population
- Diverging: each state's `contested_rate` against the median state

Per-capita values are only comparable among places with similar coverage. Gate them on `coverage_n`
and say so in the layout caption. Scatter shows association at state or county level, not individual behaviour.

## Which layout fits which metric

| Layout | Meeting-data use |
| --- | --- |
| Tiles | any metric by state; add coverage as the tile footnote |
| Pivot | states × several rates side by side (contested, comment, lag, coverage) |
| Compare (dumbbell) | one metric across two years or two periods |
| Scatter | meeting rate vs ACS context, with the r² readout |
| Diverging | state vs median for a rate |
| Share | additive metrics only: decisions by theme within a state, or a state's share of all decisions |

## How to build it (data layer first)

1. **Metric catalog:** a dbt seed or model `civic_metric` (one row per metric: `slug`, `label`, `format`,
   `kind` = `count | rate | median`, `is_additive`, `source_model`). Same shape as the ACS manifest's
   `metrics[]`, so the page needs no new concept.
2. **Values mart:** `civic_metric_value` in long form, one row per (`geo_level`, `geo_id`, `period`,
   `metric_slug`), with `value`, `numerator`, `denominator`, `coverage_n`. Declare the primary key and
   foreign keys with dbt constraints; keep both `state_code` and `state`; store a bare year as `integer`
   and serialize it as a string on the wire. Name by entity, no `dim_`/`fact_`.
3. **Serving:** an API route returning `{ metrics, values: { geo_id: { slug: value } } }` plus coverage,
   reading `public` only. Prefer the API to a static export because meeting data refreshes nightly.
4. **Page:** add a **Source** switch (`?source=acs|meetings`) to the Matrix map. The layouts already read
   `metrics` and `values`; only the fetch changes, and the layout caption states the active source and period.
5. **Counties:** add after states are proven, because place and county labels for decisions depend on the
   geocoding in `event_place_geocoded` and `decision_place_label`.

## Phasing

1. Catalog plus state-level mart with the eight additive and six rate metrics above (one period, latest).
2. Source switch on the Matrix map, with coverage shown on every tile and row.
3. Time: quarterly periods enable Compare and a trend column.
4. ACS-joined per-capita metrics.
5. County level.

## Open questions

- Which period grain first: calendar year or quarter?
- Minimum sample size before a rate is shown (suggest 10 decisions, 3 jurisdictions).
- Confirm the `outcome` vocabulary so a pass or fail rate can be defined.
- Should coverage-gated per-capita metrics be hidden by default or shown with a warning?
