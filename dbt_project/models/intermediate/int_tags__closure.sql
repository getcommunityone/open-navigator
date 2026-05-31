{{ config(materialized='table') }}

/*
    Intermediate: transitive-closure "sub table" for the tag hierarchy.

    Adjacency (parent_tag_id in int_tags__unified) answers "who is my direct
    parent". The closure answers "give me every tag at or under node X" with a
    single equality filter, e.g.:

        select descendant_tag_id from tag_closure where ancestor_tag_id = 'ntee|E'

    One row per (ancestor, descendant) pair, including the self-pair at depth 0
    (every node is its own ancestor) — the standard closure-table convention,
    so a subtree query naturally includes the root itself.

    Method (recursive CTE walking DOWN from each node):
      - anchor:  (tag, tag, 0) for every tag — self reference.
      - recurse: for each known (ancestor -> descendant) pair, attach the
                 descendant's children, depth + 1.
    Depth capped at 8 to guard against cyclic parent_tag_id (NTEE/EveryOrg are
    shallow; the NTEE breadcrumb walk upstream caps at 5).
*/

with recursive

tags as (
    select tag_id, parent_tag_id
    from {{ ref('int_tags__unified') }}
),

closure as (
    -- Anchor: each tag is its own ancestor at depth 0.
    select
        tag_id      as ancestor_tag_id,
        tag_id      as descendant_tag_id,
        0           as depth
    from tags

    union all

    -- Recurse: extend each ancestor path down to the next generation of
    -- children (child.parent_tag_id = current descendant).
    select
        c.ancestor_tag_id,
        child.tag_id        as descendant_tag_id,
        c.depth + 1         as depth
    from closure as c
    join tags as child
        on child.parent_tag_id = c.descendant_tag_id
    where c.depth < 8
)

select
    ancestor_tag_id,
    descendant_tag_id,
    depth,
    current_timestamp as dbt_loaded_at
from closure
