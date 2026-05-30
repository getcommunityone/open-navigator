{{
  config(
    materialized='view',
    tags=['staging', 'persons', 'contacts', 'quality']
  )
}}

/*
Staging view for bronze_persons_scraped (scraped person / contact rows).

Adds name-quality classification and a recovered `name_clean` so downstream
models can filter junk WITHOUT mutating the raw bronze landing table. Nothing is
deleted here (one row in -> one row out); rows are SOFT-FLAGGED via name_quality
/ invalid_reason and the convenience boolean is_usable_person.

name_quality:
  - ok        : looks like a real person name
  - recovered : had a strippable prefix ("Portrait of <name>") that yielded a name
  - missing   : name is null/empty (often still carries a usable email)
  - invalid   : not a person (see invalid_reason)

invalid_reason (only when name_quality = 'invalid'):
  - ui_label       : page chrome ("Email", "Contact Us", "Staff Directory", ...)
  - role_only      : a bare role with no person ("Mayor", "Commissioner", ...)
  - markup_or_file : HTML/markup, a URL/path, or an image/file name
  - sentence       : a paragraph / blurb (too long or too many words)

Source: bronze_persons_scraped (open_navigator.bronze schema)
*/

WITH source AS (
    SELECT * FROM {{ source('bronze', 'bronze_persons_scraped') }}
),

cleaned AS (
    SELECT
        *,
        -- Recover a name from "Portrait/Photo/Headshot/Image/Picture of <name>".
        NULLIF(
            BTRIM(
                REGEXP_REPLACE(
                    name,
                    '^(portrait|photo|headshot|image|picture)\s+of\s+',
                    '', 'i'
                )
            ),
            ''
        ) AS name_destripped
    FROM source
),

classified AS (
    SELECT
        *,
        CASE
            WHEN name IS NULL OR BTRIM(name) = '' THEN 'missing'
            -- HTML / markup / URL-path / image or document file name
            WHEN name ~ '[<>{}|/\\@]'
                 OR name ~* '\.(png|jpe?g|gif|webp|svg|pdf)\s*$' THEN 'invalid_markup_or_file'
            -- Page chrome / call-to-action labels
            WHEN name ~* '^(e-?mail|contact|staff directory|directory|menu|home|search|read more|learn more|click here|view profile|for immediate release|covid)\M'
                 OR name ~* '(contact us|contact info|contact information|contact me|contact by email|email us|email the webmaster|email webmaster|our office|mayor''s office|staff directory)' THEN 'invalid_ui_label'
            -- A bare role title with no personal name
            WHEN name ~* '^(mayor|commissioner|council ?member|councilman|councilwoman|councilor|councillor|alderman|alderwoman|clerk|treasurer|board of [a-z]+|department of [a-z]+|chair(man|woman|person)?|director|trustee|supervisor|sheriff|assessor)\s*$' THEN 'invalid_role_only'
            -- A sentence / blurb rather than a name
            WHEN LENGTH(name) > 60
                 OR ARRAY_LENGTH(REGEXP_SPLIT_TO_ARRAY(BTRIM(name), '\s+'), 1) > 8 THEN 'invalid_sentence'
            -- A prefix was stripped and a plausible name remained
            WHEN name_destripped IS DISTINCT FROM name AND name_destripped ~ '\S' THEN 'recovered'
            ELSE 'ok'
        END AS name_status
    FROM cleaned
)

SELECT
    -- Identity / grain
    id AS bronze_person_id,
    scrape_batch_id,
    jurisdiction_id,
    state_code,
    ocd_id,

    -- Provenance
    NULLIF(BTRIM(source_page_url), '') AS source_page_url,
    NULLIF(BTRIM(page_classification), '') AS page_classification,
    NULLIF(BTRIM(extraction_method), '') AS extraction_method,
    NULLIF(BTRIM(contact_source), '') AS contact_source,

    -- Raw + cleaned name
    name AS name_raw,
    CASE
        WHEN name_status IN ('ok', 'recovered') THEN
            BTRIM(REGEXP_REPLACE(COALESCE(name_destripped, name), '\s+', ' ', 'g'))
        ELSE NULL
    END AS name_clean,

    -- Quality classification
    CASE WHEN name_status LIKE 'invalid%' THEN 'invalid' ELSE name_status END AS name_quality,
    CASE WHEN name_status LIKE 'invalid_%' THEN SUBSTRING(name_status FROM 9) END AS invalid_reason,
    (name_status IN ('ok', 'recovered')) AS is_usable_person,

    -- Other person/contact fields
    NULLIF(BTRIM(role), '') AS role,
    NULLIF(BTRIM(organization), '') AS organization,
    NULLIF(BTRIM(email), '') AS email,
    NULLIF(BTRIM(phone), '') AS phone,
    NULLIF(BTRIM(mailing_address), '') AS mailing_address,
    NULLIF(BTRIM(profile_url), '') AS profile_url,
    (email IS NOT NULL AND BTRIM(email) <> '') AS has_email,
    contact_details,

    -- Timestamps
    scraped_at,
    loaded_at

FROM classified
