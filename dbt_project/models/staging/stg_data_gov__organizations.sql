{{ config(materialized='view') }}

/*
    Staging: Data.gov (CKAN) publishing organizations.

    Source: bronze.bronze_organizations_gov — landed by
    packages/ingestion/src/ingestion/data_gov/organizations.py from the Data.gov
    CKAN `organization_list` / `organization_show` API. These are the entities
    that *publish* datasets on Data.gov: federal agencies, sub-agencies, and some
    state / county / city governments.

    Follows Stage 3 conventions (dbt_project/CONVENTIONS.md):
      - Naming: stg_<source>__<entity>
      - Reads only from source(), never from another model
      - Pinned types via the contract in _schema_stg_data_gov.yml
      - Four-CTE template: source -> renamed -> filtered -> final

    IMPORTANT disambiguations (see column comments):
      - CKAN `state` is the record *lifecycle* state ("active"/"deleted"), NOT a
        US state. Renamed to `ckan_state` to avoid collision with the project's
        US `state` / `state_code` convention.
      - CKAN `type` (`org_type` in bronze) is always the literal "organization"
        for these rows; kept as `ckan_type` for fidelity.
      - The meaningful government classification ("Federal Government",
        "County Government", "City Government", ...) lives in the CKAN `extras`
        array under key `organization_type`. Extracted here in dbt (not Python)
        into `government_level` per the data-pipeline rules.
*/

with

source as (
    select *
    from {{ source('bronze', 'bronze_organizations_gov') }}
),

renamed as (
    select
        -- Identity
        id                                                  as id,
        nullif(trim(name), '')                              as slug,
        coalesce(nullif(trim(title), ''),
                 nullif(trim(display_name), ''),
                 nullif(trim(name), ''))                    as title,
        nullif(trim(display_name), '')                      as display_name,
        nullif(trim(description), '')                       as description,

        -- Web / media
        nullif(trim(website_url), '')                       as website_url,
        nullif(trim(image_url), '')                         as image_url,
        nullif(trim(image_display_url), '')                 as image_display_url,

        -- CKAN classification / workflow (disambiguated)
        nullif(trim(org_type), '')                          as ckan_type,
        nullif(trim(state), '')                             as ckan_state,
        nullif(trim(approval_status), '')                   as approval_status,
        is_organization                                     as is_organization,

        -- Government level extracted from the CKAN `extras` array (dbt-side JSONB,
        -- not Python). extras is an array of {key,value} objects; pull the
        -- `organization_type` entry, e.g. "Federal Government" / "City Government".
        nullif(trim((
            select e->>'value'
            from jsonb_array_elements(
                case when jsonb_typeof(extras) = 'array' then extras else '[]'::jsonb end
            ) as e
            where e->>'key' = 'organization_type'
            limit 1
        )), '')                                             as government_level,

        -- Activity metrics
        coalesce(package_count, 0)                          as dataset_count,
        coalesce(num_followers, 0)                          as follower_count,

        -- Timestamps (real timestamp — keep as-is, do NOT treat as a year)
        created_at                                          as source_created_at,
        ingestion_date                                      as source_ingested_at
    from source
),

filtered as (
    -- Only surface live publishers; drop CKAN-deleted records.
    select *
    from renamed
    where id is not null
      and (ckan_state is null or ckan_state <> 'deleted')
),

final as (
    select
        id,
        slug,
        title,
        display_name,
        description,
        website_url,
        image_url,
        image_display_url,
        ckan_type,
        ckan_state,
        approval_status,
        is_organization,
        government_level,
        dataset_count,
        follower_count,
        source_created_at,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from filtered
)

select * from final
