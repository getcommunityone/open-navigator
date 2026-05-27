{{ config(materialized='table') }}

/*
    Intermediate: APPLY the Wikidata enrichment to the seeded *_wikidata rows.

    This replaces the Python "UPDATE bronze_jurisdictions_*_wikidata SET ...
    WHERE geoid = ..." step in load_jurisdictions_wikidata.py. The UPDATE-on-geoid
    becomes a LEFT JOIN: every seeded jurisdiction row (stg_wikidata__jurisdiction_*)
    keeps its base attributes and gains the matched Wikidata enrichment columns
    (or NULLs when unmatched) — exactly the post-UPDATE shape of the bronze
    *_wikidata tables, minus the legacy public.jurisdictions_wikidata path.

    There is NO clean raw-INSERT "LAND" layer for Wikidata — it was always
    UPDATE-enrichment on pre-seeded census rows. The SEED (stg_wikidata__*) plus
    this APPLY join together ARE the land+derive for this source.

    GEOID<->Wikidata-identifier reconciliation (the load-bearing bit the Python
    _parse_jurisdiction_results did per-type):
      * county  : 5-digit county GEOID == P882/P3006 (fips/fips_alt), with the
                  4-digit "missing leading zero" variant zero-padded to 5.
      * city    : 7-digit place GEOID == state_fips || lpad(P774 place fips, 5),
                  OR gnis_id == ansicode.
      * school  : 7-digit GEOID == P6545 (nces) or P882 (fips), zero-pad aware.

    FLAG (needs-human refinement): the Python loader also did fuzzy name matching
    and wbsearchentities entity-search to recover counties/municipalities whose
    identifiers do not line up with Census GEOIDs. That fuzzy recovery is NOT
    reproduced here (it stays a scraper in scripts/) — so this model attaches
    enrichment only for identifier-clean matches. Unmatched seed rows get NULL
    enrichment, same as a NULL wikidata_id row after a partial Python run.

    State-level enrichment (descriptive metadata: aliases, demonym, anthem, etc.)
    is also NOT modeled here — the FETCH layer currently bulk-maps only county /
    city / school_district. See FLAG list in the agent report.
*/

with

county_seed as (
    select * from {{ ref('stg_wikidata__jurisdiction_counties') }}
),

muni_seed as (
    select * from {{ ref('stg_wikidata__jurisdiction_municipalities') }}
),

school_seed as (
    select * from {{ ref('stg_wikidata__jurisdiction_school_districts') }}
),

enrichment as (
    select * from {{ ref('stg_wikidata__enrichment') }}
),

county_enrichment as (
    select * from enrichment where jurisdiction_type = 'county'
),

muni_enrichment as (
    select * from enrichment where jurisdiction_type = 'city'
),

school_enrichment as (
    select * from enrichment where jurisdiction_type = 'school_district'
),

counties_applied as (
    select
        s.geoid,
        s.state_code,
        s.jurisdiction_type,
        s.jurisdiction_name,
        s.latitude                                   as base_latitude,
        s.longitude                                  as base_longitude,
        s.source_ingested_at,
        e.wikidata_id,
        e.item_label                                 as wikidata_label,
        e.official_website,
        e.official_image_url,
        e.page_banner_image,
        e.locator_map_image,
        e.youtube_channel_id,
        e.youtube_channel_url,
        e.facebook_username,
        e.facebook_url,
        e.twitter_username,
        e.twitter_url,
        e.population,
        e.area_sq_km,
        e.per_capita_income,
        e.number_of_households,
        e.median_age,
        e.latitude                                   as wikidata_latitude,
        e.longitude                                  as wikidata_longitude,
        e.wikidata_fetched_at
    from county_seed s
    left join county_enrichment e
        on s.state_code = e.state_code
       and s.geoid in (
            e.fips_code,
            e.fips_alt,
            lpad(coalesce(e.fips_code, ''), 5, '0'),
            lpad(coalesce(e.fips_alt, ''), 5, '0')
       )
),

municipalities_applied as (
    select
        s.geoid,
        s.state_code,
        s.jurisdiction_type,
        s.jurisdiction_name,
        s.latitude                                   as base_latitude,
        s.longitude                                  as base_longitude,
        s.source_ingested_at,
        e.wikidata_id,
        e.item_label                                 as wikidata_label,
        e.official_website,
        e.official_image_url,
        e.page_banner_image,
        e.locator_map_image,
        e.youtube_channel_id,
        e.youtube_channel_url,
        e.facebook_username,
        e.facebook_url,
        e.twitter_username,
        e.twitter_url,
        e.population,
        e.area_sq_km,
        e.per_capita_income,
        e.number_of_households,
        e.median_age,
        e.latitude                                   as wikidata_latitude,
        e.longitude                                  as wikidata_longitude,
        e.wikidata_fetched_at
    from muni_seed s
    left join muni_enrichment e
        on s.state_code = e.state_code
       and (
            -- 7-digit place GEOID == 2-digit state FIPS || 5-digit place FIPS.
            s.geoid = left(s.geoid, 2) || lpad(coalesce(e.fips_code, ''), 5, '0')
            -- GNIS match (Census ansicode == Wikidata P590).
         or s.ansicode = e.gnis_id
       )
),

school_districts_applied as (
    select
        s.geoid,
        s.state_code,
        s.jurisdiction_type,
        s.jurisdiction_name,
        s.latitude                                   as base_latitude,
        s.longitude                                  as base_longitude,
        s.source_ingested_at,
        e.wikidata_id,
        e.item_label                                 as wikidata_label,
        e.official_website,
        e.official_image_url,
        e.page_banner_image,
        e.locator_map_image,
        e.youtube_channel_id,
        e.youtube_channel_url,
        e.facebook_username,
        e.facebook_url,
        e.twitter_username,
        e.twitter_url,
        e.population,
        e.area_sq_km,
        e.per_capita_income,
        e.number_of_households,
        e.median_age,
        e.latitude                                   as wikidata_latitude,
        e.longitude                                  as wikidata_longitude,
        e.wikidata_fetched_at
    from school_seed s
    left join school_enrichment e
        on s.state_code = e.state_code
       and s.geoid in (
            e.nces_id,
            e.fips_code,
            lpad(coalesce(e.nces_id, ''), 7, '0'),
            lpad(coalesce(e.fips_code, ''), 7, '0')
       )
),

final as (
    select
        geoid,
        state_code,
        jurisdiction_type,
        jurisdiction_name,
        wikidata_id,
        wikidata_label,
        official_website,
        official_image_url,
        page_banner_image,
        locator_map_image,
        youtube_channel_id,
        youtube_channel_url,
        facebook_username,
        facebook_url,
        twitter_username,
        twitter_url,
        population,
        area_sq_km,
        per_capita_income,
        number_of_households,
        median_age,
        coalesce(wikidata_latitude, base_latitude)   as latitude,
        coalesce(wikidata_longitude, base_longitude) as longitude,
        wikidata_fetched_at,
        source_ingested_at,
        current_timestamp                            as dbt_loaded_at
    from counties_applied

    union all
    select
        geoid, state_code, jurisdiction_type, jurisdiction_name,
        wikidata_id, wikidata_label, official_website, official_image_url,
        page_banner_image, locator_map_image, youtube_channel_id,
        youtube_channel_url, facebook_username, facebook_url, twitter_username,
        twitter_url, population, area_sq_km, per_capita_income,
        number_of_households, median_age,
        coalesce(wikidata_latitude, base_latitude),
        coalesce(wikidata_longitude, base_longitude),
        wikidata_fetched_at, source_ingested_at, current_timestamp
    from municipalities_applied

    union all
    select
        geoid, state_code, jurisdiction_type, jurisdiction_name,
        wikidata_id, wikidata_label, official_website, official_image_url,
        page_banner_image, locator_map_image, youtube_channel_id,
        youtube_channel_url, facebook_username, facebook_url, twitter_username,
        twitter_url, population, area_sq_km, per_capita_income,
        number_of_households, median_age,
        coalesce(wikidata_latitude, base_latitude),
        coalesce(wikidata_longitude, base_longitude),
        wikidata_fetched_at, source_ingested_at, current_timestamp
    from school_districts_applied
)

select * from final
