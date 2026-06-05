{{ config(materialized='view') }}

/*
    Staging (OpenStates bills): clean/cast the core bill columns from
    bronze_bills_openstates (one row per bill, natural key ocd_bill_id).

    - *_date columns are source-native TEXT (ISO timestamps); cast to date here so
      intermediate/marts/public are uniform.
    - state_code is already derived in bronze; kept as char(2) trimmed.
    - subject (jsonb array) is preserved for the trending-topics aggregate; it is
      exploded downstream in rpt_bill_map_aggregate, not here.
    - year is an INTEGER (per the calendar-year storage rule): derived from the
      latest action date, falling back to the first action date, then to the
      leading 4-digit year embedded in session_name / session_identifier. It is
      serialized as a string only at the JSON/wire boundary, not here.

    See web_docs/docs/dbt/entity-resolution-mdm.md and CONVENTIONS.md.
    Four-CTE template: source -> parsed -> final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_bills_openstates') }}
),

parsed as (
    select
        ocd_bill_id,
        identifier,
        title,
        classification,
        subject,
        from_organization_id,
        legislative_session_id,
        session_identifier,
        session_name,
        ocd_jurisdiction_id,
        upper(left(trim(state_code), 2))                       as state_code,
        first_action_date::date                                as first_action_date,
        latest_action_date::date                               as latest_action_date,
        latest_passage_date::date                              as latest_passage_date,
        latest_action_description,
        citations,
        extras,
        sponsorships,
        source_created_at,
        source_updated_at,
        synced_at,
        -- INTEGER calendar year: prefer the action date year, then the first
        -- 4-digit year token in the session label. Stays integer for range/sort.
        coalesce(
            extract(year from latest_action_date::date)::int,
            extract(year from first_action_date::date)::int,
            nullif((regexp_match(coalesce(session_name, session_identifier, ''), '(\d{4})'))[1], '')::int
        )                                                      as year
    from source
),

final as (
    select * from parsed
)

select * from final
