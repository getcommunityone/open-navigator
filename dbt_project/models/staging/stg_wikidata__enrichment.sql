{{ config(materialized='view') }}

/*
    Staging: Wikidata enrichment rows fetched by ingestion.wikidata.download.

    This is the cached ENRICHMENT side of the old
    load_jurisdictions_wikidata.py UPDATE. The FETCH layer
    (ingestion.wikidata.download) writes per-jurisdiction enrichment rows to
    data/cache/wikidata/<usps>/wikidata_enrichment_<type>.json; a thin bronze
    loader lands those rows into bronze.bronze_jurisdiction_wikidata_enrichment
    (one physical row per (state_code, jurisdiction_type, wikidata_id), with the
    Wikidata identifiers fips_code / fips_alt / gnis_id / nces_id and the
    enrichment payload). See FLAG in _schema_stg_wikidata.yml — that loader is a
    small needs-human follow-up (cache JSON -> bronze table), analogous to
    ingestion.gsa.domains landing the GSA cache CSV.

    This model normalizes types and exposes the identifier columns that
    int_wikidata__jurisdictions_enriched reconciles to the seed GEOID. Four-CTE
    template per dbt_project/CONVENTIONS.md.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_jurisdiction_wikidata_enrichment') }}
),

renamed as (
    select
        nullif(trim(wikidata_id), '')                as wikidata_id,
        upper(nullif(trim(state_code), ''))          as state_code,
        nullif(trim(jurisdiction_type), '')          as jurisdiction_type,
        nullif(trim(item_label), '')                 as item_label,
        -- Wikidata identifiers (digits-only, dashes already stripped upstream).
        replace(nullif(trim(fips_code), ''), '-', '')   as fips_code,
        replace(nullif(trim(fips_alt), ''), '-', '')    as fips_alt,
        replace(nullif(trim(gnis_id), ''), '-', '')     as gnis_id,
        replace(nullif(trim(nces_id), ''), '-', '')     as nces_id,
        -- Enrichment payload.
        nullif(trim(official_website), '')           as official_website,
        nullif(trim(official_image_url), '')         as official_image_url,
        nullif(trim(page_banner_image), '')          as page_banner_image,
        nullif(trim(locator_map_image), '')          as locator_map_image,
        nullif(trim(youtube_channel_id), '')         as youtube_channel_id,
        nullif(trim(facebook_username), '')          as facebook_username,
        nullif(trim(twitter_username), '')           as twitter_username,
        population::bigint                           as population,
        area_sq_km::double precision                 as area_sq_km,
        per_capita_income::bigint                    as per_capita_income,
        number_of_households::double precision       as number_of_households,
        median_age::double precision                 as median_age,
        latitude::double precision                   as latitude,
        longitude::double precision                  as longitude,
        fetched_at                                   as wikidata_fetched_at
    from source
),

filtered as (
    -- A usable enrichment row needs a Q-id; rows with no join identifier at all
    -- cannot be reconciled to a seed GEOID and are dropped.
    select *
    from renamed
    where wikidata_id is not null
      and (
            fips_code is not null
         or fips_alt is not null
         or gnis_id is not null
         or nces_id is not null
      )
),

final as (
    select
        wikidata_id,
        state_code,
        jurisdiction_type,
        item_label,
        fips_code,
        fips_alt,
        gnis_id,
        nces_id,
        case
            when youtube_channel_id is null then null
            else 'https://www.youtube.com/channel/' || youtube_channel_id
        end                                          as youtube_channel_url,
        official_website,
        official_image_url,
        page_banner_image,
        locator_map_image,
        youtube_channel_id,
        facebook_username,
        case
            when facebook_username is null then null
            else 'https://www.facebook.com/' || facebook_username
        end                                          as facebook_url,
        twitter_username,
        case
            when twitter_username is null then null
            else 'https://twitter.com/' || twitter_username
        end                                          as twitter_url,
        population,
        area_sq_km,
        per_capita_income,
        number_of_households,
        median_age,
        latitude,
        longitude,
        wikidata_fetched_at,
        current_timestamp                            as dbt_loaded_at
    from filtered
)

select * from final
