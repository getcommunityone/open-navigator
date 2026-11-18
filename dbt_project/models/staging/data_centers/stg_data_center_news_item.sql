{{ config(materialized='view', tags=['staging', 'data_centers']) }}

/*
    News and company-announcement items about data centers (#532), from
    bronze_data_center_news_item (python -m ingestion.data_centers.community_events).
    Grain: one row per item (news_item_id = md5(source | url)).

    body is the title and the verbatim snippet, the only text the item carries. kinds are
    the meeting words it names (town hall, community meeting, open house, information
    session, public meeting); says_data_center whether it says "data center". When the
    bronze table hasn't been created yet the view is empty, so dbt still builds.
*/

{%- set src = source('bronze', 'bronze_data_center_news_item') -%}
{%- set src_exists = execute and adapter.get_relation(
        database=src.database, schema=src.schema, identifier=src.identifier) is not none %}

{%- if src_exists %}
with items as (
    select * from {{ src }}
)

select
    news_item_id::text                                         as news_item_id,
    source::text                                               as source,
    url::text                                                  as url,
    btrim(title)::text                                         as title,
    nullif(btrim(publisher), '')::text                         as publisher,
    published_at::timestamptz                                  as published_at,
    (published_at at time zone 'UTC')::date                    as published_on,
    nullif(btrim(snippet), '')::text                           as snippet,
    nullif(btrim(company_key), '')::text                       as company_key,
    (btrim(title) || case when nullif(btrim(snippet), '') is not null and btrim(snippet) <> btrim(title)
                          then ' — ' || btrim(snippet) else '' end)::text as body,
    array(
        select distinct case lower(m[1])
            when 'town hall' then 'town_hall'
            when 'community meeting' then 'community_meeting'
            when 'open house' then 'open_house'
            when 'information session' then 'information_session'
            when 'public meeting' then 'public_meeting'
        end
        from regexp_matches(title || ' ' || coalesce(snippet, ''),
            '\m(town hall|community meeting|open house|information session|public meeting)s?\M', 'gi') as m
        order by 1
    )::text[]                                                  as kinds,
    ((title || ' ' || coalesce(snippet, '')) ~* '{{ data_center_regex() }}')::boolean as says_data_center,
    first_seen_at::timestamptz                                 as first_seen_at
from items
{%- else %}
select
    null::text as news_item_id, null::text as source, null::text as url, null::text as title,
    null::text as publisher, null::timestamptz as published_at, null::date as published_on,
    null::text as snippet, null::text as company_key, null::text as body, null::text[] as kinds,
    null::boolean as says_data_center, null::timestamptz as first_seen_at
where false
{%- endif %}
