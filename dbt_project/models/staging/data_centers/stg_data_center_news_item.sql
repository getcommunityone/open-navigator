{{ config(materialized='view', tags=['staging', 'data_centers']) }}

/*
    News and company-announcement items about data centers (#532), from
    bronze_data_center_news_item (python -m ingestion.data_centers.community_events).
    Grain: one row per item (news_item_id = md5(source | url)).

    body is the title and the verbatim snippet, the only text the item carries. kinds are
    the meeting words it names (town hall or "townhall", community meeting, open house,
    information session, public meeting; for a YouTube video, in its title only); says_data_center whether it says "data center". When the
    bronze table hasn't been created yet the view is empty, so dbt still builds.

    source_role (#549): 'article' for news, press releases and web pages; for a YouTube
    video (source youtube_search) 'news_coverage' when its channel is a TV or radio news
    outlet (a call sign such as WBRC, a network name, or "News" in the channel name) and
    'recording' otherwise, so local TV coverage is never taken for the meeting itself.
*/

{%- set news_channel_rx = "(\\m[KW][A-Z]{2,3}(-?(TV|DT|FM|AM))?\\M|\\mABC|\\mNBC|\\mCBS|\\mFOX|\\mCW\\M|\\mPBS\\M|\\mNPR\\M|Telemundo|Univision|Spectrum News|\\m[0-9]{1,2}/[0-9]{2}\\M)" %}
{%- set news_word_rx = "\\m(news|newschannel|newsnow)\\M" %}

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
        select distinct case regexp_replace(lower(m[1]), '^townhall$', 'town hall')
            when 'town hall' then 'town_hall'
            when 'community meeting' then 'community_meeting'
            when 'open house' then 'open_house'
            when 'information session' then 'information_session'
            when 'public meeting' then 'public_meeting'
        end
        -- a video's meeting word must be in its title: a description may only mention
        -- "town halls" in passing (a news roundup), the title says what the video is
        from regexp_matches(case when source = 'youtube_search' then title
                                 else title || ' ' || coalesce(snippet, '') end,
            '\m(town ?hall|community meeting|open house|information session|public meeting)s?\M', 'gi') as m
        order by 1
    )::text[]                                                  as kinds,
    ((title || ' ' || coalesce(snippet, '')) ~* '{{ data_center_regex() }}')::boolean as says_data_center,
    (case
        when source <> 'youtube_search' then 'article'
        when coalesce(publisher, '') ~ '{{ news_channel_rx }}'
          or coalesce(publisher, '') ~* '{{ news_word_rx }}' then 'news_coverage'
        else 'recording'
    end)::text                                                 as source_role,
    first_seen_at::timestamptz                                 as first_seen_at
from items
{%- else %}
select
    null::text as news_item_id, null::text as source, null::text as url, null::text as title,
    null::text as publisher, null::timestamptz as published_at, null::date as published_on,
    null::text as snippet, null::text as company_key, null::text as body, null::text[] as kinds,
    null::boolean as says_data_center, null::text as source_role, null::timestamptz as first_seen_at
where false
{%- endif %}
