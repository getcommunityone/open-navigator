{{ config(materialized='table') }}

/*
    Mart: transitive closure of the tag hierarchy ("sub table").

    One row per (ancestor_tag_id, descendant_tag_id) pair, including the self
    pair at depth 0. Enables single-equality subtree queries against `tag`:

        -- all tags under the NTEE Health major group, inclusive
        select t.*
        from tag t
        join tag_closure c on c.descendant_tag_id = t.tag_id
        where c.ancestor_tag_id = 'ntee|E';

    PK (ancestor_tag_id, descendant_tag_id); both FK -> tag.tag_id.
*/

select
    ancestor_tag_id,
    descendant_tag_id,
    depth,
    dbt_loaded_at
from {{ ref('int_tags__closure') }}
