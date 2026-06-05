{{
  config(
    materialized='table',
    indexes=[
      {'columns': ['bill_uid'], 'type': 'btree'},
      {'columns': ['person_uid'], 'type': 'btree'}
    ]
  )
}}

/*
    Mart: public.bill_sponsorship — bridge, one row per (bill, person sponsor).
    Built from int_bills__sponsor_person_linked.

    PK bill_sponsor_id = md5 of the source sponsorship uuid (ocd_sponsorship_id) —
    the only key guaranteed unique across all states (the (bill, person,
    classification) grain collides on the full dataset because OpenStates carries
    genuine duplicate sponsorship lines). A defensive row_number dedupe keeps one
    row per key. FK bill_uid -> bills.bill_uid. FK person_uid ->
    legislator.person_uid (nullable): every AL person sponsor resolves to a
    legislator (100%); person_uid is left NULL for any sponsor without a legislator
    record, and the relationships test guards the FK.

    Only person sponsors are carried (organization sponsors are dropped upstream in
    stg_openstates__bill_sponsorship). primary_party is the sponsor's party from the
    OpenStates legislator source.
*/

with

linked as (
    select * from {{ ref('int_bills__sponsor_person_linked') }}
),

keyed as (
    select
        md5(
            coalesce(
                ocd_sponsorship_id,
                'openstates_bill|' || ocd_bill_id || '|' || ocd_person_id
                    || '|' || coalesce(classification, '')
            )
        )                                                  as bill_sponsor_id,
        md5('openstates_bill|' || ocd_bill_id)             as bill_uid,
        person_uid,
        ocd_person_id,
        sponsor_name,
        is_primary,
        classification,
        primary_party
    from linked
),

-- defensive dedupe: guarantee PK uniqueness even if a sponsorship uuid recurs
deduped as (
    select *
    from (
        select
            *,
            row_number() over (partition by bill_sponsor_id order by ocd_person_id) as rn
        from keyed
    ) t
    where rn = 1
)

select
    bill_sponsor_id,
    bill_uid,
    person_uid,
    ocd_person_id,
    sponsor_name,
    is_primary,
    classification,
    primary_party,
    current_timestamp                                      as dbt_loaded_at
from deduped
