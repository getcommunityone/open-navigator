{{ config(materialized='view') }}

/*
    Staging: Ballotpedia ballot measures (1 row per measure_id).

    Reads the RAW landing table bronze.bronze_ballot_measures_ballotpedia, where
    ingestion.ballotpedia.measures now lands only the bronze keys (measure_id +
    scrape_batch_id) plus the full raw measure JSON object (raw_row, the measure
    merged with the snapshot envelope). This model reproduces the field derivation
    that used to live in the Python loader's _normalize_measure():
      - multi-alias coalescing for title / number / summary / type / votes / url
      - regex extraction of yes/no votes from a free-text outcome
        (_VOTE_PAIR_RE) when explicit yes_votes/no_votes are absent
      - regex extraction of a 4-digit election year (_YEAR_RE) from the explicit
        year/election_year else the title
      - pass/fail classification of the outcome text (_parse_passed)
    All done in SQL against raw_row JSONB. Four-CTE template:
    source -> renamed -> derived -> final. See dbt_project/CONVENTIONS.md.

    NOTE: state_code + ocd_division_id resolution and the 2025/2026 election-year
    filter are NOT done here — they live in int_ballotpedia__measure_resolved
    (resolution needs a state-name -> code crosswalk; see that model).

    Coalescing semantics: the Python loader used `a or b or c`, treating empty
    strings as falsy. nullif(<expr>, '') reproduces that so an empty string at an
    earlier alias falls through to the next.

    Regex notes (translating Python's `re` to Postgres; \m \M = word boundaries):
      - _PASSED_RE  \b(?:pass(?:ed|es|ing)?|approv(?:ed|es|al)|adopt(?:ed|s)?|yes)\b
      - _FAILED_RE  \b(?:fail(?:ed|s|ure)?|defeat(?:ed|s)?|reject(?:ed|s)?|no)\b
      - _YEAR_RE    \b(19|20)\d{2}\b
      - _VOTE_PAIR  (\d[\d,]*)\s*(?:yes|for|in favor)[^\d]{0,40}(\d[\d,]*)\s*(?:no|against)
*/

with

source as (
    select * from {{ source('bronze', 'bronze_ballot_measures_ballotpedia') }}
),

renamed as (
    select
        measure_id,
        raw_row,
        source_json_path,
        loaded_at                                                        as source_ingested_at,

        -- title: measure_title OR measure_name OR title
        coalesce(
            nullif(raw_row ->> 'measure_title', ''),
            nullif(raw_row ->> 'measure_name', ''),
            nullif(raw_row ->> 'title', '')
        )                                                                as measure_title_raw,

        -- outcome free text: measure_outcome OR status (drives votes + passed)
        coalesce(
            nullif(raw_row ->> 'measure_outcome', ''),
            nullif(raw_row ->> 'status', '')
        )                                                                as outcome,

        -- explicit year alias: election_year OR year
        coalesce(
            nullif(raw_row ->> 'election_year', ''),
            nullif(raw_row ->> 'year', '')
        )                                                                as year_explicit
    from source
),

derived as (
    select
        measure_id,
        source_json_path,
        source_ingested_at,

        left(measure_title_raw, 1000)                                    as measure_title,

        -- jurisdiction context (raw aliases; state-code resolution is downstream).
        left(nullif(raw_row ->> 'jurisdiction_id', ''), 255)             as jurisdiction_id,
        left(coalesce(
            nullif(raw_row ->> 'jurisdiction', ''),
            nullif(raw_row ->> 'jurisdiction_name', '')
        ), 255)                                                          as jurisdiction_name,
        left(nullif(raw_row ->> 'jurisdiction_type', ''), 100)           as jurisdiction_type,
        left(nullif(raw_row ->> 'scope', ''), 50)                        as scope,

        left(nullif(raw_row ->> 'election_date', ''), 50)                as election_date,

        -- election_year: 4-digit year from explicit alias first, else the title.
        left(coalesce(
            (regexp_match(year_explicit, '((?:19|20)\d{2})'))[1],
            (regexp_match(measure_title_raw, '((?:19|20)\d{2})'))[1]
        ), 4)                                                            as election_year,

        -- measure_number: measure_number OR number
        left(coalesce(
            nullif(raw_row ->> 'measure_number', ''),
            nullif(raw_row ->> 'number', '')
        ), 255)                                                          as measure_number,

        -- full_text / summary / type / subject aliases
        nullif(raw_row ->> 'full_text', '')                              as full_text,
        left(coalesce(
            nullif(raw_row ->> 'summary_text', ''),
            nullif(raw_row ->> 'measure_summary', '')
        ), 4000)                                                         as summary_text,
        left(coalesce(
            nullif(raw_row ->> 'measure_type', ''),
            nullif(raw_row ->> 'type', '')
        ), 255)                                                          as measure_type,
        left(nullif(raw_row ->> 'subject_areas', ''), 1000)              as subject_areas,

        -- yes_votes: explicit yes_votes (digits only), else group 1 of the
        -- yes/no outcome pair (digits only). NULL when neither is present.
        nullif(regexp_replace(
            coalesce(
                nullif(raw_row ->> 'yes_votes', ''),
                (regexp_match(
                    outcome,
                    '(\d[\d,]*)\s*(?:yes|for|in favor)[^\d]{0,40}(\d[\d,]*)\s*(?:no|against)',
                    'i'
                ))[1]
            ),
            '[^0-9]', '', 'g'
        ), '')::bigint                                                   as yes_votes,

        -- no_votes: explicit no_votes, else group 2 of the outcome pair.
        nullif(regexp_replace(
            coalesce(
                nullif(raw_row ->> 'no_votes', ''),
                (regexp_match(
                    outcome,
                    '(\d[\d,]*)\s*(?:yes|for|in favor)[^\d]{0,40}(\d[\d,]*)\s*(?:no|against)',
                    'i'
                ))[2]
            ),
            '[^0-9]', '', 'g'
        ), '')::bigint                                                   as no_votes,

        -- passed: explicit boolean alias wins; else classify the outcome text.
        --   pass-words AND NOT fail-words -> true
        --   fail-words AND NOT pass-words -> false
        --   else -> null (ambiguous, matching _parse_passed)
        case
            when lower(coalesce(raw_row ->> 'passed', '')) in ('true', 't', '1', 'yes') then true
            when lower(coalesce(raw_row ->> 'passed', '')) in ('false', 'f', '0', 'no') then false
            when outcome is null then null
            when outcome ~* '\m(?:pass(?:ed|es|ing)?|approv(?:ed|es|al)|adopt(?:ed|s)?|yes)\M'
                 and outcome !~* '\m(?:fail(?:ed|s|ure)?|defeat(?:ed|s)?|reject(?:ed|s)?|no)\M'
                then true
            when outcome ~* '\m(?:fail(?:ed|s|ure)?|defeat(?:ed|s)?|reject(?:ed|s)?|no)\M'
                 and outcome !~* '\m(?:pass(?:ed|es|ing)?|approv(?:ed|es|al)|adopt(?:ed|s)?|yes)\M'
                then false
            else null
        end                                                              as passed,

        -- urls
        left(nullif(raw_row ->> 'source_url', ''), 1000)                 as source_url,
        left(coalesce(
            nullif(raw_row ->> 'measure_url', ''),
            nullif(raw_row ->> 'measure_page_url', '')
        ), 1000)                                                         as measure_page_url,

        -- raw state aliases + raw ocd id preserved for downstream resolution
        coalesce(
            nullif(raw_row ->> 'state_code', ''),
            nullif(raw_row ->> 'state', '')
        )                                                                as state_raw,
        nullif(raw_row ->> 'ocd_division_id', '')                        as ocd_division_id_raw
    from renamed
),

final as (
    select
        measure_id,
        measure_title,
        jurisdiction_id,
        jurisdiction_name,
        jurisdiction_type,
        scope,
        election_date,
        election_year,
        measure_number,
        full_text,
        summary_text,
        measure_type,
        subject_areas,
        yes_votes,
        no_votes,
        passed,
        source_url,
        measure_page_url,
        state_raw,
        ocd_division_id_raw,
        source_json_path,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from derived
    -- Business rule: _normalize_measure dropped title-less rows. The loader now
    -- also drops them (no natural key), so this is belt-and-braces.
    where measure_title is not null
)

select * from final
