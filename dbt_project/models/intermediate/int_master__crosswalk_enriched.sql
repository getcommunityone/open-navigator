{{ config(materialized='table') }}

/*
    Intermediate: crosswalk enriched with a full state name (MDM).

    Reproduces the `enriched_crosswalk` CTE in consolidate_to_master() from
    scripts/datasources/master_data/create_jurisdiction_master.py:
      full_state_name = COALESCE(jurisdiction.state  -- via crosswalk.search_id
                                 , state_code -> name lookup CASE)
    Here `search_id` is our `jurisdiction_ref_id`. The state-code -> name CASE is
    the state_code_to_name macro.
*/

with

crosswalk as (
    select * from {{ ref('int_master__crosswalk') }}
),

jur as (
    select jurisdiction_id, state_name from {{ ref('stg_mdm__jurisdiction') }}
),

final as (
    select
        crosswalk.*,
        coalesce(
            jur.state_name,
            {{ state_code_to_name('crosswalk.state_code') }}
        )                                   as full_state_name
    from crosswalk
    left join jur
        on crosswalk.jurisdiction_ref_id = jur.jurisdiction_id
)

select * from final
