{{
  config(
    materialized='table',
    tags=['marts', 'events', 'documents', 'transcripts', 'production'],
    unique_key='event_document_id',
    indexes=[
      {'columns': ['event_id'], 'type': 'btree'},
      {'columns': ['document_type'], 'type': 'btree'},
      {'columns': ['video_id'], 'type': 'btree'},
      {'columns': ['state_code'], 'type': 'btree'},
      {'columns': ['event_date'], 'type': 'btree'}
    ],
    post_hook=[
      -- GIN on the STORED content_tsv column (not on to_tsvector(content)): the
      -- search ranks with ts_rank(content_tsv, query), and ranking off an
      -- expression index would force Postgres to recompute to_tsvector over the
      -- full 43KB-avg transcript for every match (a common word like "water"
      -- matches thousands of rows -> 25s+ stall). Storing the vector makes both
      -- the @@ match and the ts_rank ordering read precomputed lexemes.
      "CREATE INDEX IF NOT EXISTS event_documents_content_tsv_idx ON {{ this }} USING gin (content_tsv)"
    ]
  )
}}

/*
public.event_documents - searchable documents attached to a golden-record event.

One row per (event, document). Today the only document_type is 'transcript'
(video transcripts coming from events_text_search); the shape generalizes to
future agenda / minutes / caption documents without a schema change.

This model:
- Sources transcripts from events_text_search (already deduped to the best
  transcript per video and joined to event).
- Re-validates event_id against the CURRENT `event` build so the FK holds -
  event.event_id is a volatile ROW_NUMBER() surrogate (see mdm_bridge_event_*),
  so this must build after `event` (the ref() below enforces that ordering).
  The join is a LEFT JOIN and event_id is NULLABLE on purpose: ~90% of
  transcripts have no golden event yet (their video was never promoted into
  `event` - the YouTube->event promotion gap), and we keep them searchable
  rather than drop them. event_id is populated (and the API deep-links to a
  meeting) only when it resolves to a real golden event; a NULL FK value is
  valid and skips the constraint.
- Denormalizes a few event fields (title / date / jurisdiction / state) so the
  API search is a single-table scan and results carry location + a linkable
  meeting_id when an event exists.

Data flow:
  bronze_event_youtube_transcript -> stg_bronze_event_youtube_transcript
    -> events_text_search -> event_documents (this model)

Used by: api/routes/search_postgres.py (search_documents_pg).
*/

WITH transcripts AS (
    SELECT
        event_id,
        video_id,
        raw_text,
        segments,
        language,
        is_auto_generated,
        transcript_source,
        created_at
    FROM {{ ref('events_text_search') }}
    WHERE raw_text IS NOT NULL
),

-- LEFT JOIN to the current event build: validates event_id for the FK (only a
-- real golden event_id survives; otherwise NULL) and denormalizes the fields
-- search needs. Orphan transcripts (no golden event) are kept and searchable.
joined AS (
    SELECT
        e.event_id,
        t.video_id,
        t.raw_text,
        t.segments,
        t.language,
        t.is_auto_generated,
        t.transcript_source,
        t.created_at,
        e.event_title,
        e.event_date,
        e.jurisdiction_name,
        e.jurisdiction_type,
        e.state_code,
        e.state,
        e.city,
        e.video_url
    FROM transcripts t
    LEFT JOIN {{ ref('event') }} e ON e.event_id = t.event_id
)

SELECT
    ROW_NUMBER() OVER (ORDER BY created_at DESC, video_id) AS event_document_id,
    event_id,
    'transcript'::text                                     AS document_type,
    transcript_source                                      AS document_source,
    video_id,
    raw_text                                               AS content,
    -- Precomputed full-text vector stored alongside the raw text so the search
    -- API can ts_rank() without recomputing to_tsvector over every match.
    -- Indexed by the content_tsv GIN index (see post_hook).
    to_tsvector('english', raw_text)                       AS content_tsv,
    LENGTH(raw_text)                                       AS content_length,
    CASE
        WHEN raw_text IS NOT NULL
        THEN array_length(regexp_split_to_array(TRIM(raw_text), '\s+'), 1)
        ELSE 0
    END                                                    AS word_count,
    language,
    is_auto_generated,
    segments,
    event_title,
    event_date,
    jurisdiction_name,
    jurisdiction_type,
    state_code,
    state,
    city,
    video_url,
    created_at::timestamp                                  AS created_at
FROM joined
ORDER BY event_document_id
