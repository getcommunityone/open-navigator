{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'civic', 'topic', 'money'],
        contract={'enforced': true}
    )
}}

/*
public.topic_money_and_talk — per (jurisdiction, canonical theme, month) rollup of
the "talk" (how often a topic is decided on) vs the "money" (net dollar impact of
those decisions) signals, for the topic money-vs-talk web feature.

GRAIN: one row per (jurisdiction_id, canonical_theme, month).
  month = date_trunc('month', occurred_at)::date.

SOURCE : public/gold item_interestingness (decision grain).
THEME  : the noisy free-text item_interestingness.primary_theme is collapsed to
         one of the 18 canonical COFOG buckets via the normalize_coarse_theme()
         macro (SQL port of llm.policy_questions.coarse_theme). Rows that resolve
         to '__unthemed__' are EXCLUDED. cofog_code is resolved by JOIN to the
         policy_theme_cofog seed (primary_theme -> cofog_code).
METRICS:
  decision_count = COUNT(*)                          -- the "talk"
  spend_amount   = SUM(ABS(net_dollar_impact))       -- the "money"
                   over rows with a non-null, non-zero impact (0 if none)
  spend_count    = count of decisions contributing money

Rows with a NULL jurisdiction_id are EXCLUDED (the FK to jurisdictions and the
surrogate PK both require a real jurisdiction).
TARGET : public.topic_money_and_talk (served via publish_public_serving).
*/

with decisions as (
    select
        jurisdiction_id,
        jurisdiction_name,
        state_code,
        city,
        date_trunc('month', occurred_at)::date              as month,
        {{ normalize_coarse_theme('primary_theme') }}       as canonical_theme,
        net_dollar_impact
    from {{ ref('item_interestingness') }}
    where jurisdiction_id is not null
),

themed as (
    select *
    from decisions
    where canonical_theme <> '__unthemed__'
),

agg as (
    -- GROUP BY only the PK-determining keys (jurisdiction_id, canonical_theme,
    -- month). The descriptive attributes (name/state/city) can vary within a
    -- jurisdiction_id (e.g. some rows carry a NULL city) so they are collapsed via
    -- max() rather than grouped on — grouping on them would split one logical key
    -- into duplicate surrogate-key rows.
    select
        jurisdiction_id,
        max(jurisdiction_name)                                                      as jurisdiction_name,
        max(state_code)                                                             as state_code,
        max(city)                                                                   as city,
        canonical_theme,
        month,
        count(*)                                                                    as decision_count,
        coalesce(
            sum(abs(net_dollar_impact)) filter (
                where net_dollar_impact is not null and net_dollar_impact <> 0
            ), 0
        )                                                                           as spend_amount,
        count(*) filter (
            where net_dollar_impact is not null and net_dollar_impact <> 0
        )                                                                           as spend_count
    from themed
    group by jurisdiction_id, canonical_theme, month
),

cofog as (
    select primary_theme, cofog_code
    from {{ ref('policy_theme_cofog') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['a.jurisdiction_id', 'a.canonical_theme', 'a.month']) }}::text
                                                    as topic_money_and_talk_id,
    a.jurisdiction_id::text                         as jurisdiction_id,
    a.jurisdiction_name::text                       as jurisdiction_name,
    a.state_code::text                              as state_code,
    a.city::text                                    as city,
    a.canonical_theme::text                         as canonical_theme,
    c.cofog_code::text                              as cofog_code,
    a.month::date                                   as month,
    a.decision_count::integer                       as decision_count,
    a.spend_amount::numeric                         as spend_amount,
    a.spend_count::integer                          as spend_count
from agg a
left join cofog c on c.primary_theme = a.canonical_theme
