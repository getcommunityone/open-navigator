{{
  config(
    materialized='incremental',
    incremental_strategy='append',
    full_refresh=false,
    on_schema_change='ignore',
    tags=['marts', 'event-extraction', 'ai']
  )
}}

/*
public.event_organization — organizations the AI extracted across analyzed events.

GRAIN (different from the other event_* marts): one row per org, keyed on
org_name_normalized_state_code — an AGGREGATED, near-canonical org record, NOT a
per-event mention. It therefore resolves FIRST and LAST seen events
(first/last_seen_event_id are analysis ids -> c1_event) instead of a single
c1_event_id, and uses the org's OWN state_code for geography.

SOURCE : bronze.bronze_organizations_from_ai
TARGET : public.event_organization (range-partitioned by extracted_at; bootstrap_event_organization; APPEND only).
*/

with src as (
    select *
    from {{ ref('bronze_organizations_from_ai') }}
    {% if is_incremental() %}
    where extracted_at > (select coalesce(max(extracted_at), '1900-01-01'::timestamp) from {{ this }})
    {% endif %}
),

analysis as (
    select id as analysis_id, event_id as legacy_event_id
    from {{ source('bronze', 'bronze_events_analysis_ai') }}
),

events as (
    select legacy_id, id as c1_event_id
    from {{ source('civic_core', 'c1_event') }}
)

select
    md5(s.org_name_normalized_state_code)       as id,
    s.org_name_normalized_state_code            as extraction_key,

    s.org_id,
    s.org_name,
    s.org_name_normalized,
    s.state_code,
    {{ state_code_to_name('s.state_code') }}    as state,
    s.org_type,
    s.org_subtype,
    s.is_lobbyist_entity,
    s.lobbying_clients,
    s.party_affiliation,
    s.ein,
    s.wikidata_qid,
    s.ntee_major_group,
    s.ntee_category_label,
    s.ntee_code,
    s.role_in_meeting,
    s.financial_interest,

    -- first/last seen event resolution (aggregated grain)
    s.first_seen_event_id                       as first_seen_analysis_id,
    s.last_seen_event_id                        as last_seen_analysis_id,
    fe.c1_event_id                              as first_c1_event_id,
    le.c1_event_id                              as last_c1_event_id,

    s.source_ai_model,
    s.extracted_at

from src s
left join analysis fa on fa.analysis_id = s.first_seen_event_id
left join events   fe on fe.legacy_id   = fa.legacy_event_id
left join analysis la on la.analysis_id = s.last_seen_event_id
left join events   le on le.legacy_id   = la.legacy_event_id
