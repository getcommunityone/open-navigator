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

    PK bill_sponsor_id = md5(bill_uid || '|' || ocd_person_id || '|' ||
    coalesce(classification,'')) (verified unique). FK bill_uid -> bills.bill_uid.
    FK person_uid -> mdm_person.person_uid: every AL person sponsor resolves to a
    legislator now in mdm_person (100%), so person_uid is NOT NULL; the relationships
    test guards against any future miss when more states are loaded.

    Only person sponsors are carried (organization sponsors are dropped upstream in
    stg_openstates__bill_sponsorship). primary_party is the sponsor's party from the
    OpenStates legislator source.
*/

with

linked as (
    select * from {{ ref('int_bills__sponsor_person_linked') }}
)

select
    md5(
        md5('openstates_bill|' || ocd_bill_id)
        || '|' || ocd_person_id
        || '|' || coalesce(classification, '')
    )                                                      as bill_sponsor_id,
    md5('openstates_bill|' || ocd_bill_id)                 as bill_uid,
    person_uid,
    ocd_person_id,
    sponsor_name,
    is_primary,
    classification,
    primary_party,
    current_timestamp                                      as dbt_loaded_at
from linked
