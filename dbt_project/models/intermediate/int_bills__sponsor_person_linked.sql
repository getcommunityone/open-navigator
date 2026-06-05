{{ config(materialized='table') }}

/*
    Intermediate (OpenStates bills): resolve each person sponsorship to the MDM
    person pool.

    Grain: one row per (bill, person sponsor) from stg_openstates__bill_sponsorship.

    Resolution: join sponsorship.ocd_person_id ->
    bronze_jurisdiction_openstates.openstates_person_id (100% match for AL) and
    derive person_uid = md5('bronze_jurisdiction_openstates|' || openstates_person_id),
    matching the PK of the public.legislator mart so the bridge FKs to it.
    primary_party is carried from the legislator source.

    person_uid is derived from the JOINED legislator row, so it is NULL when a
    sponsor's ocd_person_id has no legislator record (the sponsor is still kept,
    by name, with a nullable person_uid). The FK to legislator is validated by the
    relationships test on the public.bill_sponsorship mart.
*/

with

sponsorships as (
    select * from {{ ref('stg_openstates__bill_sponsorship') }}
),

-- join the already-deduped legislator mart (one row per person) rather than raw
-- bronze, which now holds multiple sync batches (a person in two batches would
-- otherwise multiply sponsorship rows).
legislators as (
    select
        openstates_person_id,
        person_uid,
        primary_party
    from {{ ref('legislator') }}
),

linked as (
    select
        s.ocd_bill_id,
        s.ocd_sponsorship_id,
        s.ocd_person_id,
        l.person_uid,
        s.sponsor_name,
        s.is_primary,
        s.classification,
        l.primary_party
    from sponsorships s
    left join legislators l
        on l.openstates_person_id = s.ocd_person_id
)

select * from linked
