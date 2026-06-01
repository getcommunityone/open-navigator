{{ config(materialized='view') }}

/*
    Staging: CivicSearch meeting events — one row per vid_id.

    Reads the RAW landing table bronze.bronze_events_civicsearch, populated by
    the LAND loader ingestion.civicsearch.events (which lands search results
    VERBATIM — no derivation). This model cleans/types the meeting-level columns
    and adds two cheap derivations (num_snippets, num_topics). The snippet array
    is unnested separately in stg_civicsearch__snippet.

    vid_id is a YouTube video id and the bridge to bronze_event_youtube /
    int_events_union (video_id) — see int_events_civicsearch__localview_xref.

    Four-CTE template: source -> renamed -> derived -> final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_events_civicsearch') }}
),

renamed as (
    select
        nullif(trim(vid_id), '')                 as vid_id,
        nullif(trim(title), '')                  as title,
        meeting_date                             as meeting_date,
        nullif(trim(location), '')               as location,
        nullif(trim(location_query_id), '')      as location_query_id,
        distance                                 as distance,
        has_approximate_timings                  as has_approximate_timings,
        nullif(trim(youtube_url), '')            as youtube_url,
        nullif(trim(place_query_id), '')         as place_query_id,
        place_lat                                as place_lat,
        place_lon                                as place_lon,
        coalesce(matched_keywords, '[]'::jsonb)  as matched_keywords,
        coalesce(snippets, '[]'::jsonb)          as snippets,
        coalesce(topic_ids, '[]'::jsonb)         as topic_ids,
        scraped_at                               as scraped_at
    from source
    where vid_id is not null
      and length(trim(vid_id)) > 0
),

derived as (
    select
        *,
        jsonb_array_length(snippets)  as num_snippets,
        jsonb_array_length(topic_ids) as num_topics
    from renamed
),

final as (
    select
        vid_id,
        title,
        meeting_date,
        location,
        location_query_id,
        distance,
        has_approximate_timings,
        youtube_url,
        place_query_id,
        place_lat,
        place_lon,
        matched_keywords,
        snippets,
        topic_ids,
        num_snippets,
        num_topics,
        scraped_at,
        current_timestamp as dbt_loaded_at
    from derived
)

select * from final
