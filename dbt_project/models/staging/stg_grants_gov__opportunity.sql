{{ config(materialized='view') }}

/*
    Staging: Grants.gov federal grant opportunities.

    Source: bronze.bronze_grants_gov_opportunity — landed by
    ingestion.grants_gov.bronze from the Grants.gov Search2 API. One row per
    opportunity (PROSPECTIVE federal funding open / forecasted for application).

    DISTINCT ENTITY: these are opportunities to apply for ("what's open now"),
    NOT the historical IRS 990 Schedule I grants in the `grant` mart
    ("who got funded"). The two must not be conflated downstream.

    Follows Stage 3 conventions (dbt_project/CONVENTIONS.md):
      - Naming: stg_<source>__<entity>
      - Reads only from source(), never from another model
      - Pinned types via the contract in _schema_stg_grants_gov.yml
      - Four-CTE template: source -> renamed -> filtered -> final

    Notes:
      - `opportunity_id` is the natural/primary key (Grants.gov opportunity id).
      - `open_date` / `close_date` are real DATE columns (the loader parses the
        source MM/DD/YYYY strings), so the calendar-year wire/string rule does
        not apply — they serialize as ISO dates.
      - `aln` is the first Assistance Listing Number (formerly CFDA); the full
        list lives in `raw` for fidelity.
      - `raw` keeps the full Search2 oppHits record as JSONB.
*/

with

source as (
    select *
    from {{ source('bronze', 'bronze_grants_gov_opportunity') }}
),

renamed as (
    select
        -- Identity
        nullif(trim(opportunity_id), '')         as opportunity_id,
        nullif(trim(opportunity_number), '')     as opportunity_number,
        nullif(trim(title), '')                  as title,

        -- Agency
        nullif(trim(agency_code), '')            as agency_code,
        nullif(trim(agency_name), '')            as agency_name,

        -- Lifecycle
        open_date                                as open_date,
        close_date                               as close_date,
        lower(nullif(trim(opp_status), ''))      as opp_status,
        nullif(trim(doc_type), '')               as doc_type,

        -- Classification
        nullif(trim(aln), '')                    as aln,

        -- Provenance
        data_source                              as data_source,
        raw                                      as raw,
        ingestion_date                           as source_ingested_at
    from source
),

filtered as (
    select *
    from renamed
    where opportunity_id is not null
),

final as (
    select
        opportunity_id,
        opportunity_number,
        title,
        agency_code,
        agency_name,
        open_date,
        close_date,
        opp_status,
        doc_type,
        aln,
        -- Derived: is the opportunity still open for application as of today?
        (close_date is null or close_date >= current_date) as is_open,
        data_source,
        raw,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from filtered
)

select * from final
