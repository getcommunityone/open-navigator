-- Migration: two related cleanups.
--
-- A. Move public.jurisdiction_wikidata_fips_gnis_map -> bronze.bronze_jurisdiction_wikidata_fips_gnis_map.
--    This table is 833,691 rows of Wikidata QID ↔ FIPS ↔ GNIS lookups — externally sourced reference
--    data, not application/domain state. ``bronze`` is the right home.
--
-- B. Create the 5 c1_person* child tables mirroring openstates.opencivicdata_person*:
--      * c1_personidentifier  (cross-system IDs: Bioguide, OpenStates, etc.)
--      * c1_personlink        (URLs — campaign / official / social)
--      * c1_personname        (alternative / historical names)
--      * c1_personsource      (citation URLs)
--      * c1_personvote        (vote events; empty in OpenStates today but mirror for completeness)
--
--    Like the c1_event* children (migration 051), structure is 1:1 with OpenStates so a future
--    cross-DB sync is a straight INSERT-SELECT. person_id is a SOFT FK to c1_person.id
--    (no constraint) — c1_person currently has 149 rows from the legacy gold-parquet flow
--    without OCD ids; the openstates sync populates fresh ocd-person/UUID rows.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/053_wikidata_to_bronze_and_c1_person_children.sql

BEGIN;

-- =====================================================================
-- Part A: move + rename wikidata-fips-gnis map into bronze
-- =====================================================================

ALTER TABLE public.jurisdiction_wikidata_fips_gnis_map SET SCHEMA bronze;
ALTER TABLE bronze.jurisdiction_wikidata_fips_gnis_map RENAME TO bronze_jurisdiction_wikidata_fips_gnis_map;

ALTER INDEX bronze.idx_wikidata_fips_gnis_fips
    RENAME TO idx_bronze_jurisdiction_wikidata_fips_gnis_map_fips;
ALTER INDEX bronze.idx_wikidata_fips_gnis_gnis
    RENAME TO idx_bronze_jurisdiction_wikidata_fips_gnis_map_gnis;

COMMENT ON TABLE bronze.bronze_jurisdiction_wikidata_fips_gnis_map IS
    'Wikidata QID ↔ FIPS ↔ GNIS lookup table sourced from Wikidata SPARQL dumps + per-state '
    'parquet files. Moved from public schema in migration 053 since this is reference/lookup '
    'data, not application/domain state.';


-- =====================================================================
-- Part B: 5 c1_person* child tables
-- =====================================================================

-- gen_random_uuid() already enabled by migration 051
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- c1_personidentifier  (mirrors opencivicdata_personidentifier)
CREATE TABLE IF NOT EXISTS public.c1_personidentifier (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier  VARCHAR(300) NOT NULL,
    scheme      VARCHAR(300) NOT NULL,
    person_id   VARCHAR(47) NOT NULL    -- soft FK -> c1_person.id
);
CREATE INDEX IF NOT EXISTS ix_c1_personidentifier_person_id
    ON public.c1_personidentifier (person_id);
CREATE INDEX IF NOT EXISTS ix_c1_personidentifier_scheme_identifier
    ON public.c1_personidentifier (scheme, identifier);
COMMENT ON TABLE public.c1_personidentifier IS
    'Cross-system identifiers for a person (Bioguide, OpenStates, etc.). Mirrors opencivicdata_personidentifier.';


-- c1_personlink  (mirrors opencivicdata_personlink)
CREATE TABLE IF NOT EXISTS public.c1_personlink (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note      VARCHAR(300) NOT NULL DEFAULT '',
    url       VARCHAR(2000) NOT NULL,
    person_id VARCHAR(47) NOT NULL    -- soft FK -> c1_person.id
);
CREATE INDEX IF NOT EXISTS ix_c1_personlink_person_id
    ON public.c1_personlink (person_id);
COMMENT ON TABLE public.c1_personlink IS
    'External links (campaign sites, social, official) for a person. Mirrors opencivicdata_personlink.';


-- c1_personname  (mirrors opencivicdata_personname)
CREATE TABLE IF NOT EXISTS public.c1_personname (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       VARCHAR(500) NOT NULL,
    note       VARCHAR(500) NOT NULL DEFAULT '',
    start_date VARCHAR(10) NOT NULL DEFAULT '',
    end_date   VARCHAR(10) NOT NULL DEFAULT '',
    person_id  VARCHAR(47) NOT NULL    -- soft FK -> c1_person.id
);
CREATE INDEX IF NOT EXISTS ix_c1_personname_person_id
    ON public.c1_personname (person_id);
COMMENT ON TABLE public.c1_personname IS
    'Alternative / historical names for a person. Mirrors opencivicdata_personname.';


-- c1_personsource  (mirrors opencivicdata_personsource)
CREATE TABLE IF NOT EXISTS public.c1_personsource (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note      VARCHAR(300) NOT NULL DEFAULT '',
    url       VARCHAR(2000) NOT NULL,
    person_id VARCHAR(47) NOT NULL    -- soft FK -> c1_person.id
);
CREATE INDEX IF NOT EXISTS ix_c1_personsource_person_id
    ON public.c1_personsource (person_id);
COMMENT ON TABLE public.c1_personsource IS
    'Citation URLs for a person record. Mirrors opencivicdata_personsource.';


-- c1_personvote  (mirrors opencivicdata_personvote)
CREATE TABLE IF NOT EXISTS public.c1_personvote (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "option"      VARCHAR(50) NOT NULL,
    voter_name    VARCHAR(300) NOT NULL DEFAULT '',
    note          TEXT NOT NULL DEFAULT '',
    vote_event_id VARCHAR(45) NOT NULL,
    voter_id      VARCHAR(47)             -- soft FK -> c1_person.id (nullable in OpenStates)
);
CREATE INDEX IF NOT EXISTS ix_c1_personvote_vote_event_id
    ON public.c1_personvote (vote_event_id);
CREATE INDEX IF NOT EXISTS ix_c1_personvote_voter_id
    ON public.c1_personvote (voter_id) WHERE voter_id IS NOT NULL;
COMMENT ON TABLE public.c1_personvote IS
    'Individual person votes within a VoteEvent. Mirrors opencivicdata_personvote.';

COMMIT;
