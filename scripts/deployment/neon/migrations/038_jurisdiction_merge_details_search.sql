-- Merge jurisdictions_details_search enrichment into public.jurisdiction.
-- Dev:  psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/038_jurisdiction_merge_details_search.sql
--
-- Adds discovery/YouTube/website columns to jurisdiction, backfills from the legacy
-- table, then renames the old table (does not drop data).

BEGIN;

-- Typed external id (municipality_0107000, school_district_..., or legacy id::text)
ALTER TABLE public.jurisdiction
    ADD COLUMN IF NOT EXISTS jurisdiction_id VARCHAR(50);

CREATE UNIQUE INDEX IF NOT EXISTS uq_jurisdiction_jurisdiction_id
    ON public.jurisdiction (jurisdiction_id)
    WHERE jurisdiction_id IS NOT NULL AND BTRIM(jurisdiction_id) <> '';

-- Discovery / channel enrichment (from jurisdictions_details_search)
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS discovery_timestamp TIMESTAMP;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS website_url TEXT;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS youtube_channel_count INTEGER DEFAULT 0;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS youtube_channels JSONB;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS meeting_platform_count INTEGER DEFAULT 0;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS meeting_platforms JSONB;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS social_media JSONB;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS agenda_portal_count INTEGER DEFAULT 0;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS discovery_status VARCHAR(50);
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS in_localview BOOLEAN DEFAULT FALSE;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS gov_domains JSONB;

-- Wikidata enrichment (was applied on jurisdictions_details_search by load_channels.py)
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS per_capita_income NUMERIC;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS time_zone TEXT;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS ballotpedia_id TEXT;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS tripadvisor_id TEXT;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS subreddit TEXT;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS postal_codes JSONB;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS official_image_url TEXT;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS head_of_government TEXT;

-- USCM mayor enrichment
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS current_mayor VARCHAR(200);
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS mayor_election_date DATE;
ALTER TABLE public.jurisdiction ADD COLUMN IF NOT EXISTS usmayors_last_updated TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_jurisdiction_youtube_channels
    ON public.jurisdiction USING GIN (youtube_channels);
CREATE INDEX IF NOT EXISTS idx_jurisdiction_discovery_status
    ON public.jurisdiction (discovery_status);
CREATE INDEX IF NOT EXISTS idx_jurisdiction_in_localview
    ON public.jurisdiction (in_localview)
    WHERE in_localview IS TRUE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'jurisdictions_details_search'
    ) THEN
        -- Optional columns added by enrichment scripts after the original CREATE TABLE
        ALTER TABLE public.jurisdictions_details_search ADD COLUMN IF NOT EXISTS gov_domains JSONB;
        ALTER TABLE public.jurisdictions_details_search ADD COLUMN IF NOT EXISTS per_capita_income NUMERIC;
        ALTER TABLE public.jurisdictions_details_search ADD COLUMN IF NOT EXISTS time_zone TEXT;
        ALTER TABLE public.jurisdictions_details_search ADD COLUMN IF NOT EXISTS ballotpedia_id TEXT;
        ALTER TABLE public.jurisdictions_details_search ADD COLUMN IF NOT EXISTS tripadvisor_id TEXT;
        ALTER TABLE public.jurisdictions_details_search ADD COLUMN IF NOT EXISTS subreddit TEXT;
        ALTER TABLE public.jurisdictions_details_search ADD COLUMN IF NOT EXISTS postal_codes JSONB;
        ALTER TABLE public.jurisdictions_details_search ADD COLUMN IF NOT EXISTS official_image_url TEXT;
        ALTER TABLE public.jurisdictions_details_search ADD COLUMN IF NOT EXISTS head_of_government TEXT;
        ALTER TABLE public.jurisdictions_details_search ADD COLUMN IF NOT EXISTS current_mayor VARCHAR(200);
        ALTER TABLE public.jurisdictions_details_search ADD COLUMN IF NOT EXISTS mayor_election_date DATE;
        ALTER TABLE public.jurisdictions_details_search ADD COLUMN IF NOT EXISTS usmayors_last_updated TIMESTAMP;

        -- Backfill by typed jurisdiction_id
        UPDATE public.jurisdiction j
        SET
            jurisdiction_id = COALESCE(j.jurisdiction_id, d.jurisdiction_id),
            name = COALESCE(NULLIF(BTRIM(j.name), ''), d.jurisdiction_name),
            type = COALESCE(NULLIF(BTRIM(j.type), ''), d.jurisdiction_type),
            state_code = COALESCE(NULLIF(BTRIM(j.state_code), ''), d.state_code),
            state = COALESCE(NULLIF(BTRIM(j.state), ''), d.state),
            population = COALESCE(j.population, d.population),
            discovery_timestamp = COALESCE(j.discovery_timestamp, d.discovery_timestamp),
            website_url = COALESCE(j.website_url, d.website_url),
            youtube_channel_count = COALESCE(j.youtube_channel_count, d.youtube_channel_count),
            youtube_channels = COALESCE(j.youtube_channels, d.youtube_channels),
            meeting_platform_count = COALESCE(j.meeting_platform_count, d.meeting_platform_count),
            meeting_platforms = COALESCE(j.meeting_platforms, d.meeting_platforms),
            social_media = COALESCE(j.social_media, d.social_media),
            agenda_portal_count = COALESCE(j.agenda_portal_count, d.agenda_portal_count),
            discovery_status = COALESCE(j.discovery_status, d.status),
            in_localview = COALESCE(j.in_localview, d.in_localview),
            gov_domains = COALESCE(j.gov_domains, d.gov_domains),
            per_capita_income = COALESCE(j.per_capita_income, d.per_capita_income),
            time_zone = COALESCE(j.time_zone, d.time_zone),
            ballotpedia_id = COALESCE(j.ballotpedia_id, d.ballotpedia_id),
            tripadvisor_id = COALESCE(j.tripadvisor_id, d.tripadvisor_id),
            subreddit = COALESCE(j.subreddit, d.subreddit),
            postal_codes = COALESCE(j.postal_codes, d.postal_codes),
            official_image_url = COALESCE(j.official_image_url, d.official_image_url),
            head_of_government = COALESCE(j.head_of_government, d.head_of_government),
            current_mayor = COALESCE(j.current_mayor, d.current_mayor),
            mayor_election_date = COALESCE(j.mayor_election_date, d.mayor_election_date),
            usmayors_last_updated = COALESCE(j.usmayors_last_updated, d.usmayors_last_updated),
            last_updated = GREATEST(j.last_updated, COALESCE(d.last_updated, j.last_updated))
        FROM public.jurisdictions_details_search d
        WHERE j.jurisdiction_id IS NOT DISTINCT FROM d.jurisdiction_id
           OR j.id::text = d.jurisdiction_id;

        -- Legacy link: integer search id stored in details.jurisdiction_id
        UPDATE public.jurisdiction j
        SET
            jurisdiction_id = COALESCE(j.jurisdiction_id, d.jurisdiction_id),
            website_url = COALESCE(j.website_url, d.website_url),
            youtube_channels = COALESCE(j.youtube_channels, d.youtube_channels),
            youtube_channel_count = COALESCE(j.youtube_channel_count, d.youtube_channel_count),
            discovery_status = COALESCE(j.discovery_status, d.status),
            in_localview = COALESCE(j.in_localview, d.in_localview),
            last_updated = GREATEST(j.last_updated, COALESCE(d.last_updated, j.last_updated))
        FROM public.jurisdictions_details_search d
        WHERE j.id::text = d.jurisdiction_id
          AND j.jurisdiction_id IS DISTINCT FROM d.jurisdiction_id;

        -- Name + state + type match
        UPDATE public.jurisdiction j
        SET
            jurisdiction_id = COALESCE(j.jurisdiction_id, d.jurisdiction_id),
            website_url = COALESCE(j.website_url, d.website_url),
            youtube_channels = COALESCE(j.youtube_channels, d.youtube_channels),
            youtube_channel_count = COALESCE(j.youtube_channel_count, d.youtube_channel_count),
            discovery_status = COALESCE(j.discovery_status, d.status),
            in_localview = COALESCE(j.in_localview, d.in_localview),
            last_updated = GREATEST(j.last_updated, COALESCE(d.last_updated, j.last_updated))
        FROM public.jurisdictions_details_search d
        WHERE j.jurisdiction_id IS NULL
          AND LOWER(BTRIM(j.name)) = LOWER(BTRIM(d.jurisdiction_name))
          AND j.state_code = d.state_code
          AND j.type = d.jurisdiction_type;

        -- Rows only in legacy table → insert into jurisdiction
        INSERT INTO public.jurisdiction (
            jurisdiction_id, name, type, state_code, state, population,
            discovery_timestamp, website_url, youtube_channel_count, youtube_channels,
            meeting_platform_count, meeting_platforms, social_media, agenda_portal_count,
            discovery_status, in_localview, gov_domains,
            per_capita_income, time_zone, ballotpedia_id, tripadvisor_id, subreddit,
            postal_codes, official_image_url, head_of_government,
            current_mayor, mayor_election_date, usmayors_last_updated,
            source, last_updated
        )
        SELECT
            d.jurisdiction_id,
            d.jurisdiction_name,
            d.jurisdiction_type,
            d.state_code,
            d.state,
            d.population,
            d.discovery_timestamp,
            d.website_url,
            COALESCE(d.youtube_channel_count, 0),
            d.youtube_channels,
            COALESCE(d.meeting_platform_count, 0),
            d.meeting_platforms,
            d.social_media,
            COALESCE(d.agenda_portal_count, 0),
            d.status,
            COALESCE(d.in_localview, FALSE),
            d.gov_domains,
            d.per_capita_income,
            d.time_zone,
            d.ballotpedia_id,
            d.tripadvisor_id,
            d.subreddit,
            d.postal_codes,
            d.official_image_url,
            d.head_of_government,
            d.current_mayor,
            d.mayor_election_date,
            d.usmayors_last_updated,
            'discovery',
            COALESCE(d.last_updated, CURRENT_TIMESTAMP)
        FROM public.jurisdictions_details_search d
        WHERE NOT EXISTS (
            SELECT 1 FROM public.jurisdiction j
            WHERE j.jurisdiction_id IS NOT DISTINCT FROM d.jurisdiction_id
               OR j.id::text = d.jurisdiction_id
               OR (
                   LOWER(BTRIM(j.name)) = LOWER(BTRIM(d.jurisdiction_name))
                   AND j.state_code = d.state_code
                   AND j.type = d.jurisdiction_type
               )
        );

        ALTER TABLE public.jurisdictions_details_search
            RENAME TO _deprecated_jurisdictions_details_search;
    END IF;
END $$;

COMMIT;
