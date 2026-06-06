{{
    config(
        materialized='table',
        unique_key='id'
    )
}}

/*
    Mart: Data.gov publishing organizations (public schema).

    One row per Data.gov (CKAN) publishing organization — federal agencies,
    sub-agencies, and the state/county/city governments that publish datasets on
    Data.gov. Named for the entity it represents (organizations_gov), parallel to
    `organizations_nonprofits`; no dim_/fact_ prefixes per project naming rules.

    Standalone gov-org reference. NOT folded into `mdm_organization` (that master
    is the nonprofit/social-org consolidation population) — see the model schema
    and the bridging recommendation in the task summary.

    PK: id (enforced via contract in _schema_organizations_gov.yml).
*/

with

stg as (
    select *
    from {{ ref('stg_data_gov__organizations') }}
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
        government_level,
        ckan_type,
        ckan_state,
        approval_status,
        is_organization,
        dataset_count,
        follower_count,
        source_created_at,
        source_ingested_at,
        current_timestamp as dbt_updated_at
    from stg
)

select * from final
