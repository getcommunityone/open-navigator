{{ config(materialized='view') }}

/*
    Staging (OpenStates bill abstracts, #1274): one row per OpenStates bill (natural key ocd_bill_id) with its
    abstracts flattened to one text field. bronze_bills_openstates keeps abstracts as a jsonb array of
    {abstract, note} objects; topic models search this text alongside the title (e.g. topic_legislation_bill).
    Bills without an abstract get ''. A separate view so stg_openstates__bill (and the views over it) stay
    untouched.
*/

with

source as (
    select ocd_bill_id, abstracts from {{ source('bronze', 'bronze_bills_openstates') }}
),

final as (
    select
        s.ocd_bill_id,
        coalesce(
            (select string_agg(nullif(trim(a ->> 'abstract'), ''), ' ')
             from jsonb_array_elements(case when jsonb_typeof(s.abstracts) = 'array' then s.abstracts else '[]'::jsonb end) a),
            ''
        )::text as abstract_text
    from source s
)

select * from final
