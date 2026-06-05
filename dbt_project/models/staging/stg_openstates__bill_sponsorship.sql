{{ config(materialized='view') }}

/*
    Staging (OpenStates bill sponsorships): explode the sponsorships jsonb array on
    bronze_bills_openstates to one row per (bill, sponsor).

    Each sponsorship element: {id,name,entity_type,primary,classification,
    person_id,organization_id}. ocd_person_id (person_id) matches OpenStates
    legislators (bronze_jurisdiction_openstates.openstates_person_id) at 100% for AL
    and is the join key to the MDM person pool downstream.

    Scope: ONLY entity_type='person' sponsors are kept here — organization sponsors
    (entity_type='organization', person_id null) are dropped because the bill ->
    person bridge and FK to mdm_person are person-grained. If an org-sponsor bridge
    is needed later it should be a separate model keyed on organization_id.

    Four-CTE template: source -> exploded -> persons -> final.
*/

with

source as (
    select
        ocd_bill_id,
        sponsorships
    from {{ source('bronze', 'bronze_bills_openstates') }}
),

exploded as (
    select
        s.ocd_bill_id,
        elem
    from source s,
        lateral jsonb_array_elements(s.sponsorships) as elem
    where jsonb_typeof(s.sponsorships) = 'array'
),

persons as (
    select
        ocd_bill_id,
        nullif(elem ->> 'person_id', '')                       as ocd_person_id,
        nullif(elem ->> 'name', '')                            as sponsor_name,
        coalesce((elem ->> 'primary')::boolean, false)         as is_primary,
        nullif(elem ->> 'classification', '')                  as classification,
        nullif(elem ->> 'entity_type', '')                     as entity_type
    from exploded
    where (elem ->> 'entity_type') = 'person'
      and nullif(elem ->> 'person_id', '') is not null
),

final as (
    select * from persons
)

select * from final
