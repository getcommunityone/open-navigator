{{ config(materialized='table') }}

/*
    Intermediate: unified tag taxonomy node set (NTEE + EveryOrg).

    Folds the two curated cause vocabularies into one node table so they can be
    exposed downstream as the public `tag` taxonomy (replacing the ad-hoc
    public.cause_ntee). Each branch is normalized to a common shape; the
    hierarchy edge (parent_tag_id) and per-vocabulary extras are preserved.

    Collision-safe synthetic key:
        tag_id        = vocabulary || '|' || source_code   (e.g. 'ntee|E20')
        parent_tag_id = vocabulary || '|' || <parent code>  (null at roots)
    This mirrors the '<source>|<id>' dedupe-key convention used elsewhere
    (e.g. youtube|<video_id> bridges) and prevents NTEE codes from colliding
    with EveryOrg slugs in a shared namespace.

    The NTEE hierarchy/breadcrumb is already derived in int_ntee__breadcrumb
    (recursive parent_code walk) and EveryOrg adjacency lands in
    stg_everyorg__cause — we reuse both rather than re-walking here. `depth` is
    computed downstream from int_tags__closure to keep one source of truth for
    the hierarchy walk.
*/

with

ntee as (
    select * from {{ ref('int_ntee__breadcrumb') }}
),

everyorg as (
    select * from {{ ref('stg_everyorg__cause') }}
),

ntee_tags as (
    select
        'ntee|' || code                                 as tag_id,
        'ntee'                                          as vocabulary,
        code                                            as source_code,
        name                                            as label,
        description,
        case
            when parent_code is not null then 'ntee|' || parent_code
        end                                             as parent_tag_id,
        cause_breadcrumb                                as breadcrumb,
        category,
        subcategory,
        cast(null as text)                              as icon,
        cast(null as integer)                           as popularity_rank,
        'irs'                                           as source,
        cast(source_ingested_at as timestamptz)         as source_ingested_at
    from ntee
),

everyorg_tags as (
    select
        'everyorg|' || cause_id                         as tag_id,
        'everyorg'                                      as vocabulary,
        cause_id                                        as source_code,
        cause_name                                      as label,
        description,
        case
            when parent_id is not null then 'everyorg|' || parent_id
        end                                             as parent_tag_id,
        -- EveryOrg has no precomputed breadcrumb; fall back to the label.
        cause_name                                      as breadcrumb,
        category,
        cast(null as text)                              as subcategory,
        icon,
        cast(popularity_rank as integer)                as popularity_rank,
        'everyorg'                                      as source,
        cast(source_ingested_at as timestamptz)         as source_ingested_at
    from everyorg
),

unioned as (
    select * from ntee_tags
    union all
    select * from everyorg_tags
),

final as (
    select
        tag_id,
        vocabulary,
        source_code,
        label,
        description,
        parent_tag_id,
        breadcrumb,
        category,
        subcategory,
        icon,
        popularity_rank,
        source,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from unioned
)

select * from final
