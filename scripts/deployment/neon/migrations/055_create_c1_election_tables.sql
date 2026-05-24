-- Migration: add c1 election-domain tables aligned with the bronze election scrape.
--
-- Bronze already stores election / candidacy / ballot measure rows in
-- bronze.bronze_elections_scraped. These tables provide the c1 destination layer.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.c1_division (
    id              VARCHAR(300) PRIMARY KEY,
    name            VARCHAR(500) NOT NULL DEFAULT '',
    classification  VARCHAR(100) NOT NULL DEFAULT '',
    parent_id       VARCHAR(300),
    jurisdiction_id VARCHAR(300),
    state_code      CHAR(2),
    extras          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_c1_division_parent_id ON public.c1_division (parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_division_jurisdiction_id ON public.c1_division (jurisdiction_id) WHERE jurisdiction_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_division_state_code ON public.c1_division (state_code) WHERE state_code IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.c1_election (
    id              VARCHAR(50) PRIMARY KEY,
    legacy_id       BIGINT,
    name            TEXT NOT NULL,
    election_date   DATE,
    election_type   TEXT,
    election_status TEXT,
    jurisdiction_id VARCHAR(300),
    division_id     VARCHAR(300),
    state_code      CHAR(2),
    dedupe_key      VARCHAR(500),
    source          VARCHAR(100) NOT NULL DEFAULT 'bronze_elections_scraped',
    source_url      TEXT,
    links           JSONB        NOT NULL DEFAULT '[]'::jsonb,
    sources         JSONB        NOT NULL DEFAULT '[]'::jsonb,
    extras          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_c1_election_dedupe_key ON public.c1_election (dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_election_jurisdiction_id ON public.c1_election (jurisdiction_id) WHERE jurisdiction_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_election_division_id ON public.c1_election (division_id) WHERE division_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_election_state_code ON public.c1_election (state_code) WHERE state_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_election_election_date ON public.c1_election (election_date) WHERE election_date IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.c1_electionsource (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    election_id VARCHAR(50) NOT NULL,
    note        VARCHAR(300) NOT NULL DEFAULT '',
    url         VARCHAR(2000) NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_c1_electionsource_unique
    ON public.c1_electionsource (election_id, note, url);

CREATE TABLE IF NOT EXISTS public.c1_candidatecontest (
    id              VARCHAR(50) PRIMARY KEY,
    legacy_id       BIGINT,
    election_id     VARCHAR(50) NOT NULL,
    name            TEXT NOT NULL,
    office          TEXT,
    status          TEXT,
    jurisdiction_id VARCHAR(300),
    state_code      CHAR(2),
    dedupe_key      VARCHAR(500),
    source          VARCHAR(100) NOT NULL DEFAULT 'bronze_elections_scraped',
    source_url      TEXT,
    extras          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_c1_candidatecontest_dedupe_key ON public.c1_candidatecontest (dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_candidatecontest_election_id ON public.c1_candidatecontest (election_id);
CREATE INDEX IF NOT EXISTS ix_c1_candidatecontest_jurisdiction_id ON public.c1_candidatecontest (jurisdiction_id) WHERE jurisdiction_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_candidatecontest_state_code ON public.c1_candidatecontest (state_code) WHERE state_code IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.c1_candidacy (
    id              VARCHAR(50) PRIMARY KEY,
    legacy_id       BIGINT,
    election_id     VARCHAR(50) NOT NULL,
    contest_id      VARCHAR(50),
    contest_name    TEXT,
    person_name     TEXT,
    person_id       VARCHAR(50),
    party           TEXT,
    status          TEXT,
    vote_count      BIGINT,
    vote_percent    DOUBLE PRECISION,
    jurisdiction_id VARCHAR(300),
    state_code      CHAR(2),
    dedupe_key      VARCHAR(500),
    source          VARCHAR(100) NOT NULL DEFAULT 'bronze_elections_scraped',
    source_url      TEXT,
    extras          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    raw_row         JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_c1_candidacy_dedupe_key ON public.c1_candidacy (dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_candidacy_election_id ON public.c1_candidacy (election_id);
CREATE INDEX IF NOT EXISTS ix_c1_candidacy_contest_id ON public.c1_candidacy (contest_id) WHERE contest_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_candidacy_jurisdiction_id ON public.c1_candidacy (jurisdiction_id) WHERE jurisdiction_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_candidacy_state_code ON public.c1_candidacy (state_code) WHERE state_code IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.c1_ballotmeasure (
    id              VARCHAR(50) PRIMARY KEY,
    legacy_id       BIGINT,
    election_id     VARCHAR(50),
    name            TEXT NOT NULL,
    title           TEXT,
    summary         TEXT,
    classification  TEXT,
    status          TEXT,
    result          TEXT,
    yes_votes       BIGINT,
    no_votes        BIGINT,
    yes_percentage  DOUBLE PRECISION,
    jurisdiction_id VARCHAR(300),
    state_code      CHAR(2),
    dedupe_key      VARCHAR(500),
    source          VARCHAR(100) NOT NULL DEFAULT 'bronze_elections_scraped',
    source_url      TEXT,
    extras          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    raw_row         JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_c1_ballotmeasure_dedupe_key ON public.c1_ballotmeasure (dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_ballotmeasure_election_id ON public.c1_ballotmeasure (election_id) WHERE election_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_ballotmeasure_jurisdiction_id ON public.c1_ballotmeasure (jurisdiction_id) WHERE jurisdiction_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_ballotmeasure_state_code ON public.c1_ballotmeasure (state_code) WHERE state_code IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.c1_ballotmeasuresource (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ballotmeasure_id VARCHAR(50) NOT NULL,
    note             VARCHAR(300) NOT NULL DEFAULT '',
    url              VARCHAR(2000) NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_c1_ballotmeasuresource_unique
    ON public.c1_ballotmeasuresource (ballotmeasure_id, note, url);

COMMENT ON TABLE public.c1_election IS 'Election calendar rows promoted from bronze.bronze_elections_scraped.';
COMMENT ON TABLE public.c1_candidatecontest IS 'Contest rows derived from candidacy records.';
COMMENT ON TABLE public.c1_candidacy IS 'Candidate rows promoted from bronze.bronze_elections_scraped.';
COMMENT ON TABLE public.c1_ballotmeasure IS 'Ballot measure rows promoted from bronze.bronze_elections_scraped.';

COMMIT;