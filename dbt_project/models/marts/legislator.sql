{{
  config(
    materialized='table',
    indexes=[
      {'columns': ['openstates_person_id'], 'type': 'btree', 'unique': True},
      {'columns': ['state_code'], 'type': 'btree'},
      {'columns': ['jurisdiction_id'], 'type': 'btree'}
    ]
  )
}}

/*
    Mart: public.legislator — one row per OpenStates legislator (PK person_uid),
    sourced from bronze.bronze_jurisdiction_openstates (the opencivicdata_person
    sync). This is the person entity that bill sponsorships link to.

    person_uid = md5('bronze_jurisdiction_openstates|' || openstates_person_id) —
    the SAME deterministic key int_bills__sponsor_person_linked derives, so the
    bill_sponsorship bridge FKs here. The key also matches what a future fold of
    legislators into the Splink-clustered mdm_person would produce, so ids line up
    if/when that happens.

    jurisdiction_id is a NULLABLE FK -> jurisdictions.jurisdiction_id (the
    state-level row, resolved by state_code = USPS code), mirroring bills. The
    source has one row per person but we dedupe defensively on openstates_person_id
    so the PK is guaranteed unique.

    Contract enforced: PK + FK declared so Postgres enforces them.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_jurisdiction_openstates') }}
),

-- one row per OpenStates person (defensive dedupe; keep the most recently synced)
deduped as (
    select *
    from (
        select
            *,
            row_number() over (
                partition by openstates_person_id
                order by synced_at desc nulls last
            ) as rn
        from source
        where openstates_person_id is not null
    ) ranked
    where rn = 1
),

-- state-level jurisdictions only (jurisdiction_id = USPS code for the state row)
state_jurisdictions as (
    select
        jurisdiction_id,
        state_code
    from {{ ref('int_jurisdictions') }}
    where jurisdiction_type = 'state'
)

select
    md5('bronze_jurisdiction_openstates|' || d.openstates_person_id) as person_uid,
    cast(d.openstates_person_id as text)        as openstates_person_id,
    cast(d.name as text)                        as full_name,
    cast(d.given_name as text)                  as given_name,
    cast(d.family_name as text)                 as family_name,
    cast(d.primary_party as text)               as primary_party,
    cast(d.gender as text)                      as gender,
    cast(d.email as text)                       as email,
    cast(d.state_code as text)                  as state_code,
    cast(j.jurisdiction_id as text)             as jurisdiction_id,
    cast(d.current_jurisdiction_id as text)     as current_jurisdiction_id,
    cast(d.birth_date as text)                  as birth_date,
    cast(d.biography as text)                   as biography,
    cast(d.image as text)                       as image,
    current_timestamp                           as dbt_loaded_at
from deduped d
left join state_jurisdictions j
    on j.state_code = d.state_code
