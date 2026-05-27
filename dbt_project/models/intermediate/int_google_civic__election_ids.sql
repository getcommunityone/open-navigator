{{ config(materialized='table') }}

/*
    Intermediate: resolve the shared c1 election id + dedupe_key for every
    bronze election-domain record.

    This is the keystone the c1 promotion marts all depend on. It reproduces
    _election_id() from scripts/datasources/openstates/sync_elections_to_c1.py,
    which has three branches keyed on record_type and the presence of a parent
    election_id carried in raw_row:

      1. record_type = 'election'
           dedupe_key = key(jurisdiction, date, name, type)
           election_id = fit_c1_id(ocd_id, fallback = dedupe_key or id)
      2. record_type in ('candidacy','ballot_measure') AND parent_election_id set
           election_id = fit_c1_id(parent_election_id, fallback = parent_election_id)
           dedupe_key  = key(jurisdiction, date, name, type)
                         (or key('election', election_id) when name/date/type all null)
      3. record_type in ('candidacy','ballot_measure') AND no parent_election_id
           dedupe_key = key(jurisdiction, date, name, type, id)
           election_id = fit_c1_id(ocd_id, fallback = dedupe_key or id)

    where ``jurisdiction = jurisdiction_id or ocd_jurisdiction_id``. The resolved
    election_id is then re-fit (fit_c1_id(election_id, fallback=id)) exactly as the
    upserts do before keying child rows. division_id and jurisdiction_id are
    truncated to their c1 limits here so divisions / elections / contests all
    agree.

    DEVIATION (flagged): the legacy fallback hashed overflowing ids via Python
    uuid5 (no SQL equivalent). Here the deterministic fallback is the bronze row
    id as text; dedupe_key (the ON CONFLICT key that drives dedup) is reproduced
    verbatim, so dedup correctness is preserved.
*/

with

source as (
    select * from {{ ref('stg_google_civic__election_record') }}
),

keyed as (
    select
        *,
        coalesce(jurisdiction_id, ocd_jurisdiction_id)              as election_jurisdiction,
        {{ c1_truncate('coalesce(ocd_jurisdiction_id, jurisdiction_id)', c1_limit('division_id')) }}
                                                                    as division_id,
        {{ c1_truncate('jurisdiction_id', c1_limit('jurisdiction_id')) }}
                                                                    as fit_jurisdiction_id
    from source
),

dedupe_keyed as (
    select
        *,
        case
            when record_type = 'election'
                then {{ c1_dedupe_key('election_jurisdiction', "coalesce(election_date::text, '')", 'election_name', 'election_type') }}
            when parent_election_id is not null
                then coalesce(
                    {{ c1_dedupe_key('election_jurisdiction', "coalesce(election_date::text, '')", 'election_name', 'election_type') }},
                    {{ c1_dedupe_key("'election'", "trim(parent_election_id)") }}
                )
            else {{ c1_dedupe_key('election_jurisdiction', "coalesce(election_date::text, '')", 'election_name', 'election_type', 'bronze_record_id::text') }}
        end as dedupe_key,
        -- The raw election_id candidate before fit/fallback resolution.
        case
            when record_type = 'election' then ocd_id
            when parent_election_id is not null then parent_election_id
            else ocd_id
        end as election_id_candidate
    from keyed
),

resolved as (
    select
        *,
        -- fit_c1_id(candidate, fallback): use the candidate id when it fits 50
        -- chars, else the deterministic surrogate (bronze row id). The legacy
        -- code re-fits the resolved id once more (fit_c1_id(election_id, id));
        -- since the surrogate already fits, a single fit is equivalent.
        {{ c1_fit_id('election_id_candidate', 'bronze_record_id::text') }} as election_id
    from dedupe_keyed
),

final as (
    select
        bronze_record_id,
        scrape_batch_id,
        record_type,
        ocd_id,
        election_id,
        dedupe_key,
        parent_election_id,
        election_name,
        election_date,
        election_type,
        election_status,
        election_jurisdiction,
        ocd_jurisdiction_id,
        division_id,
        fit_jurisdiction_id,
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
        raw_row,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from resolved
)

select * from final
