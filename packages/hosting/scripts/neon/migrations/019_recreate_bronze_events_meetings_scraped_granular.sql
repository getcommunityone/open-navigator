-- Migration: Replace per-jurisdiction wide rows with one row per scraped URL (county / municipality / school district).
-- Drops tables from 018 and recreates with granular meeting-oriented columns.
-- Calendar years in JSON elsewhere use VARCHAR(4); meeting_date is a true DATE for filtering.

BEGIN;

DROP TABLE IF EXISTS bronze.bronze_events_meetings_counties_scraped CASCADE;
DROP TABLE IF EXISTS bronze.bronze_events_meetings_municipalities_scraped CASCADE;
DROP TABLE IF EXISTS bronze.bronze_events_meetings_school_districts_scraped CASCADE;

CREATE TABLE bronze.bronze_events_meetings_counties_scraped (
    id                       BIGSERIAL PRIMARY KEY,
    jurisdiction_id        TEXT NOT NULL,
    state_code               CHAR(2) NOT NULL,
    census_geoid             TEXT NOT NULL,
    homepage_url             TEXT,
    manifest_scraped_at      TIMESTAMPTZ NOT NULL,
    manifest_relative_path   TEXT,
    url                      TEXT NOT NULL,
    url_sha256               CHAR(64) NOT NULL,
    resource_kind            TEXT NOT NULL,
    local_path               TEXT,
    file_bytes               BIGINT,
    doc_type                 TEXT,
    anchor_or_link_text      TEXT,
    is_likely_meeting        BOOLEAN NOT NULL DEFAULT FALSE,
    meeting_date             DATE,
    meeting_date_source      TEXT,
    meeting_title            TEXT,
    meeting_attendees        JSONB,
    contact_hints            JSONB,
    raw_resource             JSONB,
    loaded_at                TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_meetings_counties_scraped_jurisdiction_url UNIQUE (jurisdiction_id, url_sha256),
    CONSTRAINT chk_meetings_counties_resource_kind CHECK (
        resource_kind IN ('html_page', 'pdf', 'youtube', 'other_stream')
    )
);

CREATE INDEX idx_meetings_counties_scraped_state ON bronze.bronze_events_meetings_counties_scraped (state_code);
CREATE INDEX idx_meetings_counties_scraped_jurisdiction ON bronze.bronze_events_meetings_counties_scraped (jurisdiction_id);
CREATE INDEX idx_meetings_counties_scraped_meeting ON bronze.bronze_events_meetings_counties_scraped (is_likely_meeting);
CREATE INDEX idx_meetings_counties_scraped_meeting_date ON bronze.bronze_events_meetings_counties_scraped (meeting_date);

COMMENT ON TABLE bronze.bronze_events_meetings_counties_scraped IS
    'One row per URL from county meeting scrapes (_manifest pages_fetched, pdfs, streams). meeting_attendees reserved for future named rosters; contact_hints holds emails/phones matched from manifest by_page.';
COMMENT ON COLUMN bronze.bronze_events_meetings_counties_scraped.meeting_attendees IS
    'Reserved: named attendees when scraper or downstream NLP supplies them; manifests today rarely include rosters.';

CREATE TABLE bronze.bronze_events_meetings_municipalities_scraped (
    id                       BIGSERIAL PRIMARY KEY,
    jurisdiction_id        TEXT NOT NULL,
    state_code               CHAR(2) NOT NULL,
    census_geoid             TEXT NOT NULL,
    homepage_url             TEXT,
    manifest_scraped_at      TIMESTAMPTZ NOT NULL,
    manifest_relative_path   TEXT,
    url                      TEXT NOT NULL,
    url_sha256               CHAR(64) NOT NULL,
    resource_kind            TEXT NOT NULL,
    local_path               TEXT,
    file_bytes               BIGINT,
    doc_type                 TEXT,
    anchor_or_link_text      TEXT,
    is_likely_meeting        BOOLEAN NOT NULL DEFAULT FALSE,
    meeting_date             DATE,
    meeting_date_source      TEXT,
    meeting_title            TEXT,
    meeting_attendees        JSONB,
    contact_hints            JSONB,
    raw_resource             JSONB,
    loaded_at                TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_meetings_muni_scraped_jurisdiction_url UNIQUE (jurisdiction_id, url_sha256),
    CONSTRAINT chk_meetings_muni_resource_kind CHECK (
        resource_kind IN ('html_page', 'pdf', 'youtube', 'other_stream')
    )
);

CREATE INDEX idx_meetings_muni_scraped_state ON bronze.bronze_events_meetings_municipalities_scraped (state_code);
CREATE INDEX idx_meetings_muni_scraped_jurisdiction ON bronze.bronze_events_meetings_municipalities_scraped (jurisdiction_id);
CREATE INDEX idx_meetings_muni_scraped_meeting ON bronze.bronze_events_meetings_municipalities_scraped (is_likely_meeting);
CREATE INDEX idx_meetings_muni_scraped_meeting_date ON bronze.bronze_events_meetings_municipalities_scraped (meeting_date);

COMMENT ON TABLE bronze.bronze_events_meetings_municipalities_scraped IS
    'One row per URL from municipality meeting scrapes; same semantics as counties_scraped.';

CREATE TABLE bronze.bronze_events_meetings_school_districts_scraped (
    id                       BIGSERIAL PRIMARY KEY,
    jurisdiction_id        TEXT NOT NULL,
    state_code               CHAR(2) NOT NULL,
    census_geoid             TEXT NOT NULL,
    homepage_url             TEXT,
    manifest_scraped_at      TIMESTAMPTZ NOT NULL,
    manifest_relative_path   TEXT,
    url                      TEXT NOT NULL,
    url_sha256               CHAR(64) NOT NULL,
    resource_kind            TEXT NOT NULL,
    local_path               TEXT,
    file_bytes               BIGINT,
    doc_type                 TEXT,
    anchor_or_link_text      TEXT,
    is_likely_meeting        BOOLEAN NOT NULL DEFAULT FALSE,
    meeting_date             DATE,
    meeting_date_source      TEXT,
    meeting_title            TEXT,
    meeting_attendees        JSONB,
    contact_hints            JSONB,
    raw_resource             JSONB,
    loaded_at                TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_meetings_sd_scraped_jurisdiction_url UNIQUE (jurisdiction_id, url_sha256),
    CONSTRAINT chk_meetings_sd_resource_kind CHECK (
        resource_kind IN ('html_page', 'pdf', 'youtube', 'other_stream')
    )
);

CREATE INDEX idx_meetings_sd_scraped_state ON bronze.bronze_events_meetings_school_districts_scraped (state_code);
CREATE INDEX idx_meetings_sd_scraped_jurisdiction ON bronze.bronze_events_meetings_school_districts_scraped (jurisdiction_id);
CREATE INDEX idx_meetings_sd_scraped_meeting ON bronze.bronze_events_meetings_school_districts_scraped (is_likely_meeting);
CREATE INDEX idx_meetings_sd_scraped_meeting_date ON bronze.bronze_events_meetings_school_districts_scraped (meeting_date);

COMMENT ON TABLE bronze.bronze_events_meetings_school_districts_scraped IS
    'One row per URL from school_district scrapes (cache path .../school/school_district_*).';

COMMIT;
