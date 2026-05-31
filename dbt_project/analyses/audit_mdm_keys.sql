-- Smoke-test the MDM normalization macros against real rows from every source
-- that feeds person/address entity resolution. Eyeball raw vs normalized to gauge
-- how dirty each source is (esp. campaign contributor_name and AI full_name)
-- BEFORE building the conformance layer on top.
--
-- Requires the extensions: dbt run-operation enable_mdm_extensions
-- Run: dbt compile --select analysis:audit_mdm_keys   (then run the SQL in the warehouse)
-- See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 1 / Build order step 1).

WITH locations AS (
    SELECT 'bronze_locations' AS source_system,
           name AS raw_name, address AS raw_address, zip AS raw_zip
    FROM bronze.bronze_locations
    LIMIT 50
),

openstates AS (
    SELECT 'openstates_persons' AS source_system,
           name AS raw_name, mailing_address AS raw_address, NULL::text AS raw_zip
    FROM bronze.bronze_persons_scraped
    LIMIT 50
),

nccs AS (
    SELECT 'givingtuesday_990_nccs' AS source_system,
           org_name_current AS raw_name, f990_org_addr_street AS raw_address,
           f990_org_addr_zip AS raw_zip
    FROM bronze.bronze_organizations_nonprofits_nccs
    LIMIT 50
),

contributions AS (
    SELECT 'campaign_contributions' AS source_system,
           contributor_name AS raw_name, NULL::text AS raw_address,
           contributor_zip AS raw_zip
    FROM bronze.bronze_campaigns_contributions
    LIMIT 50
),

addresses AS (
    -- parcel/property records: owner_name (person|org) + pre-parsed street
    SELECT 'parcel_addresses' AS source_system,
           owner_name AS raw_name,
           COALESCE(NULLIF(street_line1, ''), situs_full, situs_location) AS raw_address,
           postal_code AS raw_zip
    FROM bronze.bronze_addresses
    LIMIT 50
),

event_people AS (
    SELECT 'event_person' AS source_system,
           full_name AS raw_name, NULL::text AS raw_address, NULL::text AS raw_zip
    FROM public.event_person
    LIMIT 50
),

event_places AS (
    SELECT 'event_place' AS source_system,
           NULL::text AS raw_name, street_address AS raw_address, NULL::text AS raw_zip
    FROM public.event_place
    LIMIT 50
),

unioned AS (
    SELECT * FROM locations
    UNION ALL SELECT * FROM openstates
    UNION ALL SELECT * FROM nccs
    UNION ALL SELECT * FROM contributions
    UNION ALL SELECT * FROM addresses
    UNION ALL SELECT * FROM event_people
    UNION ALL SELECT * FROM event_places
)

SELECT
    source_system,
    raw_name,
    {{ normalize_person_name('raw_name') }}  AS normalized_name,
    {{ name_phonetic_key('raw_name') }}      AS name_phonetic_key,
    raw_address,
    {{ normalize_address('raw_address') }}   AS normalized_address,
    {{ zip5('raw_zip') }}                     AS zip5
FROM unioned
ORDER BY source_system, raw_name
