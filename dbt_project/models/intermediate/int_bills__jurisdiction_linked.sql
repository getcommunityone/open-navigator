{{ config(materialized='table') }}

/*
    Intermediate (OpenStates bills): resolve each bill to a jurisdiction_id.

    Grain: one row per bill (ocd_bill_id), unchanged from stg_openstates__bill.

    Primary resolution path: state_code -> public.jurisdictions.jurisdiction_id for
    the STATE row (jurisdiction_type='state'). State legislatures map to the
    state-level jurisdiction (confirmed: jurisdiction_id='AL' name='Alabama'). The
    states row in int_jurisdictions keys jurisdiction_id = the 2-letter USPS code,
    so this is a direct state_code = jurisdiction_id match against the state rows.

    jurisdiction_id is NULLABLE: federal / unmapped bills are allowed (e.g. a
    state_code with no matching state row, or future place-level bills).
*/

with

bills as (
    select * from {{ ref('stg_openstates__bill') }}
),

-- state-level jurisdictions only (jurisdiction_id = USPS code for the state row)
state_jurisdictions as (
    select
        jurisdiction_id,
        state_code
    from {{ ref('int_jurisdictions') }}
    where jurisdiction_type = 'state'
),

linked as (
    select
        b.*,
        j.jurisdiction_id
    from bills b
    left join state_jurisdictions j
        on j.state_code = b.state_code
)

select * from linked
