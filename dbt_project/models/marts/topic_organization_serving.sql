{{
  config(
    materialized='table',
    tags=['marts', 'topic', 'organization', 'serving'],
    indexes=[
      {'columns': ['topic_slug', 'state_code', 'evidence_rank'], 'type': 'btree'}
    ]
  )
}}

/*
    Serving slice of topic_organization (#1382): what the Nonprofits screen and GET /api/topics/{topic}/organizations
    read, small enough for Neon. Grain: one row per (topic_id, master_org_id).

    Kept: the 20 strongest per topic × state (evidence_rank, then revenue, then name) plus every named_in_meeting row.
    Columns: only those the API returns; match_text cut to 280 characters and mission to 100 (the screen shows one line).
    The full mart stays in gold (topic_organization); totals per method come from topic_organization_count.

    PK  topic_organization_id. FK  topic_id -> civicsearch_topic; master_org_id -> mdm_organization.
*/

{%- set per_state = 20 -%}

with ranked as (
    select
        o.*,
        row_number() over (
            partition by o.topic_id, o.state_code
            order by o.evidence_rank, o.revenue desc nulls last, o.org_name, o.master_org_id
        ) as rn
    from {{ ref('topic_organization') }} as o
),

cut as (
    select
        r.*,
        greatest(1, strpos(r.match_text, '<mark>') - 100)            as cut_from
    from ranked as r
),

windowed as (
    select
        c.*,
        regexp_replace(
            -- The last, cut-off word goes only when the window stops before the end.
            case when c.cut_from + 279 < length(c.match_text)
                 then regexp_replace(substr(c.match_text, c.cut_from, 280), '\s+\S*$', '')
                 else substr(c.match_text, c.cut_from) end,
            case when c.cut_from > 1 then '^\S*\s+' else '^$' end, '')  as cut_text
    from cut as c
)

select
    topic_organization_id::text                                       as topic_organization_id,
    topic_id::integer                                                 as topic_id,
    topic_slug::text                                                  as topic_slug,
    master_org_id::text                                               as master_org_id,
    org_name::text                                                    as org_name,
    city::text                                                        as city,
    state_code::text                                                  as state_code,
    match_method::text                                                as match_method,
    evidence_rank::integer                                            as evidence_rank,
    -- Up to 280 characters starting a little before the first <mark> (so the highlight is always in it), cut at
    -- words; an opened <mark> left open by the cut is closed.
    (case when length(match_text) <= 280 then match_text
          else (case when cut_from > 1 then '…' else '' end) || cut_text ||
               (case when (length(cut_text) - length(replace(cut_text, '<mark>', ''))) / 6
                        > (length(cut_text) - length(replace(cut_text, '</mark>', ''))) / 7
                     then '</mark>' else '' end) ||
               (case when cut_from + 279 < length(match_text) then '…' else '' end)
     end)::text                                                       as match_text,
    match_source_url::text                                            as match_source_url,
    match_date::date                                                  as match_date,
    match_place::text                                                 as match_place,
    (case when length(mission) <= 100 then mission
          else regexp_replace(left(mission, 100), '\s+\S*$', '') || '…' end)::text as mission,
    side::text                                                        as side,
    revenue::bigint                                                   as revenue,
    revenue_tax_year::integer                                         as revenue_tax_year,
    website_url::text                                                 as website_url,
    built_at::timestamptz                                             as built_at
from windowed
where rn <= {{ per_state }} or match_method = 'named_in_meeting'
