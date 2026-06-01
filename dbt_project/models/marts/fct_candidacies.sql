{{
    config(
        materialized='table',
        tags=['gold', 'elections', 'google_civic'],
    )
}}

/*
    Mart (fct): candidacies — the civic_candidacy surface.

    Reproduces upsert_candidacies() from
    scripts/datasources/openstates/sync_elections_to_c1.py.

    Legacy logic (candidacy rows only):
        contest_key      = dedupe_key(election_id, candidate_post, candidate_party)
        contest_id       = make_ocd_id('candidatecontest', contest_key or '{election_id}|{id}')
        resolved_contest = contest_ids[contest_key or contest_id]   (== contest_id here)
        candidacy_key    = dedupe_key(election_id, contest_id, candidate_name, candidate_party)
        candidacy_id     = fit_c1_id(ocd_id, fallback = candidacy_key or id)
        -> upsert ON CONFLICT (dedupe_key) when set, else (id).

    Column mapping (civic_candidacy):
        id            = candidacy_id
        legacy_id     = bronze_record_id
        election_id   = fit_c1_id(election_id, id)
        contest_id    = fit_c1_id(resolved_contest_id, id)
        contest_name  = candidate_post or candidate_name or election_name or 'Contest'
        person_name   = candidate_name
        person_id     = NULL
        party         = candidate_party
        status        = candidate_status
        vote_count    = candidate_vote_count
        vote_percent  = candidate_vote_percent
        jurisdiction_id = truncate(jurisdiction_id, 300)
        state_code
        dedupe_key    = candidacy_key
        source        = truncate(source_name or 'bronze_elections_scraped', 100)
        source_url
        extras        = raw_row
        raw_row       = raw_row

    The grain is one row per candidacy; rows sharing a dedupe_key collapse
    (ON CONFLICT (dedupe_key)). The contest_id is recomputed with the identical
    c1_contest_id macro used by dim_candidate_contests, preserving the FK.
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

with_contest as (
    select
        *,
        {{ c1_contest_id('contest_key', "election_id || '|' || bronze_record_id::text") }} as contest_id
    from candidacies
),

with_candidacy_key as (
    select
        *,
        {{ c1_dedupe_key('election_id', 'contest_id', 'candidate_name', 'candidate_party') }} as candidacy_key
    from with_contest
),

with_candidacy_id as (
    select
        *,
        {{ c1_fit_id('ocd_id', 'coalesce(candidacy_key, bronze_record_id::text)') }} as candidacy_id
    from with_candidacy_key
),

deduped as (
    -- ON CONFLICT (dedupe_key) collapses rows sharing a candidacy_key; the
    -- upsert DO UPDATE means the LAST row wins -> keep the highest bronze id.
    -- Rows with a NULL dedupe_key conflict on id instead; they never share an
    -- id here (ocd_id is row-unique or falls back to the unique bronze id), so
    -- partitioning on coalesce(candidacy_key, candidacy_id) is faithful.
    {{ latest_per_natural_key('with_candidacy_id', 'coalesce(candidacy_key, candidacy_id)', 'bronze_record_id') }}
),

final as (
    select
        candidacy_id                                    as id,
        bronze_record_id                                as legacy_id,
        election_id,
        contest_id,
        coalesce(candidate_post, candidate_name, election_name, 'Contest') as contest_name,
        candidate_name                                  as person_name,
        cast(null as text)                              as person_id,
        candidate_party                                 as party,
        candidate_status                                as status,
        candidate_vote_count                            as vote_count,
        candidate_vote_percent                          as vote_percent,
        fit_jurisdiction_id                             as jurisdiction_id,
        state_code,
        candidacy_key                                   as dedupe_key,
        {{ c1_truncate("coalesce(source_name, 'bronze_elections_scraped')", c1_limit('source')) }} as source,
        source_url,
        coalesce(raw_row, '{}'::jsonb)                  as extras,
        coalesce(raw_row, '{}'::jsonb)                  as raw_row,
        current_timestamp                               as dbt_loaded_at
    from deduped
)

select * from final
