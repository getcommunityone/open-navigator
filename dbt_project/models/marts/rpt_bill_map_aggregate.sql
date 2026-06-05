{{
  config(
    materialized='table',
    indexes=[
      {'columns': ['jurisdiction_id'], 'type': 'btree'},
      {'columns': ['state_code'], 'type': 'btree'}
    ]
  )
}}

/*
    Reporting aggregate: public.rpt_bill_map_aggregate — pre-aggregated bill SUBJECTS
    (topics) by jurisdiction for fast map/geography "trending topics" queries.

    Grain: one row per (jurisdiction_id, state_code, subject). subject is exploded
    from the bills.subject jsonb array. Modeled on int_trending_causes_by_jurisdiction
    (ranking + sample-headlines idiom).

    Metrics:
      - bill_count: total bills mentioning the subject in the jurisdiction.
      - recent_bill_count: "trending" — bills whose latest_action_date is within the
        last 2 years.
      - most_recent_action_date: latest action across the subject's bills.
      - topic_rank: row_number within the jurisdiction by bill_count desc — the UI
        pulls "top N trending topics in this geography".
      - sample_bill_titles: up to 3 most-recent bill titles.

    PK surrogate bill_topic_id = md5(coalesce(jurisdiction_id,'') || '|' || subject).
    FK jurisdiction_id -> jurisdictions.jurisdiction_id (nullable). Indexed on
    jurisdiction_id and state_code.
*/

with

bills as (
    select
        bill_uid,
        jurisdiction_id,
        state_code,
        title,
        latest_action_date,
        subject
    from {{ ref('bills') }}
),

-- explode the subject jsonb array to one row per (bill, subject)
bill_subjects as (
    select
        b.bill_uid,
        b.jurisdiction_id,
        b.state_code,
        b.title,
        b.latest_action_date,
        nullif(btrim(subj.value #>> '{}'), '')             as subject
    from bills b,
        lateral jsonb_array_elements(
            case when jsonb_typeof(b.subject) = 'array' then b.subject else '[]'::jsonb end
        ) as subj(value)
),

filtered as (
    select * from bill_subjects where subject is not null
),

aggregated as (
    -- Grain is (jurisdiction_id, subject) to match the surrogate PK. state_code is
    -- functionally determined by jurisdiction_id (every bill maps to its state row),
    -- so max(state_code) is safe and keeps (jurisdiction_id, subject) the unique key.
    select
        jurisdiction_id,
        max(state_code)                                    as state_code,
        subject,
        count(distinct bill_uid)                           as bill_count,
        count(distinct bill_uid) filter (
            where latest_action_date >= (current_date - interval '2 years')
        )                                                  as recent_bill_count,
        max(latest_action_date)                            as most_recent_action_date,
        (array_agg(title order by latest_action_date desc nulls last))[1:3]
                                                           as sample_bill_titles
    from filtered
    group by jurisdiction_id, subject
),

ranked as (
    select
        *,
        row_number() over (
            partition by jurisdiction_id
            order by bill_count desc, most_recent_action_date desc nulls last, subject
        )                                                  as topic_rank
    from aggregated
)

select
    md5(coalesce(jurisdiction_id, '') || '|' || subject)   as bill_topic_id,
    jurisdiction_id,
    state_code,
    subject,
    bill_count,
    recent_bill_count,
    most_recent_action_date,
    topic_rank,
    sample_bill_titles,
    current_timestamp                                      as dbt_loaded_at
from ranked
