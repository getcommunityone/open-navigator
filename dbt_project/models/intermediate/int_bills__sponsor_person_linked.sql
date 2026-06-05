{{ config(materialized='table') }}

/*
    Intermediate (OpenStates bills): resolve each person sponsorship to the MDM
    person pool.

    Grain: one row per (bill, person sponsor) from stg_openstates__bill_sponsorship.

    Resolution: join sponsorship.ocd_person_id ->
    bronze_jurisdiction_openstates.openstates_person_id (100% match for AL) and
    derive person_uid = md5('bronze_jurisdiction_openstates|' || openstates_person_id),
    matching the staging key in stg_openstates_legislators__person so it FKs to
    mdm_person.person_uid. primary_party is carried from the legislator source.

    person_uid is derived directly from ocd_person_id even when the legislator row
    is absent (so the bridge never loses a sponsor); the join to the legislator
    source only enriches primary_party. The FK to mdm_person is validated by the
    relationships test on the public.bill_sponsorship mart.
*/

with

sponsorships as (
    select * from {{ ref('stg_openstates__bill_sponsorship') }}
),

legislators as (
    select
        openstates_person_id,
        primary_party
    from {{ source('bronze', 'bronze_jurisdiction_openstates') }}
),

linked as (
    select
        s.ocd_bill_id,
        s.ocd_person_id,
        md5('bronze_jurisdiction_openstates|' || s.ocd_person_id) as person_uid,
        s.sponsor_name,
        s.is_primary,
        s.classification,
        l.primary_party
    from sponsorships s
    left join legislators l
        on l.openstates_person_id = s.ocd_person_id
)

select * from linked
