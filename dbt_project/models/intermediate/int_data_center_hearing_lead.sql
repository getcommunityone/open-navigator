{{ config(materialized='table', tags=['intermediate', 'data_centers']) }}

/*
    Every data center hearing lead, one row per meeting (#955, #956): the curated seed
    (seeds.data_center_hearing_lead, from the owner's research lists) plus the CC BY 4.0 tracker
    leads (stg_data_center_hearing_tracker_lead).
    Grain: one row per (state_code, place, meeting_date). When several leads name the same
    meeting, one is kept, in this order: a seed lead with an official URL, a tracker lead with an
    official URL, any other seed lead, any other tracker lead (Siting Radar before Data Center
    Fights, then lead_id). So a curated official lead is never replaced, and a tracker can still
    supply the official page a seed lead lacked.
    place = the name without its type word (Hazle Township -> hazle, Denton City -> denton),
    lower-cased, which is how data_center_hearing matches jurisdictions too.
    Read by fetch_hearing_sources (which official pages to fetch) and data_center_hearing.
*/

with seed as (
    select
        lead_id::text           as lead_id,
        meeting_date::date      as meeting_date,
        jurisdiction_name::text as jurisdiction_name,
        state_code::text        as state_code,
        body_name::text         as body_name,
        topic::text             as topic,
        source_kind::text       as source_kind,
        source_name::text       as source_name,
        nullif(source_url, '')::text as source_url,
        lead_from::text         as lead_from,
        null::text              as census_geoid,
        null::text              as attribution,
        0                       as origin_rank
    from {{ ref('data_center_hearing_lead') }}
),

tracker as (
    select
        lead_id,
        meeting_date,
        jurisdiction_name,
        state_code,
        body_name,
        topic,
        source_kind,
        source_name,
        source_url,
        tracker                 as lead_from,
        census_geoid,
        attribution,
        case tracker when 'sitingradar' then 1 else 2 end as origin_rank
    from {{ ref('stg_data_center_hearing_tracker_lead') }}
),

all_leads as (
    select * from seed
    union all
    select * from tracker
),

ranked as (
    select
        *,
        row_number() over (
            partition by
                state_code,
                lower(regexp_replace(btrim(jurisdiction_name), '\s+(city|town|village|township|charter township|county|borough|parish)$', '', 'i')),
                meeting_date
            order by
                (source_kind = 'official' and coalesce(source_url, '') <> '') desc,
                origin_rank,
                lead_id
        ) as pick
    from all_leads
)

select
    lead_id,
    meeting_date,
    jurisdiction_name,
    state_code,
    body_name,
    topic,
    source_kind,
    source_name,
    source_url,
    lead_from,
    census_geoid,
    attribution
from ranked
where pick = 1
