{{ config(materialized='table') }}

/*
    Mart: unified, hierarchical tag taxonomy (NTEE + EveryOrg).

    Replaces the ad-hoc public.cause_ntee. One row per tag node, keyed by the
    collision-safe synthetic tag_id (vocabulary || '|' || source_code). Hierarchy
    is adjacency (parent_tag_id, self-FK) plus the tag_closure sub-table for
    subtree queries. `depth` is the node's distance from its root, derived from
    the closure (max ancestor distance) so there is a single hierarchy walk.

    Serve cause/tag browse + filtering from here; roll entities up the tree by
    joining tag_organization -> tag_closure.
*/

with

tags as (
    select * from {{ ref('int_tags__unified') }}
),

-- Distance from root = the deepest ancestor chain ending at this node.
depth_from_root as (
    select
        descendant_tag_id   as tag_id,
        max(depth)          as depth
    from {{ ref('int_tags__closure') }}
    group by descendant_tag_id
)

select
    t.tag_id,
    t.vocabulary,
    t.source_code,
    t.label,
    t.description,
    t.parent_tag_id,
    coalesce(d.depth, 0)    as depth,
    t.breadcrumb,
    t.category,
    t.subcategory,
    t.icon,
    t.popularity_rank,
    t.source,
    t.source_ingested_at,
    t.dbt_loaded_at
from tags as t
left join depth_from_root as d
    on t.tag_id = d.tag_id
