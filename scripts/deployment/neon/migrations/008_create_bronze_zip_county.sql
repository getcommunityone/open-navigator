CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_zip_county (
    zip                  CHAR(5)        NOT NULL,
    county               CHAR(5)        NOT NULL,
    usps_zip_pref_city   VARCHAR(100),
    usps_zip_pref_state  CHAR(2),
    res_ratio            NUMERIC(20, 17),
    bus_ratio            NUMERIC(20, 17),
    oth_ratio            NUMERIC(20, 17),
    tot_ratio            NUMERIC(20, 17),
    ingestion_date       TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (zip, county)
);

CREATE INDEX IF NOT EXISTS idx_bzc_zip    ON bronze.bronze_jurisdictions_zip_county(zip);
CREATE INDEX IF NOT EXISTS idx_bzc_county ON bronze.bronze_jurisdictions_zip_county(county);
CREATE INDEX IF NOT EXISTS idx_bzc_state  ON bronze.bronze_jurisdictions_zip_county(usps_zip_pref_state);
