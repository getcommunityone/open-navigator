{{ config(materialized='table', tags=['intermediate', 'data_centers']) }}

/*
    Every data center hearing lead (#955, #956): the curated seed
    (seeds.data_center_hearing_lead, from the owner's research lists) plus the CC BY 4.0 tracker
    leads (stg_data_center_hearing_tracker_lead).
    Grain: one row per lead. Several leads can name the same meeting; they share meeting_key,
    and ALL of them are kept here, so fetch_hearing_sources fetches every official page a lead
    cites (a seed URL blocked by robots.txt doesn't hide a tracker's readable agenda).
    data_center_hearing then keeps one row per meeting_key, preferring a verified one, then
    lead_rank.

    meeting_key = state | place | county-or-not | date. place is the name without its type word
    (Hazle Township -> hazle, Denton City -> denton), lower-cased, as data_center_hearing matches
    jurisdictions; a county (or parish) never shares a key with a same-named town (Washington
    County vs Washington Township). One meeting per place per day is assumed: a planning
    commission and a council meeting on the same day in one place are one key.
    lead_rank (1 = best): a seed lead with an official URL, a tracker lead with one, any other
    seed lead, any other tracker lead (Siting Radar before Data Center Fights), then lead_id.
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

keyed as (
    select
        *,
        state_code || '|'
            || lower(regexp_replace(btrim(jurisdiction_name), '\s+(city|town|village|township|charter township|county|borough|parish)$', '', 'i'))
            || '|' || case when jurisdiction_name ~* '\m(county|parish)$' then 'county' else 'local' end
            || '|' || meeting_date::text                        as meeting_key
    from all_leads
)

select
    lead_id,
    meeting_key,
    row_number() over (
        partition by meeting_key
        order by
            (source_kind = 'official' and coalesce(source_url, '') <> '') desc,
            origin_rank,
            lead_id
    )::int              as lead_rank,
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
from keyed
