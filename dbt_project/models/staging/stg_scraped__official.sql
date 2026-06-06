{{ config(materialized='view') }}

/*
    Staging: municipal council members scraped from city sites.

    Source: bronze.bronze_officials_scraped (landed by
    ingestion.municipal.load_council_officials, rows from
    scrapers.municipal.council_roster). Fills the council gap where OpenStates
    has a city's mayor but not its district council members.

    Cleans/casts to the same presented shape contact_official needs from the
    OpenStates staging model (stg_openstates__official): a cleaned title, a
    2-letter state_code, full state name, and is_current. party is NULL (city
    council seats are non-partisan / not captured).

    Keep only rows that name a real official and resolve to a state.

    GRAIN: one row per scraped membership (ocd_membership_id is unique).
*/

with source as (
    select * from {{ source('bronze', 'bronze_officials_scraped') }}
)

select
    ocd_membership_id,
    nullif(trim(full_name), '')              as full_name,
    nullif(trim(title), '')                  as title,
    nullif(trim(jurisdiction), '')           as jurisdiction,
    upper(nullif(trim(state_code), ''))      as state_code,
    nullif(trim(state), '')                  as state,
    cast(null as text)                       as party,
    nullif(trim(district), '')               as district,
    nullif(trim(office), '')                 as office,
    nullif(lower(trim(email)), '')           as email,
    nullif(trim(phone), '')                  as phone,
    nullif(trim(photo_url), '')              as photo_url,
    coalesce(is_current, true)               as is_current
from source
where nullif(trim(full_name), '') is not null
  and upper(nullif(trim(state_code), '')) is not null
