{{
  config(
    materialized='table',
    post_hook=[
      "CREATE INDEX IF NOT EXISTS mdm_organization_org_name_fts_idx ON {{ this }} USING gin (to_tsvector('english', org_name))",
      "CREATE INDEX IF NOT EXISTS mdm_organization_org_name_norm_idx ON {{ this }} (org_name_norm)",
      "CREATE INDEX IF NOT EXISTS mdm_organization_state_code_idx ON {{ this }} (state_code)"
    ]
  )
}}

/*
    Mart (MDM Layer 5): one golden record per resolved organization, with a
    canonical org_type. Canonical public org table.

    Indexes (post_hook): a GIN FTS index on org_name for org search; a btree on
    org_name_norm that both orders org browse/name-sort results (index scan instead
    of a 3.6M-row sort) and powers the person-search anti-join keeping
    officer-derived org names (e.g. CareQuest Institute) out of People results; and
    a btree on state_code so a state-scoped name search BitmapAnds the state index
    with the FTS index instead of scanning the full match set
    (see api/routes/search_postgres.py search_organizations_pg / search_persons_pg).

    Survivorship has two tracks:
      - IDENTITY / LOCATION (city, geocode, ein, website): the most-complete,
        most-trusted occurrence wins (has EIN, has city, has geocode; nonprofit
        registry > facility > AI). NCCS is preferred here for its geocoding.
      - NAME: chosen by *authority for the legal name*, then recency. Government &
        schools own their own names; for nonprofits IRS BMF (the monthly legal-name
        registry) outranks NCCS Core (a research extract that lags and keeps the
        pre-rebrand name even on a recent filing year). This is why CareQuest
        Institute (EIN 384016550) now resolves to its current name instead of the
        stale NCCS "Catalyst Institute Inc" — both report 2024, so recency alone
        ties and authority breaks it.

    Name changes are preserved: former_names + name_history (each distinct name
    with the year span and sources it was seen under), current_name_since_year,
    and has_name_change. NOTE: years come from each source's as_of_year (NCCS
    org_year_last, IRS tax_period year, etc.), so they date when we *observed* a
    name, not the legal change date — they bound the change, not pinpoint it.

    org_type is the most common NON-'other' type across the cluster (falls back to
    the golden record's type). first_seen_year / last_seen_year give the date span.

    Serve org search/browse from here; tie to person/address via the org bridges,
    and to the governing jurisdiction via mdm_bridge_org_jurisdiction.
*/

with clustered as (
    select * from {{ ref('int_organizations__clustered') }}
),

-- Identity/location golden row: most-complete, most-trusted (NCCS-preferred).
ranked as (
    select
        *,
        row_number() over (
            partition by master_org_id
            order by
                (ein is not null) desc,
                (city_norm is not null) desc,
                (lat is not null) desc,
                case source_system
                    when 'bronze_organizations_nonprofits_nccs' then 1
                    when 'bronze_locations' then 2
                    when 'bronze_organizations_from_ai' then 3
                    when 'bronze_organizations_nonprofits_irs' then 4
                    else 5
                end,
                org_uid
        ) as rn
    from clustered
),

golden as (
    select * from ranked where rn = 1
),

-- most common non-'other' type per cluster
type_vote as (
    select distinct on (master_org_id)
        master_org_id,
        org_type as voted_type
    from clustered
    where org_type <> 'other'
    group by master_org_id, org_type
    order by master_org_id, count(*) desc
),

evidence as (
    select
        master_org_id,
        count(*)                       as n_occurrences,
        count(distinct source_system)  as n_sources,
        min(as_of_year)                as first_seen_year,
        max(as_of_year)                as last_seen_year
    from clustered
    group by 1
),

-- ── Name survivorship & history ────────────────────────────────────────────
-- Authority rank for an org's NAME (lower = more authoritative). Distinct from
-- the identity/location ranking above, which is geocoding-driven.
name_occurrences as (
    select
        master_org_id,
        org_name,
        org_name_norm,
        as_of_year,
        source_system,
        case source_system
            when 'bronze_jurisdictions' then 0               -- canonical gov name
            when 'bronze_schools_nces' then 0                -- canonical school name
            when 'bronze_organizations_nonprofits_irs' then 1  -- IRS = legal-name registry
            when 'bronze_organizations_nonprofits_nccs' then 2 -- NCCS lags IRS on name
            when 'bronze_locations' then 3
            when 'bronze_organizations_from_ai' then 4
            else 5
        end as name_rank
    from clustered
    where org_name_norm is not null
),

-- One row per distinct name (by norm) within a cluster: when it was seen, from
-- where, and the best display spelling (from the most authoritative/recent source).
name_variants as (
    select
        master_org_id,
        org_name_norm,
        min(name_rank)   as best_rank,
        min(as_of_year)  as first_year,
        max(as_of_year)  as last_year,
        (array_agg(org_name order by name_rank asc, as_of_year desc nulls last))[1] as display_name,
        array_agg(distinct source_system order by source_system) as sources
    from name_occurrences
    group by master_org_id, org_name_norm
),

-- Current name = most authoritative variant, ties broken by recency.
current_name as (
    select distinct on (master_org_id)
        master_org_id,
        org_name_norm   as current_norm,
        display_name    as current_name_raw,
        first_year      as current_name_since_year
    from name_variants
    order by master_org_id, best_rank asc, last_year desc nulls last, first_year desc nulls last
),

name_history as (
    select
        master_org_id,
        count(*) as distinct_name_count,
        jsonb_agg(
            jsonb_build_object(
                'name', display_name,
                'name_norm', org_name_norm,
                -- calendar years as JSON strings, per the project convention
                'first_year', first_year::text,
                'last_year', last_year::text,
                'sources', to_jsonb(sources)
            )
            order by last_year desc nulls last, first_year desc nulls last
        ) as name_history
    from name_variants
    group by master_org_id
),

former_names as (
    select
        v.master_org_id,
        jsonb_agg(v.display_name order by v.last_year desc nulls last, v.first_year desc nulls last) as former_names
    from name_variants v
    join current_name c on c.master_org_id = v.master_org_id
    where v.org_name_norm <> c.current_norm
    group by v.master_org_id
)

select
    g.master_org_id,
    {{ display_org_name('coalesce(cn.current_name_raw, g.org_name)') }}  as org_name,
    coalesce(cn.current_norm, g.org_name_norm)                          as org_name_norm,
    coalesce(v.voted_type, g.org_type)  as org_type,
    g.org_subtype,
    g.ein,
    g.city_norm,
    g.state_code,
    g.zip5,
    g.lat,
    g.lon,
    g.website,
    e.n_occurrences,
    e.n_sources,
    e.first_seen_year,
    e.last_seen_year,
    coalesce(fn.former_names, '[]'::jsonb)              as former_names,
    coalesce(nh.name_history, '[]'::jsonb)              as name_history,
    cn.current_name_since_year,
    (coalesce(nh.distinct_name_count, 0) > 1)           as has_name_change
from golden g
join evidence e using (master_org_id)
left join type_vote v using (master_org_id)
left join current_name cn using (master_org_id)
left join name_history nh using (master_org_id)
left join former_names fn using (master_org_id)
