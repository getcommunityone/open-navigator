{{
    config(
        materialized='table',
        tags=['gold', 'elections', 'ballot_measures', 'google_civic'],
    )
}}

/*
    Mart (fct): ballot measures from the election scrape — the civic_ballotmeasure
    surface.

    Named *_civic to avoid colliding with the existing NIST/VIP
    {{ ref('ballot_measures') }} mart (different source + schema). Reproduces
    upsert_ballot_measures() from
    scripts/datasources/openstates/sync_elections_to_c1.py.

    Legacy logic (ballot_measure rows only):
        measure_key = dedupe_key(election_id, measure_title, measure_classification, measure_outcome)
        measure_id  = fit_c1_id(ocd_id, fallback = measure_key or id)
        -> upsert ON CONFLICT (dedupe_key) when set, else (id).

    Column mapping (civic_ballotmeasure):
        id            = measure_id
        legacy_id     = bronze_record_id
        election_id   = fit_c1_id(election_id, id)
        name          = measure_title or election_name or 'Ballot measure'
        title         = measure_title
        summary       = measure_summary
        classification= measure_classification
        status        = measure_outcome
        result        = measure_outcome
        yes_votes     = measure_yes_count
        no_votes      = measure_no_count
        yes_percentage= NULL
        jurisdiction_id = truncate(jurisdiction_id, 300)
        state_code
        dedupe_key    = measure_key
        source        = truncate(source_name or 'bronze_elections_scraped', 100)
        source_url
        extras        = raw_row
        raw_row       = raw_row

    The civic_ballotmeasuresource child rows (_source_rows) are a separate
    normalized table; see "DEFERRED" in the schema yml.
*/

with

source as (
    select * from {{ ref('int_google_civic__election_ids') }}
),

measures as (
    select
        *,
        {{ c1_dedupe_key('election_id', 'measure_title', 'measure_classification', 'measure_outcome') }} as measure_key
    from source
    where record_type = 'ballot_measure'
),

with_measure_id as (
    select
        *,
        {{ c1_fit_id('ocd_id', 'coalesce(measure_key, bronze_record_id::text)') }} as measure_id
    from measures
),

deduped as (
    -- ON CONFLICT (dedupe_key) collapses rows sharing a measure_key; DO UPDATE
    -- => last row wins -> keep highest bronze id. NULL-key rows conflict on id
    -- (row-unique), so partition on coalesce(measure_key, measure_id).
    {{ latest_per_natural_key('with_measure_id', 'coalesce(measure_key, measure_id)', 'bronze_record_id') }}
),

final as (
    select
        measure_id                                      as id,
        bronze_record_id                                as legacy_id,
        election_id,
        coalesce(measure_title, election_name, 'Ballot measure') as name,
        measure_title                                   as title,
        measure_summary                                 as summary,
        measure_classification                          as classification,
        measure_outcome                                 as status,
        measure_outcome                                 as result,
        measure_yes_count                               as yes_votes,
        measure_no_count                                as no_votes,
        cast(null as double precision)                  as yes_percentage,
        fit_jurisdiction_id                             as jurisdiction_id,
        state_code,
        measure_key                                     as dedupe_key,
        {{ c1_truncate("coalesce(source_name, 'bronze_elections_scraped')", c1_limit('source')) }} as source,
        source_url,
        coalesce(raw_row, '{}'::jsonb)                  as extras,
        coalesce(raw_row, '{}'::jsonb)                  as raw_row,
        current_timestamp                               as dbt_loaded_at
    from deduped
)

select * from final
