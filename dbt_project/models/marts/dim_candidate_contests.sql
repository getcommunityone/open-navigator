{{
    config(
        materialized='table',
        tags=['gold', 'elections', 'google_civic'],
    )
}}

/*
    Mart (dim): candidate contests — the c1_candidatecontest surface.

    Reproduces upsert_candidate_contests() from
    scripts/datasources/openstates/sync_elections_to_c1.py.

    Legacy logic (candidacy rows only):
        contest_key = dedupe_key(election_id, candidate_post, candidate_party)
        contest_id  = make_ocd_id('candidatecontest', contest_key or '{election_id}|{id}')
        group_key   = contest_key or contest_id
        -> ONE payload per group_key (first row wins).

    Column mapping (c1_candidatecontest):
        id            = contest_id
        legacy_id     = bronze_record_id
        election_id   = fit_c1_id(election_id, id)
        name          = candidate_post or candidate_name or election_name or 'Contest'
        office        = candidate_post
        status        = candidate_status
        jurisdiction_id = truncate(jurisdiction_id, 300)
        state_code
        dedupe_key    = contest_key
        source        = truncate(source_name or 'bronze_elections_scraped', 100)
        source_url
        extras        = raw_row

    DEVIATION (flagged): make_ocd_id used Python uuid5 (no SQL equivalent); the
    contest id here is 'ocd-cc/' || md5(contest_key) (see c1_contest_id macro).
    fct_candidacies recomputes the identical id, so the join is preserved. The
    contest_key (dedupe_key, the ON CONFLICT key) is reproduced verbatim, so the
    grain matches the legacy upsert.
*/

with

source as (
    select * from {{ ref('int_google_civic__election_ids') }}
),

candidacies as (
    select
        *,
        {{ c1_dedupe_key('election_id', 'candidate_post', 'candidate_party') }} as contest_key
    from source
    where record_type = 'candidacy'
),

with_contest_id as (
    select
        *,
        {{ c1_contest_id('contest_key', "election_id || '|' || bronze_record_id::text") }} as contest_id
    from candidacies
),

keyed as (
    select
        *,
        coalesce(contest_key, contest_id) as group_key
    from with_contest_id
),

deduped as (
    -- One row per group_key; the legacy dict kept the FIRST row encountered
    -- under ORDER BY id, i.e. the lowest bronze_record_id. desc on the negated
    -- id keeps the smallest id.
    {{ latest_per_natural_key('keyed', 'group_key', '(-bronze_record_id)') }}
),

final as (
    select
        contest_id                                      as id,
        bronze_record_id                                as legacy_id,
        election_id,
        coalesce(candidate_post, candidate_name, election_name, 'Contest') as name,
        candidate_post                                  as office,
        candidate_status                                as status,
        fit_jurisdiction_id                             as jurisdiction_id,
        state_code,
        contest_key                                     as dedupe_key,
        {{ c1_truncate("coalesce(source_name, 'bronze_elections_scraped')", c1_limit('source')) }} as source,
        source_url,
        coalesce(raw_row, '{}'::jsonb)                  as extras,
        current_timestamp                               as dbt_loaded_at
    from deduped
)

select * from final
