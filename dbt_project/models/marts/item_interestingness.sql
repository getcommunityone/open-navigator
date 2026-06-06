{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'civic', 'interestingness'],
        contract={'enforced': true}
    )
}}

/*
public.item_interestingness — tunable, explainable interestingness score per
civic agenda item (= decision), powering the discovery feed and the per-lens
"story lens" views.

GRAIN: one row per event_decision_id (latest extraction).

  interestingness_score = 100 * time_decay * Σ_k ( weight_k * component_k ) / Σ_k weight_k
  time_decay            = pow(0.5, age_days / half_life_days)   -- past items only

Weights come from the interestingness_weights SEED (tunable without code, read
via the civic_component_weights() macro). half_life_days and the peer window are
dbt vars. The Σweight normalization guarantees score ∈ [0,100] for any weight
scaling. Every component is emitted alongside the composite so each lens can sort
by a single signal, plus top_signals (ordered component contributions) for the
"why this surfaced" badge.

MATERIALIZATION: full-refresh table (not incremental) — percentile components are
computed against a sliding peer window, so adding rows re-ranks existing ones; a
correct incremental would have to recompute the whole window anyway. The item
count (~2.6K) is small, so a table rebuild is cheap.

FORWARD ITEMS: scheduled_for has no source yet, so time_decay's "no decay for
forward items" branch is dormant and every row is treated as past.
*/

{% set half_life = var('civic_half_life_days', 90) %}

with sig as (
    select * from {{ ref('int_civic__item_signals') }}
),

norms as (
    select * from {{ ref('int_civic__item_signal_norms') }}
),

weights as (
    {{ civic_component_weights() }}
),

scored as (
    select
        s.event_decision_id,
        s.meeting_id,
        s.jurisdiction_id,
        s.jurisdiction_name,
        s.state_code,
        s.state,
        s.city,
        s.size_tier,
        s.occurred_at,
        s.scheduled_for,
        s.subject_id,
        s.subject_key,
        s.title,
        s.summary,
        s.primary_theme,
        s.cofog_code,
        s.outcome,

        -- components (each already [0,1])
        n.conflict,
        n.money,
        n.novelty,
        n.engagement,
        n.surprise,
        n.urgency,
        n.buried,

        -- supporting raw signals (for lens filters + UI)
        s.votes_yes,
        s.votes_no,
        s.total_votes,
        s.competing_views_count,
        s.has_competing_views,
        s.public_comment_speaker_count,
        s.net_dollar_impact,
        s.appearance_idx,
        s.is_reversal,
        s.is_revisit,
        s.primary_latitude,
        s.primary_longitude,

        -- time decay (past items): pow(0.5, age_days / half_life)
        case
            when s.scheduled_for is not null then 1.0
            else power(0.5, greatest(0, current_date - s.occurred_at)::numeric / {{ half_life }})
        end as time_decay,

        -- normalized weighted average of components (∈ [0,1])
        (
            w.w_conflict   * n.conflict
          + w.w_money      * n.money
          + w.w_novelty    * n.novelty
          + w.w_engagement * n.engagement
          + w.w_surprise   * n.surprise
          + w.w_urgency    * n.urgency
          + w.w_buried     * n.buried
        ) / w.w_total as weighted_component_avg,

        w.w_conflict, w.w_money, w.w_novelty, w.w_engagement,
        w.w_surprise, w.w_urgency, w.w_buried, w.w_total
    from sig s
    join norms n on n.event_decision_id = s.event_decision_id
    cross join weights w
),

with_top as (
    select
        sc.*,
        ts.top_signals
    from scored sc
    cross join lateral (
        select jsonb_agg(
                   jsonb_build_object('component', component, 'contribution', round(contribution::numeric, 4))
                   order by contribution desc
               ) filter (where contribution > 0) as top_signals
        from (
            values
                ('conflict',   sc.w_conflict   * sc.conflict   / sc.w_total),
                ('money',      sc.w_money      * sc.money      / sc.w_total),
                ('novelty',    sc.w_novelty    * sc.novelty    / sc.w_total),
                ('engagement', sc.w_engagement * sc.engagement / sc.w_total),
                ('surprise',   sc.w_surprise   * sc.surprise   / sc.w_total),
                ('urgency',    sc.w_urgency    * sc.urgency    / sc.w_total),
                ('buried',     sc.w_buried     * sc.buried     / sc.w_total)
        ) t(component, contribution)
    ) ts
)

select
    event_decision_id::text                             as event_decision_id,
    meeting_id::integer                                 as meeting_id,
    jurisdiction_id::text                               as jurisdiction_id,
    jurisdiction_name::text                             as jurisdiction_name,
    state_code::text                                    as state_code,
    state::text                                         as state,
    city::text                                          as city,
    size_tier::integer                                  as size_tier,
    occurred_at::date                                   as occurred_at,
    scheduled_for::date                                 as scheduled_for,
    subject_id::text                                    as subject_id,
    subject_key::text                                   as subject_key,
    title::text                                         as title,
    summary::text                                       as summary,
    primary_theme::text                                 as primary_theme,
    cofog_code::text                                    as cofog_code,
    outcome::text                                       as outcome,

    conflict::double precision                          as conflict,
    money::double precision                             as money,
    novelty::double precision                           as novelty,
    engagement::double precision                        as engagement,
    surprise::double precision                          as surprise,
    urgency::double precision                           as urgency,
    buried::double precision                            as buried,

    votes_yes::integer                                  as votes_yes,
    votes_no::integer                                   as votes_no,
    total_votes::integer                                as total_votes,
    competing_views_count::integer                      as competing_views_count,
    has_competing_views::boolean                        as has_competing_views,
    public_comment_speaker_count::integer               as public_comment_speaker_count,
    net_dollar_impact::numeric                          as net_dollar_impact,
    appearance_idx::integer                             as appearance_idx,
    is_reversal::boolean                                as is_reversal,
    is_revisit::boolean                                 as is_revisit,
    primary_latitude::double precision                  as primary_latitude,
    primary_longitude::double precision                 as primary_longitude,

    time_decay::double precision                        as time_decay,
    -- composite, guaranteed ∈ [0,100]
    (100.0 * time_decay * weighted_component_avg)::double precision as interestingness_score,
    coalesce(top_signals, '[]'::jsonb)::jsonb           as top_signals
from with_top
