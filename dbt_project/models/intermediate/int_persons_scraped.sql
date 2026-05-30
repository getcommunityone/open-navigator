{{
  config(
    materialized='view',
    tags=['intermediate', 'persons', 'contacts']
  )
}}

/*
Usable scraped persons, deduplicated to one row per person per jurisdiction.

This is the first downstream consumer of the name-quality classification in
stg_bronze_persons_scraped: it filters to is_usable_person (dropping the UI
chrome, org/place names, logo alt-text, non-Latin script, dated headings, etc.
that the staging view soft-flags) and collapses duplicate scrapes of the same
person.

Grain: one row per (jurisdiction_id, normalized name_clean).
Dedup: when the same person was scraped multiple times, keep the most complete
row — prefer one carrying an email, then a phone, then the most recently
scraped, with bronze_person_id as a final deterministic tiebreaker.
source_row_count records how many raw rows collapsed into each surviving person.
*/

WITH usable AS (
    SELECT
        bronze_person_id,
        scrape_batch_id,
        jurisdiction_id,
        state_code,
        ocd_id,
        source_page_url,
        page_classification,
        extraction_method,
        contact_source,
        name_clean,
        {{ normalize_name('name_clean') }} AS name_key,
        role,
        organization,
        email,
        phone,
        mailing_address,
        profile_url,
        has_email,
        contact_details,
        scraped_at,
        loaded_at
    FROM {{ ref('stg_bronze_persons_scraped') }}
    WHERE is_usable_person
      -- name_clean is non-null for every usable row, but guard the dedup key
      -- against names that normalize to empty (e.g. punctuation-only remnants).
      AND {{ normalize_name('name_clean') }} <> ''
),

ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY jurisdiction_id, name_key
            ORDER BY
                has_email DESC,
                (phone IS NOT NULL) DESC,
                scraped_at DESC NULLS LAST,
                bronze_person_id
        ) AS rn,
        COUNT(*) OVER (PARTITION BY jurisdiction_id, name_key) AS source_row_count
    FROM usable
)

SELECT
    -- Surrogate key for the deduplicated person grain
    {{ dbt_utils.generate_surrogate_key(['jurisdiction_id', 'name_key']) }} AS person_key,

    -- Provenance of the winning row
    bronze_person_id,
    scrape_batch_id,
    jurisdiction_id,
    state_code,
    ocd_id,
    source_page_url,
    page_classification,
    extraction_method,
    contact_source,

    -- Identity
    name_clean AS name,
    name_key,
    role,
    organization,

    -- Contact
    email,
    phone,
    mailing_address,
    profile_url,
    has_email,
    contact_details,

    -- Dedup bookkeeping
    source_row_count,

    -- Timestamps
    scraped_at,
    loaded_at

FROM ranked
WHERE rn = 1
