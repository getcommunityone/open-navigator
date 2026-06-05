{{ config(materialized='view') }}

/*
    Staging: current government officials from OpenStates.

    Source: bronze.bronze_officials_openstates (landed by
    ingestion.openstates.officials — one row per person×membership across ALL
    organization classifications, so mayors/council members are included, not
    just legislators).

    This model cleans/casts and derives the canonical contact_official shape:
      - state_code (2-letter) recovered from the OCD jurisdiction id, covering
        state:/territory:/district: tokens (so PR + DC resolve, not just states),
        AND state (full name) via the state_code_to_name macro.
      - title: a cleaned, title-cased role.
      - is_current: term still open or ending on/after the current-term cutoff.

    Keep only rows that name a real official (full_name + role) AND resolve to a
    state — the ~21k jurisdiction-less committee memberships (chair/member/ex
    officio of sub-orgs with no jurisdiction_id) are not jurisdiction officials
    and are dropped here.

    GRAIN: one row per membership (ocd_membership_id is unique). Feeds the public
    contact_official mart.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_officials_openstates') }}
),

parsed as (
    select
        ocd_membership_id,
        ocd_person_id,
        ocd_organization_id,
        ocd_jurisdiction_id,

        nullif(trim(full_name), '')                            as full_name,
        nullif(trim(party), '')                                as party,

        -- raw role kept for provenance; title is the cleaned, presented form
        nullif(trim(role), '')                                 as role,
        nullif(trim(initcap(role)), '')                        as title,

        nullif(trim(district), '')                             as district,
        nullif(trim(organization_name), '')                    as jurisdiction,
        nullif(trim(organization_classification), '')          as chamber,

        nullif(lower(trim(email)), '')                         as email,
        nullif(trim(image), '')                                as photo_url,

        -- Recover the 2-letter code from state:/territory:/district: tokens.
        upper(
            (regexp_match(
                ocd_jurisdiction_id,
                '/(?:state|territory|district):([a-z]{2})(?:/|$)'
            ))[1]
        )                                                      as state_code,

        nullif(trim(start_date), '')                           as start_date_raw,
        nullif(trim(end_date), '')                             as end_date_raw,
        synced_at
    from source
),

filtered as (
    select * from parsed
    where full_name is not null
      and role is not null
      and state_code is not null
),

final as (
    select
        ocd_membership_id,
        ocd_person_id,
        ocd_organization_id,
        ocd_jurisdiction_id,

        full_name,
        party,
        role,
        title,
        district,
        jurisdiction,
        chamber,
        email,
        photo_url,

        state_code,
        {{ state_code_to_name('state_code') }}                 as state,

        -- term dates as real DATEs where parseable, else NULL (source is text)
        case
            when start_date_raw ~ '^\d{4}-\d{2}-\d{2}'
            then substring(start_date_raw from 1 for 10)::date
        end                                                    as start_date,
        case
            when end_date_raw ~ '^\d{4}-\d{2}-\d{2}'
            then substring(end_date_raw from 1 for 10)::date
        end                                                    as end_date,

        -- open-ended term, or one ending on/after the current-term cutoff
        (
            end_date_raw is null
            or end_date_raw >= '2024-01-01'
        )                                                      as is_current,

        synced_at
    from filtered
)

select * from final
