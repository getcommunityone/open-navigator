{{ config(materialized='table') }}

/*
    Mart: bridge linking a golden organization to its NTEE tag.

    The nonprofit satellite (mdm_organization_nonprofit) carries a single full
    NTEE code per master_org_id. We attach each org to the most specific NTEE
    node in `tag` that is a prefix of its code, so the closure table rolls it up
    to every ancestor:

        exact        ntee_code == tag.source_code           (node exists at full depth)
        prefix       longest tag.source_code that prefixes ntee_code
        major_group  the prefix match is the 1-letter root (e.g. 'E')

    An org whose code shares no prefix with any node (taxonomy gap) gets no row —
    FK integrity to `tag` is preserved. NTEE-only by design (EveryOrg has no
    org/event linkage in the warehouse).

    PK (master_org_id, tag_id); FK master_org_id -> mdm_organization,
    tag_id -> tag.
*/

with

orgs as (
    select
        master_org_id,
        upper(nullif(trim(ntee_code), '')) as ntee_code
    from {{ ref('mdm_organization_nonprofit') }}
    where ntee_code is not null
),

ntee_nodes as (
    select
        tag_id,
        source_code,
        length(source_code) as code_len
    from {{ ref('tag') }}
    where vocabulary = 'ntee'
),

-- Every node whose source_code is a prefix of the org's full code.
candidate_matches as (
    select
        o.master_org_id,
        o.ntee_code,
        node.tag_id,
        node.source_code,
        node.code_len
    from orgs as o
    join ntee_nodes as node
        on o.ntee_code like node.source_code || '%'
),

-- Keep the most specific (longest) matching node per org.
ranked as (
    select
        *,
        row_number() over (
            partition by master_org_id
            order by code_len desc
        ) as match_rank
    from candidate_matches
),

final as (
    select
        master_org_id,
        tag_id,
        true                                as is_primary,
        case
            when source_code = ntee_code then 'exact'
            when code_len = 1            then 'major_group'
            else 'prefix'
        end                                 as match_method,
        current_timestamp                   as assigned_at
    from ranked
    where match_rank = 1
)

select * from final
