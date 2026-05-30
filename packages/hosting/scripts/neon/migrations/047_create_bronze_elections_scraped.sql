-- Migration: bronze.bronze_elections_scraped — election calendar + results + ballot
-- measures. Schema aligned with OpenCivicData Election Proposal (OCD-EP-0020):
--   https://open-civic-data.readthedocs.io/en/latest/proposals/0020.html
--
-- OCD-EP-0020 defines three primary entities:
--   * Election     — a date-anchored event for one or more contests (id ocd-election/UUID).
--   * Candidacy    — a Person running for a Post in an Election (id ocd-candidacy/UUID).
--   * BallotMeasure — a yes/no measure on a ballot (id ocd-ballotmeasure/UUID).
--
-- Rather than three separate bronze tables we use one wide-and-shallow table with a
-- discriminator column ``record_type`` and entity-specific JSONB payloads. This keeps
-- the bronze layer flat for cheap ingestion and pushes normalization to a downstream
-- intermediate model that explodes the JSONB into typed views.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/047_create_bronze_elections_scraped.sql

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.bronze_elections_scraped (
    id                          BIGSERIAL PRIMARY KEY,
    scrape_batch_id             UUID NOT NULL,

    -- Discriminator: which OCD-EP-0020 entity this row represents.
    -- One of: 'election', 'candidacy', 'ballot_measure'.
    record_type                 TEXT NOT NULL CHECK (record_type IN ('election', 'candidacy', 'ballot_measure')),

    -- ocd-election / ocd-candidacy / ocd-ballotmeasure URN.
    ocd_id                      TEXT,

    -- Election-level common columns (denormalized for cheap filtering).
    election_name               TEXT,
    election_date               DATE,
    election_type               TEXT,                 -- general, primary, special, runoff, …
    election_status             TEXT,                 -- scheduled, in_progress, certified, contested

    -- Jurisdiction linkage. The OCD election can span any division; ``ocd_jurisdiction_id``
    -- (ocd-jurisdiction/...) is the authoritative key. ``state_code`` + ``jurisdiction_id``
    -- (our local int_jurisdictions key) populated when resolvable.
    ocd_jurisdiction_id         TEXT,
    state_code                  CHAR(2),
    jurisdiction_id             TEXT,

    -- Candidacy-specific (NULL for other record_types).
    candidate_name              TEXT,
    candidate_party             TEXT,
    candidate_post              TEXT,                 -- "Mayor", "City Council District 3", …
    candidate_status            TEXT,                 -- filed, qualified, withdrawn, winner, runner_up
    candidate_vote_count        BIGINT,
    candidate_vote_percent      DOUBLE PRECISION,

    -- Ballot-measure-specific (NULL for other record_types).
    measure_title               TEXT,
    measure_summary             TEXT,
    measure_classification      TEXT,                 -- referendum, initiative, charter_amendment, bond, …
    measure_yes_count           BIGINT,
    measure_no_count            BIGINT,
    measure_outcome             TEXT,                 -- passed, failed, withdrawn

    -- Provenance.
    source_url                  TEXT,
    source_name                 TEXT,                 -- 'ballotpedia', 'ca_sos', 'wikidata', …

    -- Full OCD-shaped payload for downstream normalization.
    -- Election rows: {sources:[], identifiers:[], divisions:[], children:[]}
    -- Candidacy rows: {contests:[], person:{}, post:{}, party:{}, registrations:[]}
    -- BallotMeasure rows: {classifications:[], description, full_text, supporters, opponents}
    raw_row                     JSONB NOT NULL DEFAULT '{}'::JSONB,

    scraped_at                  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    loaded_at                   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bronze_elections_scraped_record_type
    ON bronze.bronze_elections_scraped (record_type);
CREATE INDEX IF NOT EXISTS idx_bronze_elections_scraped_state
    ON bronze.bronze_elections_scraped (state_code);
CREATE INDEX IF NOT EXISTS idx_bronze_elections_scraped_jurisdiction
    ON bronze.bronze_elections_scraped (jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_bronze_elections_scraped_ocd_jur
    ON bronze.bronze_elections_scraped (ocd_jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_bronze_elections_scraped_date
    ON bronze.bronze_elections_scraped (election_date);
CREATE INDEX IF NOT EXISTS idx_bronze_elections_scraped_batch
    ON bronze.bronze_elections_scraped (scrape_batch_id);
CREATE INDEX IF NOT EXISTS idx_bronze_elections_scraped_ocd_id
    ON bronze.bronze_elections_scraped (ocd_id);

COMMENT ON TABLE bronze.bronze_elections_scraped IS
    'Election calendar + results + ballot measures, modeled on OCD-EP-0020 '
    '(https://open-civic-data.readthedocs.io/en/latest/proposals/0020.html). '
    'One row per Election | Candidacy | BallotMeasure entity, discriminated by record_type. '
    'Best-effort; treat as bronze.';

COMMENT ON COLUMN bronze.bronze_elections_scraped.record_type IS
    'OCD-EP-0020 entity discriminator: election | candidacy | ballot_measure.';
COMMENT ON COLUMN bronze.bronze_elections_scraped.ocd_id IS
    'Canonical OCD URN: ocd-election/UUID, ocd-candidacy/UUID, or ocd-ballotmeasure/UUID.';
COMMENT ON COLUMN bronze.bronze_elections_scraped.raw_row IS
    'Full source payload in OCD-EP-0020 shape (sources, identifiers, divisions for elections; '
    'contests, person, post, party for candidacies; classifications, description, supporters/opponents for measures).';

COMMIT;
