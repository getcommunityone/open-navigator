{{ config(materialized='view') }}

/*
    Staging: Power BI ballot measures (1 row per bronze raw row).

    Reads the RAW landing table bronze.bronze_ballot_measures_powerbi, where
    ingestion.powerbi.ballot_measures now lands only (id, scrape_batch_id,
    raw_row JSONB, source_csv_path, ...). This model reproduces the derivation
    that used to live in the Python loader:
      - _build_column_map / COLUMN_ALIASES heuristic header → bronze-column
        mapping (lowercase + strip non-alphanumerics, first-alias-wins), and
      - the _coerce_* parsing (int / float-with-%-strip / 4-digit year / date).
    All done in SQL against raw_row JSONB. Four-CTE template:
    source -> renamed -> derived -> final. See dbt_project/CONVENTIONS.md.

    The state/jurisdiction/OCD resolution that the loader used to do by QUERYING
    intermediate.int_jurisdictions from Python (a layering inversion) is NOT done
    here — it becomes a proper dbt JOIN downstream in
    int_powerbi__measure_with_jurisdiction.

    Header normalization: the Python loader matched aliases after lowercasing and
    stripping every non-alphanumeric char (so "Measure Title", "measure_title",
    and "MeasureTitle" all collapse). We reproduce that with regexp_replace on
    each raw_row key, flatten to (norm_key, value) pairs, then pick the first
    matching alias per bronze column.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_ballot_measures_powerbi') }}
),

renamed as (
    -- Flatten raw_row into one (norm_key, value) row per CSV column, where
    -- norm_key = lower(strip-non-alphanumeric(original header)) — mirrors _norm().
    select
        s.id                                                          as bronze_id,
        s.scrape_batch_id,
        s.source_csv_path,
        s.scraped_at,
        regexp_replace(lower(kv.key), '[^a-z0-9]+', '', 'g')          as norm_key,
        nullif(kv.value, '')                                          as value
    from source s
    cross join lateral jsonb_each_text(s.raw_row) as kv(key, value)
),

aliased as (
    -- First-alias-wins per bronze column. coalesce(...) over per-alias max()
    -- reproduces COLUMN_ALIASES order: the earliest alias present in the row
    -- supplies the value (later aliases only fill when earlier ones are null).
    select
        bronze_id,
        scrape_batch_id,
        source_csv_path,
        scraped_at,

        coalesce(
            max(value) filter (where norm_key = 'measureid'),
            max(value) filter (where norm_key = 'id'),
            max(value) filter (where norm_key = 'ballotmeasureid'),
            max(value) filter (where norm_key = 'ocdid'),
            max(value) filter (where norm_key = 'g10')
        )                                                             as measure_id,

        coalesce(
            max(value) filter (where norm_key = 'measuretitle'),
            max(value) filter (where norm_key = 'title'),
            max(value) filter (where norm_key = 'measurename'),
            max(value) filter (where norm_key = 'name'),
            max(value) filter (where norm_key = 'ballotmeasure'),
            max(value) filter (where norm_key = 'measure'),
            max(value) filter (where norm_key = 'g2')
        )                                                             as measure_title,

        coalesce(
            max(value) filter (where norm_key = 'measuresummary'),
            max(value) filter (where norm_key = 'summary'),
            max(value) filter (where norm_key = 'description'),
            max(value) filter (where norm_key = 'ballotsummary'),
            max(value) filter (where norm_key = 'g3')
        )                                                             as measure_summary,

        coalesce(
            max(value) filter (where norm_key = 'measuretype'),
            max(value) filter (where norm_key = 'type'),
            max(value) filter (where norm_key = 'classification'),
            max(value) filter (where norm_key = 'ballottype'),
            max(value) filter (where norm_key = 'irtypedefinition'),
            max(value) filter (where norm_key = 'g4'),
            max(value) filter (where norm_key = 'ballottypecombined'),
            max(value) filter (where norm_key = 'g9')
        )                                                             as measure_type,

        coalesce(
            max(value) filter (where norm_key = 'statecode'),
            max(value) filter (where norm_key = 'stateabbreviation'),
            max(value) filter (where norm_key = 'stateabbr'),
            max(value) filter (where norm_key = 'st')
        )                                                             as state_code_raw,

        coalesce(
            max(value) filter (where norm_key = 'state'),
            max(value) filter (where norm_key = 'statename'),
            max(value) filter (where norm_key = 'statename1'),
            max(value) filter (where norm_key = 'g0')
        )                                                             as state,

        coalesce(
            max(value) filter (where norm_key = 'jurisdiction'),
            max(value) filter (where norm_key = 'jurisdictionname'),
            max(value) filter (where norm_key = 'locality'),
            max(value) filter (where norm_key = 'city'),
            max(value) filter (where norm_key = 'county')
        )                                                             as jurisdiction_name,

        coalesce(
            max(value) filter (where norm_key = 'electiondate'),
            max(value) filter (where norm_key = 'date'),
            max(value) filter (where norm_key = 'votedate')
        )                                                             as election_date_raw,

        coalesce(
            max(value) filter (where norm_key = 'electionyear'),
            max(value) filter (where norm_key = 'year'),
            max(value) filter (where norm_key = 'g1')
        )                                                             as election_year_raw,

        coalesce(
            max(value) filter (where norm_key = 'outcome'),
            max(value) filter (where norm_key = 'result'),
            max(value) filter (where norm_key = 'status'),
            max(value) filter (where norm_key = 'passfail'),
            max(value) filter (where norm_key = 'passfailcalculation'),
            max(value) filter (where norm_key = 'g7')
        )                                                             as outcome,

        coalesce(
            max(value) filter (where norm_key = 'yescount'),
            max(value) filter (where norm_key = 'yesvotes'),
            max(value) filter (where norm_key = 'votesyes'),
            max(value) filter (where norm_key = 'yes')
        )                                                             as yes_count_raw,

        coalesce(
            max(value) filter (where norm_key = 'nocount'),
            max(value) filter (where norm_key = 'novotes'),
            max(value) filter (where norm_key = 'votesno'),
            max(value) filter (where norm_key = 'no')
        )                                                             as no_count_raw,

        coalesce(
            max(value) filter (where norm_key = 'yespercent'),
            max(value) filter (where norm_key = 'yespct'),
            max(value) filter (where norm_key = 'percentyes'),
            max(value) filter (where norm_key = 'approval'),
            max(value) filter (where norm_key = 'percentagevote'),
            max(value) filter (where norm_key = 'g8')
        )                                                             as yes_percent_raw,

        coalesce(
            max(value) filter (where norm_key = 'sourceurl'),
            max(value) filter (where norm_key = 'url'),
            max(value) filter (where norm_key = 'link'),
            max(value) filter (where norm_key = 'ballotpediaurl')
        )                                                             as source_url

    from renamed
    group by bronze_id, scrape_batch_id, source_csv_path, scraped_at
),

derived as (
    -- Reproduce the _coerce_* parsing in SQL.
    select
        bronze_id,
        scrape_batch_id,
        source_csv_path,
        scraped_at,
        nullif(trim(measure_id), '')                                 as measure_id,
        nullif(trim(measure_title), '')                              as measure_title,
        nullif(trim(measure_summary), '')                            as measure_summary,
        nullif(trim(measure_type), '')                               as measure_type,

        -- state_code: _coerce_str(..., maxlen=2) on the raw 2-letter alias.
        -- Only kept when it is a clean 2-letter code; otherwise NULL and the
        -- downstream int model resolves it from the state name via int_jurisdictions.
        case
            when upper(left(trim(state_code_raw), 2)) ~ '^[A-Z]{2}$'
                then upper(left(trim(state_code_raw), 2))
        end                                                          as state_code,

        nullif(trim(state), '')                                      as state,
        nullif(trim(jurisdiction_name), '')                          as jurisdiction_name,

        -- _coerce_date: parse to a DATE, NULL on failure. The Python helper used
        -- pd.to_datetime(errors="raise") wrapped in try/except (NULL on failure).
        -- Postgres ::date raises on bad input mid-build, so we only attempt the
        -- cast for date-SHAPED strings: ISO yyyy-mm-dd / yyyy/mm/dd or US m/d/yyyy.
        case
            when trim(election_date_raw) ~ '^\d{4}[-/]\d{1,2}[-/]\d{1,2}([ T].*)?$'
                then left(trim(election_date_raw), 10)::date
            when trim(election_date_raw) ~ '^\d{1,2}[-/]\d{1,2}[-/]\d{4}$'
                then trim(election_date_raw)::date
        end                                                          as election_date,

        -- _coerce_year: first 4-digit 19xx/20xx token in the string, else fall
        -- back to _coerce_int and accept it only if 1900..2100.
        coalesce(
            (regexp_match(coalesce(election_year_raw, ''), '((?:19|20)\d{2})'))[1],
            case
                when (regexp_replace(coalesce(election_year_raw, ''), '[^0-9.]', '', 'g')) ~ '^[0-9]+(\.[0-9]+)?$'
                     and trunc((regexp_replace(coalesce(election_year_raw, ''), '[^0-9.]', '', 'g'))::numeric) between 1900 and 2100
                    then trunc((regexp_replace(coalesce(election_year_raw, ''), '[^0-9.]', '', 'g'))::numeric)::int::varchar
            end
        )                                                            as election_year,

        nullif(trim(outcome), '')                                    as outcome,

        -- _coerce_int: strip commas, int(float(s)).
        case
            when regexp_replace(coalesce(yes_count_raw, ''), '[^0-9.\-]', '', 'g') ~ '^-?[0-9]+(\.[0-9]+)?$'
                then trunc((regexp_replace(yes_count_raw, '[^0-9.\-]', '', 'g'))::numeric)::bigint
        end                                                          as yes_count,
        case
            when regexp_replace(coalesce(no_count_raw, ''), '[^0-9.\-]', '', 'g') ~ '^-?[0-9]+(\.[0-9]+)?$'
                then trunc((regexp_replace(no_count_raw, '[^0-9.\-]', '', 'g'))::numeric)::bigint
        end                                                          as no_count,

        -- _coerce_float: strip commas and %, float(s).
        case
            when regexp_replace(coalesce(yes_percent_raw, ''), '[^0-9.\-]', '', 'g') ~ '^-?[0-9]+(\.[0-9]+)?$'
                then (regexp_replace(yes_percent_raw, '[^0-9.\-]', '', 'g'))::double precision
        end                                                          as yes_percent,

        nullif(trim(source_url), '')                                 as source_url
    from aliased
),

final as (
    select
        bronze_id,
        scrape_batch_id,
        measure_id,
        measure_title,
        measure_summary,
        measure_type,
        state_code,
        state,
        jurisdiction_name,
        election_date,
        election_year,
        outcome,
        yes_count,
        no_count,
        yes_percent,
        source_url,
        source_csv_path,
        scraped_at,
        current_timestamp as dbt_loaded_at
    from derived
)

select * from final
