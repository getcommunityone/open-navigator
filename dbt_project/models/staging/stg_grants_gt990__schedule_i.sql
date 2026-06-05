{{ config(materialized='view') }}

/*
    Staging: GivingTuesday 990 Schedule I Part II grants (1 row per grant line).

    Reads bronze.bronze_grants_gt990_schedule_i, landed by
    ingestion.givingtuesday.load --datamart schedule_i (ScheduleIPart2Grants
    datamart). Light cleaning + type stabilization only — EIN normalization,
    tax_year cast to integer (per the Calendar-Years rule), state uppercased,
    blank strings nulled. Grantor -> org-master resolution and the surrogate
    grant_id happen downstream in the `grant` mart. Four-CTE template:
    source -> renamed -> filtered -> final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_grants_gt990_schedule_i') }}
),

renamed as (
    select
        nullif(trim(grantor_ein), '')                  as grantor_ein,
        -- bare calendar year -> integer storage (CLAUDE.md Calendar-Years rule)
        cast(tax_year as integer)                      as tax_year,
        nullif(trim(grantor_name), '')                 as grantor_name,
        nullif(trim(grantee_name), '')                 as grantee_name,
        nullif(trim(grantee_ein), '')                  as grantee_ein,
        nullif(trim(grantee_city), '')                 as grantee_city,
        upper(nullif(trim(grantee_state_code), ''))    as grantee_state_code,
        nullif(trim(grantee_zip), '')                  as grantee_zip,
        nullif(trim(irc_section), '')                  as irc_section,
        cash_grant_amount                              as cash_grant_amount,
        noncash_assistance_amount                      as noncash_assistance_amount,
        nullif(trim(valuation_method), '')             as valuation_method,
        nullif(trim(noncash_description), '')          as noncash_description,
        nullif(trim(purpose), '')                      as purpose,
        nullif(trim(source_url), '')                   as source_url
    from source
),

filtered as (
    select *
    from renamed
    where grantor_ein is not null
      and length(grantor_ein) >= 9
      and grantee_name is not null
),

final as (
    select * from filtered
)

select * from final
