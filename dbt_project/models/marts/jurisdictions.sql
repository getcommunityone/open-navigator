{#
  post_hook GIN FTS index rationale: jurisdiction search (search_jurisdictions_pg
  in api/routes/search_postgres.py) ranks with
  ts_rank(to_tsvector('english', COALESCE(search_text, display_name)), query).
  Without a GIN index Postgres recomputes to_tsvector over all ~82k rows per
  query (seq scan). The index expression MUST match the API's tsvector
  expression exactly (COALESCE(search_text, display_name)) for the planner to
  use it. Mirrors the pattern in event.sql / event_documents.sql. This note
  lives in a Jinja comment, NOT a `--` SQL comment inside config(), which is
  invalid Jinja and breaks `dbt parse` for the whole project.
#}
{{
  config(
    materialized='table',
    tags=['gold', 'jurisdictions', 'api'],
    unique_key='jurisdiction_id',
    indexes=[
      {'columns': ['jurisdiction_id'], 'unique': True},
      {'columns': ['geoid'], 'type': 'btree'},
      {'columns': ['state_code'], 'type': 'btree'},
      {'columns': ['jurisdiction_type'], 'type': 'btree'}
    ],
    post_hook=[
      "CREATE INDEX IF NOT EXISTS jurisdictions_search_fts_idx ON {{ this }} USING gin (to_tsvector('english', coalesce(search_text, display_name)))"
    ]
  )
}}

/*
public.jurisdictions - API-Ready Final Table

Single source of truth for jurisdiction data consumed by
api/routes/search_postgres.py (search_jurisdictions_pg) and the frontend
jurisdiction search.

Lineage note: rebuilt on the LIVE canonical pipeline
(intermediate.int_jurisdictions, 82,921 rows, built from the sharded
bronze.bronze_jurisdictions_* tables). The previous lineage
(source bronze_jurisdictions -> int_jurisdictions_clean ->
int_jurisdictions_linked) was dead in this warehouse: the single "master list"
table bronze.bronze_jurisdictions was never created here, only the shards.

One row per jurisdiction (per geoid). Enrichment joins are deduped so they do
not fan out the grain:
  - population  <- public.jurisdiction_acs.total_population (on geoid)
  - website_url <- intermediate.int_jurisdiction_websites (best 1 per
                   jurisdiction_id, ranked by source quality)

jurisdiction_type is mapped to the values the API level filter expects
(level_mapping in search_postgres.py: city/county/town/village/
school_district/special_district/state). Census-native 'municipality' -> 'city'
and 'township' -> 'town'; the raw census type is kept as jurisdiction_category.
*/

WITH base AS (
    SELECT *
    FROM {{ ref('int_jurisdictions') }}
),

-- Quality filter: must have the essential identifiers + a valid geoid length
quality_filtered AS (
    SELECT *
    FROM base
    WHERE
        name IS NOT NULL
        AND state_code IS NOT NULL
        AND geoid IS NOT NULL
        AND jurisdiction_type IS NOT NULL
        AND (
            (jurisdiction_type = 'state'           AND length(geoid) = 2)
            OR (jurisdiction_type = 'county'        AND length(geoid) = 5)
            OR (jurisdiction_type = 'municipality'  AND length(geoid) = 7)
            OR (jurisdiction_type = 'school_district' AND length(geoid) = 7)
            OR (jurisdiction_type = 'township'      AND length(geoid) = 10)
        )
),

-- Best single website per jurisdiction (avoid fan-out; up to 136 rows/jurisdiction)
websites_ranked AS (
    SELECT
        jurisdiction_id,
        website_url,
        ROW_NUMBER() OVER (
            PARTITION BY jurisdiction_id
            ORDER BY
                CASE website_source
                    WHEN 'override'        THEN 1
                    WHEN 'gsa'             THEN 2
                    WHEN 'naco'            THEN 3
                    WHEN 'nces_directory'  THEN 4
                    WHEN 'league'          THEN 5
                    WHEN 'uscm'            THEN 6
                    WHEN 'wikidata'        THEN 7
                    ELSE 99
                END,
                website_url
        ) AS rn
    FROM {{ ref('int_jurisdiction_websites') }}
    WHERE jurisdiction_id IS NOT NULL
      AND website_url IS NOT NULL
),

best_website AS (
    SELECT jurisdiction_id, website_url
    FROM websites_ranked
    WHERE rn = 1
),

-- Population: ACS has multiple rows per geoid (geography_type place vs sduni,
-- multiple vintages). Dedupe to one row per geoid, latest vintage first.
acs_ranked AS (
    SELECT
        geoid,
        total_population,
        ROW_NUMBER() OVER (
            PARTITION BY geoid
            ORDER BY acs_vintage_year DESC,
                     CASE geography_type WHEN 'place' THEN 1 ELSE 2 END,
                     total_population DESC
        ) AS rn
    FROM {{ source('gold_runtime', 'jurisdiction_acs') }}
    WHERE geoid IS NOT NULL
),

acs AS (
    SELECT geoid, total_population
    FROM acs_ranked
    WHERE rn = 1
),

api_ready AS (
    SELECT
        j.jurisdiction_id,
        j.geoid,
        j.fips_code,
        j.ansicode,

        -- Display fields
        j.name,
        j.name AS display_name,

        -- API-facing type (matches level_mapping in search_postgres.py).
        -- search_jurisdictions_pg both filters its WHERE clause on and SELECTs
        -- `jurisdiction_type` (aliased to `type` in its own SELECT for output),
        -- so this single canonical column is all the API needs.
        CASE j.jurisdiction_type
            WHEN 'municipality' THEN 'city'
            WHEN 'township'     THEN 'town'
            ELSE j.jurisdiction_type
        END AS jurisdiction_type,
        -- Raw census classification preserved for provenance
        j.jurisdiction_type AS jurisdiction_category,

        -- Geographic hierarchy
        j.state_code,
        j.state AS state_name,
        -- A county's own name IS its county; no place->county crosswalk is
        -- available at scale (bronze_jurisdictions_place_county has only 66
        -- rows), so non-county jurisdictions have a NULL county_name.
        CASE
            WHEN j.jurisdiction_type = 'county' THEN j.name
            ELSE NULL
        END AS county_name,

        -- Demographics
        a.total_population::bigint AS population,
        j.area_sq_miles,

        -- Location
        j.latitude,
        j.longitude,

        -- Links
        w.website_url,

        -- Search blob: name + state + type (+ county when present)
        TRIM(
            CONCAT_WS(' ',
                j.name,
                j.state,
                j.state_code,
                j.jurisdiction_type,
                CASE WHEN j.jurisdiction_type = 'county' THEN j.name ELSE NULL END
            )
        ) AS search_text,

        j.ingestion_date,
        j.transformed_at,
        CURRENT_TIMESTAMP AS published_at
    FROM quality_filtered j
    LEFT JOIN best_website w ON j.jurisdiction_id = w.jurisdiction_id
    LEFT JOIN acs a ON j.geoid = a.geoid
)

SELECT * FROM api_ready
