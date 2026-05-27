{{ config(materialized='view') }}

/*
    Staging: election-domain records landed in bronze.bronze_elections_scraped
    (1 row per bronze record, discriminated by record_type).

    1:1 with the bronze landing table written by ingestion.google_civic.officials
    (election | candidacy | ballot_measure rows). Light cleaning + type
    stabilization only — the c1-promotion id resolution, election grouping and
    per-table dedup happen downstream in int_google_civic__election_ids and the
    election marts (reproducing scripts/datasources/openstates/sync_elections_to_c1.py).

    The only derivation done here is pulling the parent ``election_id`` out of the
    raw_row JSONB (candidacy / ballot_measure rows carry their parent civic
    election id there — see _election_id() in the legacy loader). Four-CTE
    template: source -> renamed -> filtered -> final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_elections_scraped') }}
),

renamed as (
    select
        id                                              as bronze_record_id,
        scrape_batch_id::text                           as scrape_batch_id,
        nullif(trim(record_type), '')                   as record_type,
        nullif(trim(ocd_id), '')                        as ocd_id,
        nullif(trim(election_name), '')                 as election_name,
        election_date                                   as election_date,
        nullif(trim(election_type), '')                 as election_type,
        nullif(trim(election_status), '')               as election_status,
        nullif(trim(ocd_jurisdiction_id), '')           as ocd_jurisdiction_id,
        upper(nullif(trim(state_code), ''))             as state_code,
        nullif(trim(jurisdiction_id), '')               as jurisdiction_id,
        nullif(trim(candidate_name), '')                as candidate_name,
        nullif(trim(candidate_party), '')               as candidate_party,
        nullif(trim(candidate_post), '')                as candidate_post,
        nullif(trim(candidate_status), '')              as candidate_status,
        candidate_vote_count                            as candidate_vote_count,
        candidate_vote_percent                          as candidate_vote_percent,
        nullif(trim(measure_title), '')                 as measure_title,
        nullif(trim(measure_summary), '')               as measure_summary,
        nullif(trim(measure_classification), '')        as measure_classification,
        measure_yes_count                               as measure_yes_count,
        measure_no_count                                as measure_no_count,
        nullif(trim(measure_outcome), '')               as measure_outcome,
        nullif(trim(source_url), '')                    as source_url,
        nullif(trim(source_name), '')                   as source_name,
        -- Parent civic election id carried in the JSONB payload (candidacy /
        -- ballot_measure rows). Mirrors raw.get("election_id") in _election_id().
        nullif(trim(raw_row ->> 'election_id'), '')     as parent_election_id,
        raw_row                                         as raw_row,
        loaded_at                                       as source_ingested_at
    from source
),

filtered as (
    -- Business rule: only the three contracted record types promote to c1.
    select *
    from renamed
    where record_type in ('election', 'candidacy', 'ballot_measure')
),

final as (
    select
        bronze_record_id,
        scrape_batch_id,
        record_type,
        ocd_id,
        election_name,
        election_date,
        election_type,
        election_status,
        ocd_jurisdiction_id,
        state_code,
        jurisdiction_id,
        candidate_name,
        candidate_party,
        candidate_post,
        candidate_status,
        candidate_vote_count,
        candidate_vote_percent,
        measure_title,
        measure_summary,
        measure_classification,
        measure_yes_count,
        measure_no_count,
        measure_outcome,
        source_url,
        source_name,
        parent_election_id,
        raw_row,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from filtered
)

select * from final
