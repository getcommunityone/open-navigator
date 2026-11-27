{{ config(materialized='table', tags=['data_centers', 'meeting_comments', 'serving'],
          indexes=[{'columns': ['state_code, meeting_date']}]) }}

/*
    Public comments about a data center (#1233, epic #1232): the data-center view over
    meeting_comment. Grain: one row per comment. A comment counts when it is a public
    comment (its introduction doesn't say staff / applicant / consultant) and either
      own_words   its own words name the Data centers topic (curated_topics 100001:
                  data center, data centre, hyperscale, server farm); or
      same_block  it sits in the same comment period (block_index: comments < 3 minutes
                  apart) as at least two public comments that do, those make up at least a
                  third of the period, and it raises at least one data-center concern
                  (comment_concern_terms, topic data-centers). Speakers often say "this
                  project" without repeating "data center".
    concern_keys keep only the data-center concern list; reference_concern_count counts the
    categories on the reference list (in_reference_list, the categories the comparison uses).
    Known misses: comments without a self-introduction or chair call; meetings without timed
    captions; a period where the project is never called a data center.
*/

{%- set dc_topic_id = 100001 %}

with c as (
    select * from {{ ref('meeting_comment') }} where is_public_comment
),

blocks as (
    select
        video_id,
        block_index,
        count(*)                                                    as block_comments,
        count(*) filter (where {{ dc_topic_id }} = any(topic_ids))  as block_dc_comments
    from c
    group by video_id, block_index
),

dc_concerns as (
    select concern_key, in_reference_list
    from {{ ref('comment_concern_terms') }}
    where topic_query_id = 'data-centers'
),

scored as (
    select
        c.*,
        (select coalesce(array_agg(k order by k), '{}') from unnest(c.concern_keys) as k
          where k in (select concern_key from dc_concerns))                                   as dc_concern_keys,
        (select count(*) from unnest(c.concern_keys) as k
          where k in (select concern_key from dc_concerns where in_reference_list))           as reference_concern_count,
        case
            when {{ dc_topic_id }} = any(c.topic_ids) then 'own_words'
            when b.block_dc_comments >= 2 and b.block_dc_comments * 3 >= b.block_comments then 'same_block'
        end                                                                                   as match_basis
    from c
    inner join blocks as b on b.video_id = c.video_id and b.block_index = c.block_index
)

select
    meeting_comment_id::text                as data_center_comment_id,
    meeting_comment_id::text                as meeting_comment_id,
    video_id::text                          as video_id,
    meeting_date::date                      as meeting_date,
    jurisdiction_id::text                   as jurisdiction_id,
    jurisdiction_name::text                 as jurisdiction_name,
    state_code::text                        as state_code,
    state::text                             as state,
    start_seconds::numeric(12, 3)           as start_seconds,
    end_seconds::numeric(12, 3)             as end_seconds,
    word_count::int                         as word_count,
    speaker_display_name::text              as speaker_display_name,
    match_basis::text                       as match_basis,
    dc_concern_keys::text[]                 as concern_keys,
    cardinality(dc_concern_keys)::int       as concern_count,
    reference_concern_count::int            as reference_concern_count,
    company_keys::text[]                    as company_keys,
    person_keys::text[]                     as person_keys,
    mentions_ai::boolean                    as mentions_ai,
    role_keys::text[]                       as role_keys,
    possible_minor::boolean                 as possible_minor
from scored
where match_basis = 'own_words'
   or (match_basis = 'same_block' and cardinality(dc_concern_keys) > 0)
