-- Migration 102: rename the two bronze YouTube tables to entity-clear names,
-- make video_id the PRIMARY KEY on each, give both the SAME set of video_ids
-- (union), and backfill blank/null shared metadata from the counterpart table.
-- Date: 2026-05-31
-- Target: DEV warehouse (localhost:5433 / NEON_DATABASE_URL_DEV). NEVER prod.
--
-- WHY
-- ---
-- bronze_events_youtube (scraped video/event metadata) and bronze_events_text_ai
-- (transcript + AI text) both describe the same universe of YouTube videos keyed
-- by video_id, yet:
--   * the names are inconsistent ("events" plural; "text_ai" doesn't say
--     youtube/transcript),
--   * neither is keyed on the natural key video_id (youtube had only a UNIQUE
--     constraint; text_ai's PK was the surrogate id), and
--   * their video_id sets had drifted apart (10,457 in both; 48,302 youtube-only;
--     99,312 transcript-only).
-- This renames them to bronze_event_youtube / bronze_event_youtube_transcript,
-- promotes video_id to PRIMARY KEY, unions the video_id sets, and fills sparse
-- shared columns from the other table.
--
-- COLUMN MAPPING (identically-named + cross-named pairs)
--   description<->vid_desc, view_count<->vid_views, duration_minutes<->vid_length_min,
--   published_at<->vid_upload_date, title<->vid_title (coalesce).
--
-- SAFETY
-- ------
-- * One transaction; inspect counts before COMMIT (see the asserts at the end).
-- * The geo-sync trigger function bronze.sync_text_ai_geo_from_youtube() hard-codes
--   the OLD youtube table name, so it is recreated against the new name BEFORE any
--   insert fires it (BEFORE INSERT OR UPDATE OF video_id on the transcript table).
-- * video_url is UNIQUE on the youtube table only. The transcript->youtube insert
--   carries video_url only when globally unique (not already in youtube AND not
--   duplicated within the inserted batch), else NULL -- avoids unique violations.
--   The youtube<-transcript backfill deliberately does NOT touch youtube.video_url
--   for the same reason (and the overlap rows already carry it).
-- * Backfill UPDATEs are COALESCE/NULLIF-guarded => idempotent and non-clobbering,
--   and never touch video_id (so the transcript geo trigger does not fire) nor
--   raw_text (so the full-text GIN index content is unchanged).

BEGIN;

-- ---------------------------------------------------------------------------
-- 0. Drop the two dbt staging VIEWS that read these base tables. They reference
--    the old source names (and one pins the jurisdiction_id column type we widen
--    below), so they must go first; `dbt run` recreates them against the renamed
--    sources. Nothing else depends on them (downstream int_/marts are tables).
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS staging.stg_youtube__event;
DROP VIEW IF EXISTS staging.stg_bronze_events_text_ai;

-- ---------------------------------------------------------------------------
-- 1. Rename the tables
-- ---------------------------------------------------------------------------
ALTER TABLE bronze.bronze_events_youtube  RENAME TO bronze_event_youtube;
ALTER TABLE bronze.bronze_events_text_ai  RENAME TO bronze_event_youtube_transcript;

-- ---------------------------------------------------------------------------
-- 2. Repoint the geo-sync trigger function at the renamed youtube table
--    (it fires on every insert into the transcript table below).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bronze.sync_text_ai_geo_from_youtube()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    y_state_code        text;
    y_state             text;
    y_jurisdiction_id   text;
    y_jurisdiction_name text;
BEGIN
    IF NEW.video_id IS NOT NULL THEN
        SELECT y.state_code, y.state, y.jurisdiction_id, y.jurisdiction_name
          INTO y_state_code, y_state, y_jurisdiction_id, y_jurisdiction_name
        FROM bronze.bronze_event_youtube y
        WHERE y.video_id = NEW.video_id
        ORDER BY y.last_updated DESC NULLS LAST
        LIMIT 1;

        IF FOUND THEN
            NEW.state_code        := COALESCE(y_state_code, NEW.state_code);
            NEW.state             := COALESCE(y_state, NEW.state);
            NEW.jurisdiction_id   := COALESCE(y_jurisdiction_id, NEW.jurisdiction_id);
            NEW.jurisdiction_name := COALESCE(y_jurisdiction_name, NEW.jurisdiction_name);
        END IF;
    END IF;
    RETURN NEW;
END;
$function$;

-- ---------------------------------------------------------------------------
-- 2b. Widen youtube.jurisdiction_id varchar(50) -> text to match the transcript
--     side (legacy jurisdiction_ids reach 59 chars there); avoids truncation on
--     the transcript->youtube insert and the youtube<-transcript backfill.
-- ---------------------------------------------------------------------------
ALTER TABLE bronze.bronze_event_youtube
    ALTER COLUMN jurisdiction_id TYPE text;

-- ---------------------------------------------------------------------------
-- 3. PRIMARY KEY on video_id -- youtube
--    Drop the old UNIQUE(video_id) constraint, promote video_id to PK.
--    Keep the UNIQUE(video_url) constraint.
-- ---------------------------------------------------------------------------
ALTER TABLE bronze.bronze_event_youtube
    DROP CONSTRAINT bronze_events_youtube_video_id_key;
ALTER TABLE bronze.bronze_event_youtube
    ADD CONSTRAINT bronze_event_youtube_pkey PRIMARY KEY (video_id);

-- ---------------------------------------------------------------------------
-- 4. PRIMARY KEY on video_id -- transcript
--    Drop the surrogate-id PK and the redundant video_id indexes, promote
--    video_id to PK, and preserve the id contract with a UNIQUE(id).
-- ---------------------------------------------------------------------------
ALTER TABLE bronze.bronze_event_youtube_transcript
    DROP CONSTRAINT bronze_events_text_ai_pkey;
DROP INDEX IF EXISTS bronze.idx_bronze_events_text_video_id_unique;
DROP INDEX IF EXISTS bronze.idx_bronze_events_text_ai_video_id;
ALTER TABLE bronze.bronze_event_youtube_transcript
    ADD CONSTRAINT bronze_event_youtube_transcript_pkey PRIMARY KEY (video_id);
ALTER TABLE bronze.bronze_event_youtube_transcript
    ADD CONSTRAINT bronze_event_youtube_transcript_id_key UNIQUE (id);

-- ---------------------------------------------------------------------------
-- 5. Insert youtube-only video_ids into the transcript table (stub rows).
--    id is the sequence default; has_transcript=false (no transcript text).
--    The BEFORE INSERT trigger re-derives geo from youtube (no-op here).
-- ---------------------------------------------------------------------------
INSERT INTO bronze.bronze_event_youtube_transcript
    (video_id, event_id, event_date, title, vid_title, vid_desc,
     jurisdiction_id, jurisdiction_name, state_code, state, meeting_type,
     channel_id, channel_url, channel_type, video_url,
     vid_views, vid_length_min, language, vid_upload_date,
     has_transcript, created_at, last_updated)
SELECT
    y.video_id, y.event_id, y.event_date, y.title, y.title, y.description,
    y.jurisdiction_id, y.jurisdiction_name, y.state_code, y.state, y.meeting_type,
    y.channel_id, y.channel_url, y.channel_type, y.video_url,
    y.view_count::double precision, y.duration_minutes::double precision,
    y.language, y.published_at,
    false, now(), now()
FROM bronze.bronze_event_youtube y
WHERE NOT EXISTS (
    SELECT 1 FROM bronze.bronze_event_youtube_transcript t WHERE t.video_id = y.video_id
)
ON CONFLICT (video_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 6. Insert transcript-only video_ids into the youtube table (stub rows).
--    video_url carried only when globally unique (youtube has UNIQUE(video_url));
--    id left NULL (column is nullable, no default).
-- ---------------------------------------------------------------------------
WITH src AS (
    SELECT
        t.*,
        ROW_NUMBER() OVER (PARTITION BY t.video_url
                           ORDER BY t.last_updated DESC NULLS LAST) AS vu_rn
    FROM bronze.bronze_event_youtube_transcript t
    WHERE NOT EXISTS (
        SELECT 1 FROM bronze.bronze_event_youtube y WHERE y.video_id = t.video_id
    )
)
INSERT INTO bronze.bronze_event_youtube
    (video_id, event_id, event_date, title, description,
     jurisdiction_id, jurisdiction_name, state_code, state, meeting_type,
     channel_id, channel_url, channel_type, video_url,
     view_count, duration_minutes, language, published_at,
     datasource, last_updated)
SELECT
    src.video_id, src.event_id, src.event_date,
    COALESCE(src.title, src.vid_title), src.vid_desc,
    src.jurisdiction_id, src.jurisdiction_name, src.state_code, src.state, src.meeting_type,
    src.channel_id, src.channel_url, src.channel_type,
    CASE
        WHEN src.video_url IS NOT NULL
         AND src.vu_rn = 1
         AND NOT EXISTS (SELECT 1 FROM bronze.bronze_event_youtube y2 WHERE y2.video_url = src.video_url)
        THEN src.video_url
        ELSE NULL
    END,
    CASE WHEN src.vid_views      BETWEEN 0 AND 2147483647 THEN round(src.vid_views)::int      ELSE NULL END,
    CASE WHEN src.vid_length_min BETWEEN 0 AND 2147483647 THEN round(src.vid_length_min)::int ELSE NULL END,
    src.language, src.vid_upload_date,
    'youtube', now()
FROM src
ON CONFLICT (video_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 7. Backfill blank/null shared columns on overlap rows (idempotent).
--    7a. youtube  <- transcript  (video_url intentionally excluded: UNIQUE)
-- ---------------------------------------------------------------------------
UPDATE bronze.bronze_event_youtube y SET
    event_date       = COALESCE(y.event_date, t.event_date),
    title            = COALESCE(NULLIF(y.title, ''), NULLIF(t.title, ''), t.vid_title),
    description      = COALESCE(NULLIF(y.description, ''), t.vid_desc),
    jurisdiction_id  = COALESCE(NULLIF(y.jurisdiction_id, ''), t.jurisdiction_id),
    jurisdiction_name= COALESCE(NULLIF(y.jurisdiction_name, ''), t.jurisdiction_name),
    state_code       = COALESCE(NULLIF(y.state_code, ''), t.state_code),
    state            = COALESCE(NULLIF(y.state, ''), t.state),
    meeting_type     = COALESCE(NULLIF(y.meeting_type, ''), t.meeting_type),
    channel_id       = COALESCE(NULLIF(y.channel_id, ''), t.channel_id),
    channel_url      = COALESCE(NULLIF(y.channel_url, ''), t.channel_url),
    channel_type     = COALESCE(NULLIF(y.channel_type, ''), t.channel_type),
    view_count       = COALESCE(y.view_count, CASE WHEN t.vid_views BETWEEN 0 AND 2147483647 THEN round(t.vid_views)::int ELSE NULL END),
    duration_minutes = COALESCE(y.duration_minutes, CASE WHEN t.vid_length_min BETWEEN 0 AND 2147483647 THEN round(t.vid_length_min)::int ELSE NULL END),
    language         = COALESCE(NULLIF(y.language, ''), t.language),
    published_at     = COALESCE(y.published_at, t.vid_upload_date)
FROM bronze.bronze_event_youtube_transcript t
WHERE t.video_id = y.video_id
  -- Only touch rows that actually gain a value (skips the just-inserted stubs,
  -- which already carry the counterpart's values). youtube has no GIN index so
  -- this is a btree-only update.
  AND (
       (y.event_date IS NULL                     AND t.event_date IS NOT NULL)
    OR (NULLIF(y.title, '') IS NULL              AND COALESCE(t.title, t.vid_title) IS NOT NULL)
    OR (NULLIF(y.description, '') IS NULL        AND t.vid_desc IS NOT NULL)
    OR (NULLIF(y.jurisdiction_id, '') IS NULL    AND t.jurisdiction_id IS NOT NULL)
    OR (NULLIF(y.jurisdiction_name, '') IS NULL  AND t.jurisdiction_name IS NOT NULL)
    OR (NULLIF(y.state_code, '') IS NULL         AND t.state_code IS NOT NULL)
    OR (NULLIF(y.state, '') IS NULL              AND t.state IS NOT NULL)
    OR (NULLIF(y.meeting_type, '') IS NULL       AND t.meeting_type IS NOT NULL)
    OR (NULLIF(y.channel_id, '') IS NULL         AND t.channel_id IS NOT NULL)
    OR (NULLIF(y.channel_url, '') IS NULL        AND t.channel_url IS NOT NULL)
    OR (NULLIF(y.channel_type, '') IS NULL       AND t.channel_type IS NOT NULL)
    OR (y.view_count IS NULL                     AND t.vid_views IS NOT NULL)
    OR (y.duration_minutes IS NULL               AND t.vid_length_min IS NOT NULL)
    OR (NULLIF(y.language, '') IS NULL           AND t.language IS NOT NULL)
    OR (y.published_at IS NULL                   AND t.vid_upload_date IS NOT NULL)
  );

-- 7b. transcript <- youtube  (does NOT touch video_id or raw_text)
UPDATE bronze.bronze_event_youtube_transcript t SET
    event_date       = COALESCE(t.event_date, y.event_date),
    title            = COALESCE(NULLIF(t.title, ''), y.title),
    vid_title        = COALESCE(NULLIF(t.vid_title, ''), y.title),
    vid_desc         = COALESCE(NULLIF(t.vid_desc, ''), y.description),
    jurisdiction_id  = COALESCE(NULLIF(t.jurisdiction_id, ''), y.jurisdiction_id),
    jurisdiction_name= COALESCE(NULLIF(t.jurisdiction_name, ''), y.jurisdiction_name),
    state_code       = COALESCE(NULLIF(t.state_code, ''), y.state_code),
    state            = COALESCE(NULLIF(t.state, ''), y.state),
    meeting_type     = COALESCE(NULLIF(t.meeting_type, ''), y.meeting_type),
    channel_id       = COALESCE(NULLIF(t.channel_id, ''), y.channel_id),
    channel_url      = COALESCE(NULLIF(t.channel_url, ''), y.channel_url),
    channel_type     = COALESCE(NULLIF(t.channel_type, ''), y.channel_type),
    video_url        = COALESCE(NULLIF(t.video_url, ''), y.video_url),
    vid_views        = COALESCE(t.vid_views, y.view_count::double precision),
    vid_length_min   = COALESCE(t.vid_length_min, y.duration_minutes::double precision),
    language         = COALESCE(NULLIF(t.language, ''), y.language),
    vid_upload_date  = COALESCE(t.vid_upload_date, y.published_at)
FROM bronze.bronze_event_youtube y
WHERE y.video_id = t.video_id
  -- CRITICAL: the transcript table is GIN-indexed (fillfactor 100 => non-HOT
  -- updates re-insert the whole transcript tsvector). After the union every
  -- transcript row has a youtube match, so without this guard we would churn the
  -- GIN over all 158k rows (~the hour-long trap from migration 098). Restricting
  -- to rows that actually gain a value keeps this to the ~10k original-overlap
  -- rows. raw_text is never touched, so GIN content is unchanged.
  AND (
       (t.event_date IS NULL                     AND y.event_date IS NOT NULL)
    OR (NULLIF(t.title, '') IS NULL              AND y.title IS NOT NULL)
    OR (NULLIF(t.vid_title, '') IS NULL          AND y.title IS NOT NULL)
    OR (NULLIF(t.vid_desc, '') IS NULL           AND y.description IS NOT NULL)
    OR (NULLIF(t.jurisdiction_id, '') IS NULL    AND y.jurisdiction_id IS NOT NULL)
    OR (NULLIF(t.jurisdiction_name, '') IS NULL  AND y.jurisdiction_name IS NOT NULL)
    OR (NULLIF(t.state_code, '') IS NULL         AND y.state_code IS NOT NULL)
    OR (NULLIF(t.state, '') IS NULL              AND y.state IS NOT NULL)
    OR (NULLIF(t.meeting_type, '') IS NULL       AND y.meeting_type IS NOT NULL)
    OR (NULLIF(t.channel_id, '') IS NULL         AND y.channel_id IS NOT NULL)
    OR (NULLIF(t.channel_url, '') IS NULL        AND y.channel_url IS NOT NULL)
    OR (NULLIF(t.channel_type, '') IS NULL       AND y.channel_type IS NOT NULL)
    OR (NULLIF(t.video_url, '') IS NULL          AND y.video_url IS NOT NULL)
    OR (t.vid_views IS NULL                      AND y.view_count IS NOT NULL)
    OR (t.vid_length_min IS NULL                 AND y.duration_minutes IS NOT NULL)
    OR (NULLIF(t.language, '') IS NULL           AND y.language IS NOT NULL)
    OR (t.vid_upload_date IS NULL                AND y.published_at IS NOT NULL)
  );

-- ---------------------------------------------------------------------------
-- 8. Post-conditions (raise if the merge did not converge). Both tables must
--    hold the identical set of video_ids and have a video_id PRIMARY KEY.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    n_y   bigint;
    n_t   bigint;
    n_sym bigint;  -- video_ids present in exactly one table
BEGIN
    SELECT count(*) INTO n_y FROM bronze.bronze_event_youtube;
    SELECT count(*) INTO n_t FROM bronze.bronze_event_youtube_transcript;
    SELECT count(*) INTO n_sym FROM (
        (SELECT video_id FROM bronze.bronze_event_youtube
         EXCEPT SELECT video_id FROM bronze.bronze_event_youtube_transcript)
        UNION ALL
        (SELECT video_id FROM bronze.bronze_event_youtube_transcript
         EXCEPT SELECT video_id FROM bronze.bronze_event_youtube)
    ) d;

    RAISE NOTICE 'bronze_event_youtube rows=%, transcript rows=%, video_ids in exactly one table=%',
        n_y, n_t, n_sym;

    IF n_sym <> 0 THEN
        RAISE EXCEPTION 'video_id sets did not converge: % rows present in only one table', n_sym;
    END IF;
    IF n_y <> n_t THEN
        RAISE EXCEPTION 'row counts differ after union: youtube=% transcript=%', n_y, n_t;
    END IF;
END $$;

COMMIT;
