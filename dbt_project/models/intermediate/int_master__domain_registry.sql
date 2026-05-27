{{ config(materialized='table') }}

/*
    Intermediate: domain_registry (MDM).

    Reproduces populate_domain_registry() from
    scripts/datasources/master_data/create_jurisdiction_master.py: extract a
    normalized domain from every source's website URL, union the three sources,
    and keep ONE row per domain.

    Original dedup behavior: the Python loaded org_location first, then wikidata,
    then jurisdiction, each with `ON CONFLICT (domain) DO NOTHING`. So for a
    domain seen in more than one source, the FIRST insert wins — i.e. precedence
    is organization_location > jurisdictions_wikidata > jurisdiction. We
    reproduce that exact precedence with a source_rank + row_number().
*/

with

org_domains as (
    select
        domain,
        'organization_location'         as source_table,
        org_location_id                 as source_id,
        website                         as source_url,
        org_name                        as jurisdiction_name,
        state_code,
        city,
        organization_type,
        1                               as source_rank
    from {{ ref('stg_mdm__organization_location') }}
    where domain is not null
),

wikidata_domains as (
    select
        domain,
        'jurisdictions_wikidata'        as source_table,
        wikidata_id                     as source_id,
        official_website                as source_url,
        jurisdiction_name,
        state_code,
        null::varchar                   as city,
        jurisdiction_type               as organization_type,
        2                               as source_rank
    from {{ ref('stg_mdm__jurisdictions_wikidata') }}
    where domain is not null
),

jurisdiction_domains as (
    select
        domain,
        'jurisdiction'                  as source_table,
        jurisdiction_id                 as source_id,
        website_url                     as source_url,
        jurisdiction_name,
        state_code,
        null::varchar                   as city,
        jurisdiction_type               as organization_type,
        3                               as source_rank
    from {{ ref('stg_mdm__jurisdiction') }}
    where domain is not null
),

unioned as (
    select * from org_domains
    union all
    select * from wikidata_domains
    union all
    select * from jurisdiction_domains
),

deduped as (
    -- ON CONFLICT (domain) DO NOTHING => first-loaded wins. Lowest source_rank
    -- (org_location) wins; tie-break on source_id for determinism.
    select
        *,
        row_number() over (
            partition by domain
            order by source_rank, source_id
        ) as rn
    from unioned
),

final as (
    select
        domain,
        source_table,
        source_id,
        source_url,
        jurisdiction_name,
        state_code,
        city,
        organization_type,
        1.0::decimal(3, 2)              as confidence_score,
        current_timestamp               as dbt_loaded_at
    from deduped
    where rn = 1
)

select * from final
