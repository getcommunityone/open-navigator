{{
    config(
        materialized='table',
        tags=['gold', 'elections', 'google_civic'],
    )
}}

/*
    Mart (dim): election divisions — the c1_division surface.

    Reproduces upsert_divisions() from
    scripts/datasources/openstates/sync_elections_to_c1.py:

        for every bronze row with a non-null division_id
        (= ocd_jurisdiction_id or jurisdiction_id, truncated to 300):
            id            = division_id
            name          = truncate(jurisdiction_id or election_name or division_id, 500)
            classification= 'jurisdiction'
            parent_id     = NULL
            jurisdiction_id = truncate(jurisdiction_id, 300)
            state_code
            extras        = {"source": source_name or 'bronze_elections_scraped'}

    The Python upsert collapsed to ONE payload per division_id via a dict
    (ON CONFLICT (id) DO UPDATE). Reproduced here with row_number() over
    division_id (keep the most recent bronze row -> matches dict last-write-wins
    under the loader's ORDER BY id). One row per division_id.
*/

with

source as (
    select * from {{ ref('int_google_civic__election_ids') }}
),

with_division as (
    select
        division_id,
        {{ c1_truncate('coalesce(jurisdiction_id, election_name, division_id)', 500) }} as division_name_raw,
        division_id                                     as division_name_fallback,
        fit_jurisdiction_id                             as jurisdiction_id,
        state_code,
        coalesce(source_name, 'bronze_elections_scraped') as source_name,
        bronze_record_id
    from source
    where division_id is not null
),

deduped as (
    {{ latest_per_natural_key('with_division', 'division_id', 'bronze_record_id') }}
),

final as (
    select
        division_id                                     as id,
        coalesce(division_name_raw, division_name_fallback) as name,
        'jurisdiction'::text                            as classification,
        cast(null as text)                              as parent_id,
        jurisdiction_id,
        state_code,
        json_build_object('source', source_name)        as extras,
        current_timestamp                               as dbt_loaded_at
    from deduped
)

select * from final
