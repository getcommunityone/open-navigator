{{ config(materialized='table') }}

/*
    Intermediate: Ballotpedia measures with state_code + ocd_division_id resolved,
    filtered to the in-scope election years.

    Replaces the Python loader's _state_code_from_name / _resolve_ocd_division_id
    and the 2025/2026 election-year filter (see dbt_project/CONVENTIONS.md). Reads
    stg_ballotpedia__measure (which already did the JSONB field parsing).

    What moved to SQL here:
      - state_code: a raw 2-letter alpha code is upper-cased and used directly;
        otherwise a state NAME is resolved to its 2-letter code via the inline
        `state_ref` crosswalk (same VALUES table used by int_jurisdictions.sql —
        the de-facto state name/code/FIPS lookup in this project today).
      - ocd_division_id: an explicit ocd_division_id from the source wins; else
        a STATE-scoped division id (ocd-division/country:us/state:<code>) is
        built from the resolved state_code. This reproduces the loader's
        state-scope branch and its `state_code`-only fallback.
      - election-year filter: the loader hard-filtered to ELECTION_YEARS
        (2025, 2026); that is now the WHERE at the bottom of this model.

    ============================ MISSING LOOKUP (HUMAN TODO) ============================
    The legacy loader could resolve SUB-STATE measures (scope != 'state', a named
    county/city jurisdiction) to a precise OCD division id via the Python helper
    `scripts.datasources.jurisdiction_pilot.load_ocd_jurisdictions.find_ocd_match`
    (fuzzy name+state+type match against the OCD jurisdiction roster). There is NO
    dbt seed or model that provides that OCD jurisdiction crosswalk yet, so this
    model does NOT fabricate one. For sub-state rows with no explicit
    ocd_division_id we fall back to the STATE division id (matching the loader's
    final `if state_code` fallback) and surface the gap via `ocd_match_pending`.

    To close the gap, a human must add an OCD jurisdiction crosswalk that maps
    (jurisdiction_name, state_code, jurisdiction_type) -> ocd-division id, e.g.:
      - a dbt seed dbt_project/seeds/ocd_jurisdictions.csv, OR
      - expose the OCD division ids already implied by int_jurisdictions
        (it parses ocd division/jurisdiction ids for Open States matches), and
        join here on (state_code, normalized jurisdiction_name, mapped type).
    Then replace the `ocd_division_id` fallback below with that join (preferring
    the precise sub-state id, falling back to the state id only when unmatched).
    ====================================================================================
*/

with

source as (
    select * from {{ ref('stg_ballotpedia__measure') }}
),

state_ref as (
    -- Same crosswalk as int_jurisdictions.sql (the project's de-facto state
    -- name/code/FIPS lookup). state_code is the 2-letter USPS code.
    select * from (values
        ('AL', 'Alabama'),
        ('AK', 'Alaska'),
        ('AZ', 'Arizona'),
        ('AR', 'Arkansas'),
        ('CA', 'California'),
        ('CO', 'Colorado'),
        ('CT', 'Connecticut'),
        ('DE', 'Delaware'),
        ('DC', 'District of Columbia'),
        ('FL', 'Florida'),
        ('GA', 'Georgia'),
        ('HI', 'Hawaii'),
        ('ID', 'Idaho'),
        ('IL', 'Illinois'),
        ('IN', 'Indiana'),
        ('IA', 'Iowa'),
        ('KS', 'Kansas'),
        ('KY', 'Kentucky'),
        ('LA', 'Louisiana'),
        ('ME', 'Maine'),
        ('MD', 'Maryland'),
        ('MA', 'Massachusetts'),
        ('MI', 'Michigan'),
        ('MN', 'Minnesota'),
        ('MS', 'Mississippi'),
        ('MO', 'Missouri'),
        ('MT', 'Montana'),
        ('NE', 'Nebraska'),
        ('NV', 'Nevada'),
        ('NH', 'New Hampshire'),
        ('NJ', 'New Jersey'),
        ('NM', 'New Mexico'),
        ('NY', 'New York'),
        ('NC', 'North Carolina'),
        ('ND', 'North Dakota'),
        ('OH', 'Ohio'),
        ('OK', 'Oklahoma'),
        ('OR', 'Oregon'),
        ('PA', 'Pennsylvania'),
        ('RI', 'Rhode Island'),
        ('SC', 'South Carolina'),
        ('SD', 'South Dakota'),
        ('TN', 'Tennessee'),
        ('TX', 'Texas'),
        ('UT', 'Utah'),
        ('VT', 'Vermont'),
        ('VA', 'Virginia'),
        ('WA', 'Washington'),
        ('WV', 'West Virginia'),
        ('WI', 'Wisconsin'),
        ('WY', 'Wyoming'),
        ('AS', 'American Samoa'),
        ('GU', 'Guam'),
        ('MP', 'Northern Mariana Islands'),
        ('PR', 'Puerto Rico'),
        ('VI', 'U.S. Virgin Islands')
    ) as t(state_code, state_name)
),

resolved as (
    select
        s.*,
        -- state_code: a 2-letter alpha raw value is used directly (upper-cased);
        -- otherwise resolve a state NAME via the crosswalk (case-insensitive).
        case
            when s.state_raw ~ '^[A-Za-z]{2}$' then upper(s.state_raw)
            else sr.state_code
        end                                                              as state_code
    from source s
    left join state_ref sr
        on lower(s.state_raw) = lower(sr.state_name)
),

with_ocd as (
    select
        r.*,
        -- ocd_division_id: explicit source value wins; else build the STATE
        -- division id from the resolved state_code. (Sub-state precise ids are
        -- the MISSING LOOKUP flagged above.)
        coalesce(
            r.ocd_division_id_raw,
            case
                when r.state_code is not null
                    then 'ocd-division/country:us/state:' || lower(r.state_code)
            end
        )                                                                as ocd_division_id,
        -- TRUE when this is a sub-state row that could only fall back to the
        -- state division id (i.e. the precise OCD match the human must add).
        (
            r.ocd_division_id_raw is null
            and coalesce(lower(r.scope), '') <> 'state'
            and r.jurisdiction_name is not null
        )                                                                as ocd_match_pending
    from resolved r
),

final as (
    select
        measure_id,
        ocd_division_id,
        state_code,
        ocd_match_pending,
        jurisdiction_id,
        jurisdiction_name,
        jurisdiction_type,
        scope,
        election_date,
        election_year,
        measure_number,
        measure_title,
        full_text,
        summary_text,
        measure_type,
        subject_areas,
        yes_votes,
        no_votes,
        passed,
        source_url,
        measure_page_url,
        source_json_path,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from with_ocd
    -- Business rule: the loader hard-filtered to ELECTION_YEARS = (2025, 2026).
    where election_year in ('2025', '2026')
)

select * from final
