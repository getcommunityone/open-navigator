-- Migration: bronze.bronze_addresses — tax parcel / situs property records (Esri attribute harvest)
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/074_create_bronze_addresses.sql

BEGIN;

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_addresses (
    id                      BIGSERIAL PRIMARY KEY,
    source_dataset          TEXT          NOT NULL,
    source_record_id        TEXT          NOT NULL,
    state_code              CHAR(2)       NOT NULL,
    county_fips             VARCHAR(5),
    county_name             TEXT,
    jurisdiction_id         TEXT,
    owner_name              TEXT,
    situs_location          TEXT,
    street_number           TEXT,
    street_line1            TEXT,
    street_line2            TEXT,
    city                    TEXT,
    state_abbr              CHAR(2),
    postal_code             VARCHAR(10),
    situs_full              TEXT,
    parcel_number           TEXT,
    parcel_number_formatted TEXT,
    appraised_value         BIGINT,
    tax_class               TEXT,
    data_source             TEXT          NOT NULL DEFAULT 'esri_parcel',
    esri_endpoint           TEXT,
    raw_attributes          JSONB         NOT NULL DEFAULT '{}'::jsonb,
    loaded_at               TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_bronze_addresses_source UNIQUE (source_dataset, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_bronze_addresses_state_county
    ON bronze.bronze_addresses (state_code, county_fips);
CREATE INDEX IF NOT EXISTS idx_bronze_addresses_jurisdiction_id
    ON bronze.bronze_addresses (jurisdiction_id)
    WHERE jurisdiction_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bronze_addresses_parcel_number
    ON bronze.bronze_addresses (state_code, parcel_number_formatted)
    WHERE parcel_number_formatted IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bronze_addresses_owner
    ON bronze.bronze_addresses USING gin (to_tsvector('english', coalesce(owner_name, '')));

COMMENT ON TABLE bronze.bronze_addresses IS
    'Tax parcel situs and owner attributes from county Esri FeatureServer/MapServer (returnGeometry=false harvest). Not survey-grade; assessor reference only.';

COMMIT;
