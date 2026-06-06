{{
    config(
        materialized='table',
        tags=['intermediate', 'civic', 'interestingness']
    )
}}

/*
int_civic__item_signals — RAW per-item metrics for the interestingness score.

GRAIN: one row per decision (= one civic "agenda item"), keyed on
event_decision_id. The anchor grain is public.event_decision (the multimodal AI
pipeline) — the only model carrying the place/financial/vote reference graph and
competing-views. A true per-agenda-item grain does not exist yet (the source
`agenda_items` array is unextracted), so "item" == decision here.

This model only ASSEMBLES and TYPES raw signals (votes, money, competing views,
public comment, recency, cross-session occurrence). Normalization to [0,1]
components happens downstream in int_civic__item_signal_norms.

Nulls are handled explicitly per signal. Signals with no source in the data are
emitted as documented stubs (never invented):
  * scheduled_for          — no upcoming-agenda source exists -> always NULL
  * votes_abstain          — vote_tally only ever carries yes/no -> always NULL
  * is_new_or_increased_fee_tax, is_consent_agenda, debate_duration_sec
                           — no source -> NULL/false (gated downstream by vars)
*/

with decisions as (
    -- collapse the append-partitioned source to the latest row per decision
    select *
    from (
        select
            event_decision_id,
            decision_id,
            analysis_id,
            jurisdiction_name,
            state_code,
            city,
            subject_id,
            headline,
            decision_statement,
            primary_theme,
            outcome,
            vote_tally,
            competing_views,
            financial_item_refs,
            source_ai_model,
            extracted_at,
            row_number() over (
                partition by event_decision_id order by extracted_at desc
            ) as _rn
        from {{ ref('event_decision') }}
    ) d
    where _rn = 1
),

meetings as (
    select
        event_meeting_id,
        meeting_date,
        event_date,
        body_name
    from {{ ref('event_meeting') }}
),

-- resolve jurisdiction_id + population for the size tier (name + state match)
jurisdictions as (
    select
        state_code,
        {{ normalize_jurisdiction_label_for_match('name') }} as juris_key,
        max(jurisdiction_id) as jurisdiction_id,
        max(population)      as population,
        max(latitude)        as juris_latitude,
        max(longitude)       as juris_longitude
    from {{ ref('jurisdictions') }}
    group by 1, 2
),

theme_cofog as (
    select primary_theme, cofog_code
    from {{ ref('policy_theme_cofog') }}
),

-- per-meeting public-comment aggregate (near-empty today; see bronze model note)
public_comment as (
    select
        source_event_id as analysis_id,
        count(distinct speaker_id) as public_comment_speaker_count,
        sum(
            case
                when timestamp_end_seconds is not null and timestamp_start_seconds is not null
                     and timestamp_end_seconds >= timestamp_start_seconds
                then timestamp_end_seconds - timestamp_start_seconds
            end
        )::numeric as public_comment_duration_sec
    from {{ ref('bronze_public_participation_from_ai') }}
    group by 1
),

-- money referenced by each decision: sum |amount| over its financial_item_refs,
-- resolved within the same analysis_id.
decision_money as (
    select
        d.event_decision_id,
        sum(abs(f.amount)) as net_dollar_impact,
        count(f.amount)    as financial_item_count
    from decisions d
    cross join lateral (
        select jsonb_array_elements_text(
            case when jsonb_typeof(d.financial_item_refs) = 'array'
                 then d.financial_item_refs else '[]'::jsonb end
        ) as fin_ref
    ) refs
    join {{ ref('event_financial_item') }} f
      on f.analysis_id = d.analysis_id
     and f.financial_item_id = refs.fin_ref
     and f.amount is not null
    group by 1
),

-- primary geocoded point for the decision (proximity is exposed, NOT scored here)
decision_point as (
    select
        edp.event_decision_id,
        max(g.latitude)  as primary_latitude,
        max(g.longitude) as primary_longitude
    from {{ ref('event_decision_place') }} edp
    join {{ ref('event_place_geocoded') }} g
      on g.place_id = edp.place_id
    where edp.is_primary
      and g.latitude is not null
      and g.longitude is not null
    group by 1
),

assembled as (
    select
        d.event_decision_id,
        d.decision_id,
        d.analysis_id                                   as meeting_id,
        j.jurisdiction_id,
        d.jurisdiction_name,
        d.state_code,
        {{ state_code_to_name('d.state_code') }}        as state,
        d.city,
        j.population,

        -- recency / forward window
        coalesce(
            case when m.meeting_date ~ '^\d{4}-\d{2}-\d{2}$' then m.meeting_date::date end,
            case when m.event_date   ~ '^\d{4}-\d{2}-\d{2}$' then m.event_date::date end,
            d.extracted_at::date
        )                                               as occurred_at,
        cast(null as date)                              as scheduled_for,

        -- identity / cross-session linking (subject_id is per-analysis; fall back
        -- to a normalized headline. Best-effort key, documented as such.)
        d.subject_id,
        coalesce(
            {{ normalize_jurisdiction_label_for_match('d.subject_id') }},
            nullif(regexp_replace(lower(trim(coalesce(d.headline, ''))), '[^a-z0-9]+', ' ', 'g'), '')
        )                                               as subject_key,
        d.headline                                      as title,
        d.decision_statement                            as summary,
        d.primary_theme,
        tc.cofog_code,
        d.outcome,
        {{ civic_outcome_polarity('d.outcome') }}       as outcome_polarity,

        -- votes (abstain never present in source)
        case when (d.vote_tally->>'yes') ~ '^-?[0-9]+$' then (d.vote_tally->>'yes')::int end as votes_yes,
        case when (d.vote_tally->>'no')  ~ '^-?[0-9]+$' then (d.vote_tally->>'no')::int  end as votes_no,
        cast(null as int)                               as votes_abstain,

        -- competing views (guard non-array json)
        (case when jsonb_typeof(d.competing_views->'counter_views') = 'array'
              then jsonb_array_length(d.competing_views->'counter_views') else 0 end)
        + (case when jsonb_typeof(d.competing_views->'additional_views') = 'array'
              then jsonb_array_length(d.competing_views->'additional_views') else 0 end)
                                                        as competing_views_count,

        -- public comment (0 when meeting has no extracted participation)
        coalesce(pc.public_comment_speaker_count, 0)    as public_comment_speaker_count,
        pc.public_comment_duration_sec,

        -- money
        coalesce(dm.net_dollar_impact, 0)               as net_dollar_impact,
        coalesce(dm.financial_item_count, 0)            as financial_item_count,

        -- MISSING-source stubs (gated downstream by feature-flag vars)
        cast(null as boolean)                           as is_new_or_increased_fee_tax,
        cast(null as boolean)                           as is_consent_agenda,
        cast(null as numeric)                           as debate_duration_sec,

        -- geocoded point (exposed for downstream proximity only)
        dp.primary_latitude,
        dp.primary_longitude,

        d.source_ai_model,
        d.extracted_at
    from decisions d
    left join meetings       m  on m.event_meeting_id = d.analysis_id
    left join jurisdictions  j  on j.state_code = d.state_code
                               and j.juris_key  = {{ normalize_jurisdiction_label_for_match('d.jurisdiction_name') }}
    left join theme_cofog    tc on tc.primary_theme = d.primary_theme
    left join public_comment pc on pc.analysis_id = d.analysis_id
    left join decision_money dm on dm.event_decision_id = d.event_decision_id
    left join decision_point dp on dp.event_decision_id = d.event_decision_id
),

-- cross-session occurrence ordering for novelty + surprise (reversal)
sequenced as (
    select
        *,
        row_number() over (
            partition by state_code, subject_key
            order by occurred_at, event_decision_id
        )                                               as appearance_idx,
        lag(outcome_polarity) over (
            partition by state_code, subject_key
            order by occurred_at, event_decision_id
        )                                               as prev_outcome_polarity
    from assembled
)

select
    event_decision_id,
    decision_id,
    meeting_id,
    jurisdiction_id,
    jurisdiction_name,
    state_code,
    state,
    city,
    population,
    -- size tier: NULL population -> tier 0 (peers itself); else quartile of population
    case
        when population is null then 0
        else ntile(4) over (
            partition by (population is null) order by population
        )
    end                                                 as size_tier,
    occurred_at,
    scheduled_for,
    subject_id,
    subject_key,
    title,
    summary,
    primary_theme,
    cofog_code,
    outcome,
    outcome_polarity,
    votes_yes,
    votes_no,
    votes_abstain,
    coalesce(votes_yes, 0) + coalesce(votes_no, 0) + coalesce(votes_abstain, 0) as total_votes,
    competing_views_count,
    (competing_views_count > 0)                         as has_competing_views,
    public_comment_speaker_count,
    public_comment_duration_sec,
    net_dollar_impact,
    financial_item_count,
    ln(1 + net_dollar_impact)                           as money_metric,
    is_new_or_increased_fee_tax,
    is_consent_agenda,
    debate_duration_sec,
    primary_latitude,
    primary_longitude,
    appearance_idx,
    -- reversal: outcome polarity flipped sign vs the prior session on this subject
    (appearance_idx > 1
        and prev_outcome_polarity is not null
        and outcome_polarity <> 0
        and prev_outcome_polarity <> 0
        and sign(outcome_polarity) <> sign(prev_outcome_polarity)) as is_reversal,
    (appearance_idx > 1)                                as is_revisit,
    source_ai_model,
    extracted_at
from sequenced
