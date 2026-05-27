{{ config(materialized='table') }}

/*
    Intermediate: Power BI ballot measures with resolved state / jurisdiction / OCD.

    Replaces the layering inversion the loader used to do: ballot_measures.py
    QUERIED intermediate.int_jurisdictions from Python (load_state_jurisdiction_index
    / resolve_state_jurisdiction) to stamp state_code / jurisdiction_id / ocd_id
    onto each row. That is a dbt model, so reading it from the Python loader was a
    layering inversion. It is now a proper dbt JOIN: this model refs
    int_jurisdictions (state rows) and resolves the same three columns here.

    Resolution mirrors resolve_state_jurisdiction():
      1) match on a clean 2-letter state_code from the CSV, else
      2) match on the state name / jurisdiction name (case-insensitive).
    ocd_id mirrors _ocd_id_for_state(): prefer the Open States id when it is an
    ocd-division/ id, else synthesize ocd-division/country:us/state:<lower(code)>.

    Four-CTE template: source -> states -> resolved -> final.
    See dbt_project/CONVENTIONS.md.

    NOTE (flagged): int_jurisdictions includes state-government rows (its `states`
    CTE feeds the union with jurisdiction_type = 'state'), even though its
    _intermediate.yml accepted_values test omits 'state'. The Python loader filtered
    `WHERE jurisdiction_type = 'state'`, so we do the same here. It has no `ocd_id`
    column; we synthesize it from open_states_jurisdiction_id / state_code exactly
    as the Python helper did.
*/

with

source as (
    select * from {{ ref('stg_powerbi__ballot_measure') }}
),

states as (
    -- State-government rows from the canonical jurisdictions model. One row per state.
    select
        upper(trim(state_code))                          as state_code,
        nullif(trim(state), '')                          as state_name,
        nullif(trim(name), '')                           as jurisdiction_display_name,
        jurisdiction_id,
        open_states_jurisdiction_id
    from {{ ref('int_jurisdictions') }}
    where jurisdiction_type = 'state'
      and state_code is not null
      and btrim(state_code) <> ''
),

resolved as (
    -- Resolve each measure against the state index. The join prefers a clean
    -- 2-letter state_code; otherwise it falls back to a name match (state name
    -- or jurisdiction name), mirroring resolve_state_jurisdiction().
    select
        m.bronze_id,
        m.scrape_batch_id,
        m.measure_id,
        m.measure_title,
        m.measure_summary,
        m.measure_type,
        -- Keep the CSV state name as the display state, falling back to the
        -- resolved canonical state name (matches the Python `state_label`).
        coalesce(m.state, j.state_name)                  as state,
        m.jurisdiction_name,
        m.election_date,
        m.election_year,
        m.outcome,
        m.yes_count,
        m.no_count,
        m.yes_percent,
        m.source_url,
        m.source_csv_path,
        m.scraped_at,

        -- Resolved state_code: the join's code when matched, else the CSV's own
        -- 2-letter code (which may be NULL).
        coalesce(j.state_code, m.state_code)             as state_code,
        j.jurisdiction_id,

        -- ocd_id: prefer an Open States ocd-division/ id, else synthesize from
        -- the resolved code (or the CSV code as a fallback) — _ocd_id_for_state().
        case
            when j.open_states_jurisdiction_id like 'ocd-division/%'
                then j.open_states_jurisdiction_id
            when coalesce(j.state_code, m.state_code) is not null
                then 'ocd-division/country:us/state:' || lower(coalesce(j.state_code, m.state_code))
        end                                              as ocd_id
    from source m
    left join states j
        on (
            -- 1) clean 2-letter code match
            (m.state_code is not null and j.state_code = m.state_code)
            -- 2) name match (state name or jurisdiction display name)
            or (m.state_code is null and lower(j.state_name) = lower(m.state))
            or (m.state_code is null and lower(j.jurisdiction_display_name) = lower(m.state))
        )
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
        jurisdiction_id,
        ocd_id,
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
    from resolved
)

select * from final
