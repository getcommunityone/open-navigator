{{ config(materialized='view') }}

/*
    Staging: GSA .gov domain registry.

    Reference example of the Stage 3 conventions (see dbt_project/CONVENTIONS.md):
      - Naming: stg_<source>__<entity>
      - Reads only from source(), never from another model
      - Pinned types via the contract in _schema_stg_gsa.yml
      - Four-CTE template: source → renamed → filtered → final
*/

with

source as (
    select *
    from {{ source('bronze', 'bronze_gov_domains') }}
),

renamed as (
    select
        domain_name                                                    as domain_name,
        nullif(trim(domain_type), '')                                  as domain_type,
        nullif(trim(agency), '')                                       as agency,
        nullif(trim(organization), '')                                 as organization,
        nullif(trim(city), '')                                         as city,
        upper(nullif(trim(state), ''))                                 as state_code,
        nullif(trim(security_contact), '')                             as security_contact,
        ingestion_date                                                 as source_ingested_at
    from source
),

filtered as (
    -- Business rule: drop rows with NULL domain_name (legacy data had a handful).
    select *
    from renamed
    where domain_name is not null
      and length(domain_name) > 0
),

final as (
    select
        domain_name,
        domain_type,
        agency,
        organization,
        city,
        state_code,
        security_contact,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from filtered
)

select * from final
