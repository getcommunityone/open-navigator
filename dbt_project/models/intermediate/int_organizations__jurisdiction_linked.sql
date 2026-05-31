{{ config(materialized='table') }}

/*
    Intermediate (MDM): bind each clustered organization occurrence to its parent
    governing jurisdiction (the OCD `jurisdiction_id` from the `jurisdictions`
    mart) so schools / cities / parks / sheriffs / police / churches roll up to
    the municipality / county / township that governs them.

    Match strategy, most-trusted first (recorded in jurisdiction_match_method):
      1. self          — the org IS a jurisdiction (source_system='bronze_jurisdictions');
                         parent_jurisdiction_id = source_pk (its own jurisdiction_id).
      2. municipality  — org.city_norm matches a municipality in the same state.
      3. township      — org.city_norm matches a township in the same state.
      4. county        — org.city_norm matches a county in the same state.
      5. unmatched     — no (state, name) match (parent_jurisdiction_id is NULL).

    Name matching reuses normalize_jurisdiction_label_for_match() on BOTH sides so
    it is consistent with the rest of the repo. This replaces the bespoke Python
    OCD lookup (_normalize_place_name / build_ocd_lookup) in
    scripts/discovery/fold_organization_location_into_c1.py — SQL logic lives in
    dbt, per the data-pipeline standards.

    Grain: one row per source org occurrence (1:1 with int_organizations__clustered),
    with parent_jurisdiction_id + jurisdiction_match_method appended.
*/

with orgs as (
    select * from {{ ref('int_organizations__clustered') }}
),

jur as (
    select
        jurisdiction_id,
        state_code,
        jurisdiction_type,
        {{ normalize_jurisdiction_label_for_match('display_name') }}  as name_key,
        coalesce(population, 0)                                       as population
    from {{ ref('jurisdictions') }}
    where jurisdiction_type in ('municipality', 'township', 'county')
      and state_code is not null
),

-- candidate (state, normalized-name) matches for non-jurisdiction orgs; rank so
-- a municipality wins over a township over a county, then by population.
candidates as (
    select
        o.org_uid,
        j.jurisdiction_id,
        j.jurisdiction_type,
        row_number() over (
            partition by o.org_uid
            order by
                case j.jurisdiction_type
                    when 'municipality' then 1
                    when 'township'     then 2
                    when 'county'       then 3
                    else 4
                end,
                j.population desc,
                j.jurisdiction_id
        ) as rn
    from orgs o
    join jur j
        on j.state_code = o.state_code
       and j.name_key = {{ normalize_jurisdiction_label_for_match('o.city_norm') }}
    where o.source_system <> 'bronze_jurisdictions'
      and o.city_norm is not null
      and o.state_code is not null
),

best as (
    select org_uid, jurisdiction_id, jurisdiction_type
    from candidates
    where rn = 1
)

select
    o.*,
    case
        when o.source_system = 'bronze_jurisdictions' then o.source_pk
        else b.jurisdiction_id
    end                                                  as parent_jurisdiction_id,
    case
        when o.source_system = 'bronze_jurisdictions' then 'self'
        when b.jurisdiction_type is not null           then b.jurisdiction_type
        else 'unmatched'
    end                                                  as jurisdiction_match_method
from orgs o
left join best b using (org_uid)
