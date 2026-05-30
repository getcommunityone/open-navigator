-- Migration: Scraped meetings bronze — one row per URL (link or document), manifest context on each row.
-- Drops prior granular tables (019) and recreates with resource_category + detected_stacks + extracted_contacts.

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
    resource_category        TEXT NOT NULL,
    resource_kind            TEXT NOT NULL,
    url                      TEXT NOT NULL,
    url_sha256               CHAR(64) NOT NULL,
    local_path               TEXT,
    file_bytes               BIGINT,
    doc_type                 TEXT,
    anchor_or_link_text      TEXT,
    detected_stacks          JSONB NOT NULL DEFAULT '[]'::JSONB,
    extracted_contacts       JSONB,
    contact_hints            JSONB,
    is_likely_meeting        BOOLEAN NOT NULL DEFAULT FALSE,
    meeting_date             DATE,
    meeting_date_source      TEXT,
    meeting_title            TEXT,
    meeting_attendees        JSONB,
    raw_resource             JSONB,
    loaded_at                TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_meetings_counties_scraped_jurisdiction_url UNIQUE (jurisdiction_id, url_sha256),
    CONSTRAINT chk_meetings_counties_resource_category CHECK (resource_category IN ('link', 'document')),
    CONSTRAINT chk_meetings_counties_resource_kind CHECK (
        resource_kind IN ('html_page', 'pdf', 'youtube', 'other_stream')
    )
);

CREATE INDEX idx_meetings_counties_scraped_state ON bronze.bronze_events_meetings_counties_scraped (state_code);
CREATE INDEX idx_meetings_counties_scraped_jurisdiction ON bronze.bronze_events_meetings_counties_scraped (jurisdiction_id);
CREATE INDEX idx_meetings_counties_scraped_category ON bronze.bronze_events_meetings_counties_scraped (resource_category);
CREATE INDEX idx_meetings_counties_scraped_meeting ON bronze.bronze_events_meetings_counties_scraped (is_likely_meeting);
CREATE INDEX idx_meetings_counties_scraped_meeting_date ON bronze.bronze_events_meetings_counties_scraped (meeting_date);

COMMENT ON TABLE bronze.bronze_events_meetings_counties_scraped IS
    'One row per scraped URL: resource_category link (HTML page, stream) vs document (PDF). '
    'detected_stacks and extracted_contacts are copied from the parent _manifest.json onto every row for filtering without joining.';

CREATE TABLE bronze.bronze_events_meetings_municipalities_scraped (
    id                       BIGSERIAL PRIMARY KEY,
    jurisdiction_id        TEXT NOT NULL,
    state_code               CHAR(2) NOT NULL,
    census_geoid             TEXT NOT NULL,
    homepage_url             TEXT,
    manifest_scraped_at      TIMESTAMPTZ NOT NULL,
    manifest_relative_path   TEXT,
    resource_category        TEXT NOT NULL,
    resource_kind            TEXT NOT NULL,
    url                      TEXT NOT NULL,
    url_sha256               CHAR(64) NOT NULL,
    local_path               TEXT,
    file_bytes               BIGINT,
    doc_type                 TEXT,
    anchor_or_link_text      TEXT,
    detected_stacks          JSONB NOT NULL DEFAULT '[]'::JSONB,
    extracted_contacts       JSONB,
    contact_hints            JSONB,
    is_likely_meeting        BOOLEAN NOT NULL DEFAULT FALSE,
    meeting_date             DATE,
    meeting_date_source      TEXT,
    meeting_title            TEXT,
    meeting_attendees        JSONB,
    raw_resource             JSONB,
    loaded_at                TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_meetings_muni_scraped_jurisdiction_url UNIQUE (jurisdiction_id, url_sha256),
    CONSTRAINT chk_meetings_muni_resource_category CHECK (resource_category IN ('link', 'document')),
    CONSTRAINT chk_meetings_muni_resource_kind CHECK (
        resource_kind IN ('html_page', 'pdf', 'youtube', 'other_stream')
    )
);

CREATE INDEX idx_meetings_muni_scraped_state ON bronze.bronze_events_meetings_municipalities_scraped (state_code);
CREATE INDEX idx_meetings_muni_scraped_jurisdiction ON bronze.bronze_events_meetings_municipalities_scraped (jurisdiction_id);
CREATE INDEX idx_meetings_muni_scraped_category ON bronze.bronze_events_meetings_municipalities_scraped (resource_category);
CREATE INDEX idx_meetings_muni_scraped_meeting ON bronze.bronze_events_meetings_municipalities_scraped (is_likely_meeting);
CREATE INDEX idx_meetings_muni_scraped_meeting_date ON bronze.bronze_events_meetings_municipalities_scraped (meeting_date);

COMMENT ON TABLE bronze.bronze_events_meetings_municipalities_scraped IS
    'Same grain as counties_scraped: one row per link or document from municipality manifests.';

CREATE TABLE bronze.bronze_events_meetings_school_districts_scraped (
    id                       BIGSERIAL PRIMARY KEY,
    jurisdiction_id        TEXT NOT NULL,
    state_code               CHAR(2) NOT NULL,
    census_geoid             TEXT NOT NULL,
    homepage_url             TEXT,
    manifest_scraped_at      TIMESTAMPTZ NOT NULL,
    manifest_relative_path   TEXT,
    resource_category        TEXT NOT NULL,
    resource_kind            TEXT NOT NULL,
    url                      TEXT NOT NULL,
    url_sha256               CHAR(64) NOT NULL,
    local_path               TEXT,
    file_bytes               BIGINT,
    doc_type                 TEXT,
    anchor_or_link_text      TEXT,
    detected_stacks          JSONB NOT NULL DEFAULT '[]'::JSONB,
    extracted_contacts       JSONB,
    contact_hints            JSONB,
    is_likely_meeting        BOOLEAN NOT NULL DEFAULT FALSE,
    meeting_date             DATE,
    meeting_date_source      TEXT,
    meeting_title            TEXT,
    meeting_attendees        JSONB,
    raw_resource             JSONB,
    loaded_at                TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_meetings_sd_scraped_jurisdiction_url UNIQUE (jurisdiction_id, url_sha256),
    CONSTRAINT chk_meetings_sd_resource_category CHECK (resource_category IN ('link', 'document')),
    CONSTRAINT chk_meetings_sd_resource_kind CHECK (
        resource_kind IN ('html_page', 'pdf', 'youtube', 'other_stream')
    )
);

CREATE INDEX idx_meetings_sd_scraped_state ON bronze.bronze_events_meetings_school_districts_scraped (state_code);
CREATE INDEX idx_meetings_sd_scraped_jurisdiction ON bronze.bronze_events_meetings_school_districts_scraped (jurisdiction_id);
CREATE INDEX idx_meetings_sd_scraped_category ON bronze.bronze_events_meetings_school_districts_scraped (resource_category);
CREATE INDEX idx_meetings_sd_scraped_meeting ON bronze.bronze_events_meetings_school_districts_scraped (is_likely_meeting);
CREATE INDEX idx_meetings_sd_scraped_meeting_date ON bronze.bronze_events_meetings_school_districts_scraped (meeting_date);

COMMENT ON TABLE bronze.bronze_events_meetings_school_districts_scraped IS
    'One row per link or document from school district manifests (cache .../school/school_district_*).';

COMMIT;
