{{ config(materialized='table') }}

/*
    Intermediate: NTEE codes with their hierarchical cause_breadcrumb.

    Reproduces the Python build_breadcrumb() helper that ingestion.ntee.codes
    used to compute in-memory (walking parent_code up the chain and joining
    names root -> ... -> leaf with " > "). That derivation is business logic and
    belongs here, not in the loader — the loader now lands only the raw code
    rows. Moved to dbt per dbt_project/CONVENTIONS.md.

    Method (recursive CTE):
      - anchor:   root codes (parent_code is null) -> breadcrumb = own name
      - recurse:  each child appends " > <child name>" to its parent's path
    This walks DOWN from the root, accumulating the path so the root name is
    first and the leaf name is last — identical ordering to build_breadcrumb,
    where ancestors were path.insert(0, ...) and the code's own name appended.
    The original Python capped the walk at 5 levels; we cap recursion depth at 5
    likewise (NTEE's taxonomy is shallow) to guard against cyclic parent_code.
*/

with recursive

source as (
    select * from {{ ref('stg_ntee__code') }}
),

breadcrumb_walk as (
    -- Anchor: codes that start a chain — either a true root (parent_code null)
    -- or an orphan whose parent_code points at a code not present in the table.
    -- build_breadcrumb produces a path for orphans too (the parent walk simply
    -- finds nothing), so we seed them at the code's own name, coalescing to the
    -- code itself when the name is missing (the Python `code_lookup.get(code, code)`
    -- fallback).
    select
        s.code,
        s.parent_code,
        coalesce(s.name, s.code)    as cause_breadcrumb,
        1                           as depth
    from source as s
    where s.parent_code is null
       or not exists (
            select 1 from source as p where p.code = s.parent_code
       )

    union all

    -- Recurse: append this code's name to the parent's accumulated path.
    select
        child.code,
        child.parent_code,
        parent.cause_breadcrumb || ' > ' || coalesce(child.name, child.code)
                                    as cause_breadcrumb,
        parent.depth + 1            as depth
    from source as child
    join breadcrumb_walk as parent
        on child.parent_code = parent.code
    where parent.depth < 5
),

final as (
    select
        s.code,
        s.name,
        s.description,
        s.cause_type,
        s.parent_code,
        s.category,
        s.subcategory,
        s.code_source,
        w.cause_breadcrumb,
        s.source_ingested_at,
        current_timestamp as dbt_loaded_at
    from source as s
    left join breadcrumb_walk as w
        on s.code = w.code
)

select * from final
