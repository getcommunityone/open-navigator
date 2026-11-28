{{ config(materialized='view') }}

/*
    Staging: USAspending assistance awards to local governments (#1393).

    Source: bronze.bronze_usaspending_award, landed by ingestion.usaspending.load_awards.
    One row per award (generated_unique_award_id). Types are pinned here: dollars
    numeric, dates real DATE, fiscal_year integer (federal FY: Oct-Sep, taken from
    the award period start). Missing source values stay NULL, never 0.
*/

with source as (
    select * from {{ source('bronze', 'bronze_usaspending_award') }}
)

select
    generated_unique_award_id                         as award_id,
    nullif(trim(award_id_fain), '')                   as award_number,
    nullif(trim(recipient_name), '')                  as recipient_name,
    nullif(trim(recipient_uei), '')                   as recipient_uei,
    recipient_type,
    nullif(trim(aln), '')                             as assistance_listing_number,
    nullif(trim(aln_title), '')                       as assistance_listing_title,
    nullif(trim(awarding_agency), '')                 as awarding_agency,
    nullif(trim(funding_agency), '')                  as funding_agency,
    award_type,
    total_obligation::numeric(18,2)                   as total_obligation,
    total_outlays::numeric(18,2)                      as total_outlays,
    period_start::date                                as period_start,
    period_end::date                                  as period_end,
    case when period_start is not null
         then (extract(year from period_start)::int
               + case when extract(month from period_start) >= 10 then 1 else 0 end)
    end::integer                                      as fiscal_year,
    upper(nullif(trim(pop_state_code), ''))           as pop_state_code,
    nullif(trim(pop_state), '')                       as pop_state,
    nullif(trim(pop_county), '')                      as pop_county,
    nullif(trim(pop_city), '')                        as pop_city,
    upper(nullif(trim(recipient_state_code), ''))     as recipient_state_code,
    nullif(trim(description), '')                     as description,
    source_updated_at::timestamp                      as source_updated_at,
    ingestion_date                                    as ingested_at
from source
where generated_unique_award_id is not null
