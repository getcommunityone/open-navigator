{{
    config(
        materialized='table',
        tags=['gold', 'elections', 'google_civic'],
    )
}}

/*
    Mart (fct): elections — the c1_election surface.

    Reproduces upsert_elections() + _election_rows_for_upsert() from
    scripts/datasources/openstates/sync_elections_to_c1.py.

    The legacy logic:
      * _election_rows_for_upsert: one bronze row per resolved election_id,
        PREFERRING an actual record_type='election' row when the group has one,
        otherwise falling back to the first child (candidacy/ballot_measure)
        carrying that election_id.
      * upsert_elections: then dedups again on election_id (seen_election_ids),
        so the net grain is one row per resolved election_id.

    Column mapping (c1_election):
        id            = election_id
        legacy_id     = bronze_record_id
        name          = election_name or source_name or 'Election'
        election_date, election_type, election_status
        jurisdiction_id = truncate(jurisdiction_id, 300)
        division_id   = truncate(ocd_jurisdiction_id or jurisdiction_id, 300)
        state_code
        dedupe_key
        source        = truncate(source_name or 'bronze_elections_scraped', 100)
        source_url
        links         = raw_row->'links'  (default [])
        sources       = raw_row->'sources' (default [])
        extras        = raw_row

    The c1_electionsource child rows (_source_rows) are a separate normalized
    table; see "DEFERRED" in the schema yml.
*/

with

source as (
    select * from {{ ref('int_google_civic__election_ids') }}
),

prioritized as (
    -- Prefer a real 'election' record per election_id; fall back to a child row.
    -- record_rank 0 for election rows, 1 otherwise -> picked first by the
    -- latest_per_natural_key order key built below.
    select
        *,
        case when record_type = 'election' then 0 else 1 end as record_rank,
        -- Descending order key: election rows (rank 0) must sort AFTER child
        -- rows so `desc` picks them; encode as a sortable surrogate.
        case when record_type = 'election' then bronze_record_id + 1000000000000000
             else bronze_record_id end as _pick_order
    from source
),

picked as (
    {{ latest_per_natural_key('prioritized', 'election_id', '_pick_order') }}
),

final as (
    select
        election_id                                     as id,
        bronze_record_id                                as legacy_id,
        coalesce(election_name, source_name, 'Election') as name,
        election_date,
        election_type,
        election_status,
        fit_jurisdiction_id                             as jurisdiction_id,
        division_id,
        state_code,
        dedupe_key,
        {{ c1_truncate("coalesce(source_name, 'bronze_elections_scraped')", c1_limit('source')) }} as source,
        source_url,
        coalesce(raw_row -> 'links', '[]'::jsonb)       as links,
        coalesce(raw_row -> 'sources', '[]'::jsonb)     as sources,
        coalesce(raw_row, '{}'::jsonb)                  as extras,
        current_timestamp                               as dbt_loaded_at
    from picked
)

select * from final
