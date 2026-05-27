{{ config(materialized='table') }}

/*
    Intermediate: jurisdiction_crosswalk (MDM).

    Reproduces the cross-reference build that
    scripts/datasources/master_data/create_jurisdiction_master.py assembled by
    running ~12 matching strategies as sequential INSERTs into one
    jurisdiction_crosswalk table. Here each strategy is ONE CTE; they are then
    union-all'd. Output grain: one row per (source-pair, match_method) — the same
    grain as the Python INSERTs (it did NOT collapse duplicates; the master
    consolidation step downstream does the GROUP BY).

    Per CONVENTIONS.md §3.1 each strategy is its own CTE (one responsibility, at
    most one logical join family). Strategies that the Python ran with a
    "WHERE NOT EXISTS (already matched ...)" guard reference the EARLIER CTEs so
    the ordering / straggler semantics are preserved.

    Confidence scores, match_method labels, and join predicates are copied
    verbatim from the Python SQL.

    ------------------------------------------------------------------------
    STRATEGY MAP (12 strategies -> SQL). See _schema for the full deferred list.
      1.  nces_id_exact            -> CTE x_nces             (TRANSLATED)
      2.  geoid_exact              -> CTE x_geoid            (TRANSLATED)
      3.  name_normalized          -> CTE x_name_normalized  (TRANSLATED; depends on geoid)
      4.  phone_exact              -> DEFERRED (public.jurisdiction has no phone column)
      5.  city_state_normalized    -> CTE x_city_state       (TRANSLATED)
      6a. city_geographic          -> CTE x_city_geo_wiki     (TRANSLATED)
      6b. city_geographic_details  -> CTE x_city_geo_details  (TRANSLATED)
      7.  proximity_1mile          -> CTE x_proximity         (TRANSLATED; depends on prior wiki matches)
      8.  domain_exact             -> CTE x_domain_exact      (TRANSLATED; from domain_registry)
      9.  domain_orgloc_wikidata   -> CTE x_domain_ol_wiki    (TRANSLATED)
      10. domain_orgloc_details    -> CTE x_domain_ol_details (TRANSLATED; website_url path)
      11. name_state_type          -> CTE x_name_state_type   (TRANSLATED)
      12. fuzzy_name               -> DEFERRED (Python SequenceMatcher; also disabled in main())
    ------------------------------------------------------------------------
*/

with

org as (
    select * from {{ ref('stg_mdm__organization_location') }}
),

wiki as (
    select * from {{ ref('stg_mdm__jurisdictions_wikidata') }}
),

jur as (
    select * from {{ ref('stg_mdm__jurisdiction') }}
),

registry as (
    select * from {{ ref('int_master__domain_registry') }}
),

-- 1. nces_id_exact: org_location school districts LEFT JOIN wikidata on NCES id.
x_nces as (
    select
        org.org_location_id,
        wiki.wikidata_id,
        null::integer                       as jurisdiction_ref_id,
        null::integer                       as details_search_id,
        org.source_id                       as nces_id,
        null::varchar                       as fips_code,
        null::varchar                       as geoid,
        org.org_name                        as primary_name,
        org.state_code,
        null::varchar                       as state_name,
        null::varchar                       as county,
        org.city,
        'school_district'                   as jurisdiction_type,
        org.organization_type,
        'nces_id_exact'                     as match_method,
        1.0::decimal(3, 2)                  as match_confidence
    from org
    left join wiki
        on org.source_id = wiki.nces_id
        and org.state_code = wiki.state_code
    where org.organization_type = 'school_district'
      and org.source_id is not null
),

-- 2. geoid_exact: jurisdiction LEFT JOIN wikidata on GEOID + state.
x_geoid as (
    select
        null::integer                       as org_location_id,
        wiki.wikidata_id,
        jur.jurisdiction_id                 as jurisdiction_ref_id,
        null::integer                       as details_search_id,
        null::varchar                       as nces_id,
        null::varchar                       as fips_code,
        jur.geoid,
        jur.jurisdiction_name               as primary_name,
        jur.state_code,
        jur.state_name,
        jur.county,
        null::varchar                       as city,
        jur.jurisdiction_type,
        null::varchar                       as organization_type,
        'geoid_exact'                       as match_method,
        1.0::decimal(3, 2)                  as match_confidence
    from jur
    left join wiki
        on jur.geoid = wiki.geoid
        and jur.state_code = wiki.state_code
    where jur.geoid is not null
),

-- 3. name_normalized: jurisdiction JOIN wikidata on suffix-stripped name, same
--    state + type. Python guarded with NOT EXISTS (already matched by geoid):
--    skip (jurisdiction, wikidata) pairs already present in x_geoid.
x_name_normalized as (
    select
        null::integer                       as org_location_id,
        wiki.wikidata_id,
        jur.jurisdiction_id                 as jurisdiction_ref_id,
        null::integer                       as details_search_id,
        null::varchar                       as nces_id,
        null::varchar                       as fips_code,
        null::varchar                       as geoid,
        wiki.jurisdiction_name              as primary_name,
        jur.state_code,
        null::varchar                       as state_name,
        null::varchar                       as county,
        null::varchar                       as city,
        jur.jurisdiction_type,
        null::varchar                       as organization_type,
        'name_normalized'                   as match_method,
        0.90::decimal(3, 2)                 as match_confidence
    from jur
    join wiki
        on regexp_replace(
               lower(trim(jur.jurisdiction_name)),
               ' (historic district|cdp|town|city|village|borough|municipality)$', '', 'i'
           )
           = regexp_replace(
               lower(trim(wiki.jurisdiction_name)),
               ' (historic district|cdp|town|city|village|borough|municipality)$', '', 'i'
           )
        and jur.state_code = wiki.state_code
        and jur.jurisdiction_type = wiki.jurisdiction_type
    where not exists (
        select 1 from x_geoid g
        where g.jurisdiction_ref_id = jur.jurisdiction_id
          and g.wikidata_id = wiki.wikidata_id
    )
),

-- 5. city_state_normalized: wikidata JOIN jurisdiction, same state + type,
--    name match after stripping Town/City suffix OR after stripping non-letters.
x_city_state as (
    select
        null::integer                       as org_location_id,
        wiki.wikidata_id,
        null::integer                       as jurisdiction_ref_id,
        jur.jurisdiction_id                 as details_search_id,
        null::varchar                       as nces_id,
        null::varchar                       as fips_code,
        null::varchar                       as geoid,
        wiki.jurisdiction_name              as primary_name,
        wiki.state_code,
        null::varchar                       as state_name,
        null::varchar                       as county,
        null::varchar                       as city,
        wiki.jurisdiction_type,
        null::varchar                       as organization_type,
        'city_state_normalized'             as match_method,
        0.85::decimal(3, 2)                 as match_confidence
    from wiki
    join jur
        on wiki.state_code = jur.state_code
        and wiki.jurisdiction_type = jur.jurisdiction_type
        and (
            lower(trim(wiki.jurisdiction_name))
                = lower(trim(regexp_replace(jur.jurisdiction_name, ' (Town|City)$', '', 'i')))
            or
            regexp_replace(lower(trim(wiki.jurisdiction_name)), '[^a-z]', '', 'g')
                = regexp_replace(lower(trim(jur.jurisdiction_name)), '[^a-z]', '', 'g')
        )
),

-- 6a. city_geographic: org_location JOIN wikidata cities by normalized city name.
x_city_geo_wiki as (
    select
        org.org_location_id,
        wiki.wikidata_id,
        null::integer                       as jurisdiction_ref_id,
        null::integer                       as details_search_id,
        null::varchar                       as nces_id,
        null::varchar                       as fips_code,
        null::varchar                       as geoid,
        org.org_name                        as primary_name,
        org.state_code,
        null::varchar                       as state_name,
        null::varchar                       as county,
        org.city,
        wiki.jurisdiction_type,
        org.organization_type,
        'city_geographic'                   as match_method,
        0.75::decimal(3, 2)                 as match_confidence
    from org
    join wiki
        on org.state_code = wiki.state_code
        and wiki.jurisdiction_type = 'city'
        and regexp_replace(lower(trim(org.city)), '[^a-z]', '', 'g')
            = regexp_replace(lower(trim(wiki.jurisdiction_name)), '[^a-z]', '', 'g')
    where org.city is not null
),

-- 6b. city_geographic_details: org_location JOIN jurisdiction cities by city name.
x_city_geo_details as (
    select
        org.org_location_id,
        null::integer                       as wikidata_id,
        null::integer                       as jurisdiction_ref_id,
        jur.jurisdiction_id                 as details_search_id,
        null::varchar                       as nces_id,
        null::varchar                       as fips_code,
        null::varchar                       as geoid,
        org.org_name                        as primary_name,
        org.state_code,
        null::varchar                       as state_name,
        null::varchar                       as county,
        org.city,
        jur.jurisdiction_type,
        org.organization_type,
        'city_geographic_details'           as match_method,
        0.75::decimal(3, 2)                 as match_confidence
    from org
    join jur
        on org.state_code = jur.state_code
        and jur.jurisdiction_type = 'city'
        and regexp_replace(lower(trim(org.city)), '[^a-z]', '', 'g')
            = regexp_replace(
                lower(trim(regexp_replace(jur.jurisdiction_name, ' (Town|City)$', '', 'i'))),
                '[^a-z]', '', 'g'
            )
    where org.city is not null
),

-- 7. proximity_1mile: nearest wikidata jurisdiction within ~0.015 degrees, in
--    the same state, for org_location rows NOT already matched to any wikidata
--    record by an earlier strategy (x_nces / x_city_geo_wiki). Uses a lateral
--    join (LIMIT 1 nearest) exactly like the Python CROSS JOIN LATERAL.
already_matched_to_wiki as (
    select org_location_id from x_nces           where wikidata_id is not null
    union
    select org_location_id from x_city_geo_wiki  where wikidata_id is not null
),

x_proximity as (
    select
        org.org_location_id,
        nearest.wikidata_id,
        null::integer                       as jurisdiction_ref_id,
        null::integer                       as details_search_id,
        null::varchar                       as nces_id,
        null::varchar                       as fips_code,
        null::varchar                       as geoid,
        org.org_name                        as primary_name,
        org.state_code,
        null::varchar                       as state_name,
        null::varchar                       as county,
        org.city,
        nearest.jurisdiction_type,
        org.organization_type,
        'proximity_1mile'                   as match_method,
        0.70::decimal(3, 2)                 as match_confidence
    from org
    cross join lateral (
        select
            w.wikidata_id,
            w.jurisdiction_type
        from wiki w
        where w.latitude is not null
          and w.longitude is not null
          and w.state_code = org.state_code
          and sqrt(power(w.latitude - org.latitude, 2) + power(w.longitude - org.longitude, 2)) < 0.015
        order by sqrt(power(w.latitude - org.latitude, 2) + power(w.longitude - org.longitude, 2))
        limit 1
    ) nearest
    where org.latitude is not null
      and org.longitude is not null
      and org.org_location_id not in (select org_location_id from already_matched_to_wiki)
),

-- 8. domain_exact: domains in int_master__domain_registry that appear in >1
--    source table (cross-source collision). Mirrors build_crosswalk_by_domain.
--    NOTE: the registry keeps one row per domain, so a "collision" can only be
--    detected if the de-dup is computed over the UNION rather than the deduped
--    registry. The Python computed it from domain_registry AFTER dedup, where
--    each domain has a single source_table row -> COUNT(DISTINCT source_table)
--    is always 1 and this strategy matched ~0 rows. We faithfully reproduce the
--    Python (HAVING > 1 over the deduped registry), which yields no rows; see
--    _schema note. (The real cross-source linking is covered by strategies 9/10.)
x_domain_exact as (
    select
        max(case when source_table = 'organization_location' then source_id end) as org_location_id,
        max(case when source_table = 'jurisdictions_wikidata' then source_id end) as wikidata_id,
        null::integer                       as jurisdiction_ref_id,
        max(case when source_table = 'jurisdiction' then source_id end)           as details_search_id,
        null::varchar                       as nces_id,
        null::varchar                       as fips_code,
        null::varchar                       as geoid,
        max(jurisdiction_name)              as primary_name,
        max(state_code)                     as state_code,
        null::varchar                       as state_name,
        null::varchar                       as county,
        max(city)                           as city,
        null::varchar                       as jurisdiction_type,
        null::varchar                       as organization_type,
        'domain_exact'                      as match_method,
        0.95::decimal(3, 2)                 as match_confidence
    from registry
    group by domain
    having count(distinct source_table) > 1
),

-- 9. domain_orgloc_wikidata: org_location JOIN wikidata on shared normalized domain.
x_domain_ol_wiki as (
    select
        org.org_location_id,
        wiki.wikidata_id,
        null::integer                       as jurisdiction_ref_id,
        null::integer                       as details_search_id,
        null::varchar                       as nces_id,
        null::varchar                       as fips_code,
        null::varchar                       as geoid,
        org.org_name                        as primary_name,
        org.state_code,
        null::varchar                       as state_name,
        null::varchar                       as county,
        org.city,
        wiki.jurisdiction_type,
        org.organization_type,
        'domain_orgloc_wikidata'            as match_method,
        0.90::decimal(3, 2)                 as match_confidence
    from org
    join wiki
        on org.domain = wiki.domain
    where org.domain is not null
),

-- 10. domain_orgloc_details: org_location JOIN jurisdiction on shared domain.
--     We take the Python's "direct website column" branch (jurisdiction has
--     website_url -> stg domain). The JSONB-gov_domains fallback branch is noted
--     as deferred in _schema (only ran when no website column existed).
x_domain_ol_details as (
    select
        org.org_location_id,
        null::integer                       as wikidata_id,
        null::integer                       as jurisdiction_ref_id,
        jur.jurisdiction_id                 as details_search_id,
        null::varchar                       as nces_id,
        null::varchar                       as fips_code,
        null::varchar                       as geoid,
        org.org_name                        as primary_name,
        org.state_code,
        null::varchar                       as state_name,
        null::varchar                       as county,
        org.city,
        jur.jurisdiction_type,
        org.organization_type,
        'domain_orgloc_details'             as match_method,
        0.90::decimal(3, 2)                 as match_confidence
    from org
    join jur
        on org.domain = jur.domain
    where org.domain is not null
),

-- 11. name_state_type: org_location JOIN jurisdiction on exact name + state, with
--     organization_type<->jurisdiction_type compatibility mapping.
x_name_state_type as (
    select
        org.org_location_id,
        null::integer                       as wikidata_id,
        jur.jurisdiction_id                 as jurisdiction_ref_id,
        null::integer                       as details_search_id,
        null::varchar                       as nces_id,
        null::varchar                       as fips_code,
        null::varchar                       as geoid,
        org.org_name                        as primary_name,
        org.state_code,
        null::varchar                       as state_name,
        null::varchar                       as county,
        null::varchar                       as city,
        jur.jurisdiction_type,
        org.organization_type,
        'name_state_type'                   as match_method,
        0.85::decimal(3, 2)                 as match_confidence
    from org
    join jur
        on lower(trim(org.org_name)) = lower(trim(jur.jurisdiction_name))
        and org.state_code = jur.state_code
        and (
            (org.organization_type = 'school_district' and jur.jurisdiction_type = 'school_district')
            or (org.organization_type = 'county' and jur.jurisdiction_type = 'county')
            or (org.organization_type in ('city', 'town', 'village') and jur.jurisdiction_type = 'city')
            or (org.organization_type = 'township' and jur.jurisdiction_type = 'township')
        )
    where org.org_name is not null
),

unioned as (
    select * from x_nces
    union all select * from x_geoid
    union all select * from x_name_normalized
    union all select * from x_city_state
    union all select * from x_city_geo_wiki
    union all select * from x_city_geo_details
    union all select * from x_proximity
    union all select * from x_domain_exact
    union all select * from x_domain_ol_wiki
    union all select * from x_domain_ol_details
    union all select * from x_name_state_type
),

final as (
    select
        row_number() over (order by match_method, org_location_id, wikidata_id, jurisdiction_ref_id, details_search_id)
                                            as crosswalk_id,
        org_location_id,
        wikidata_id,
        jurisdiction_ref_id,
        details_search_id,
        nces_id,
        fips_code,
        geoid,
        primary_name,
        state_code,
        state_name,
        county,
        city,
        jurisdiction_type,
        organization_type,
        match_method,
        match_confidence,
        current_timestamp                   as dbt_loaded_at
    from unioned
)

select * from final
