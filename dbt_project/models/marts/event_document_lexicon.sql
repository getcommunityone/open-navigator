{#
  Trigram "did-you-mean" lexicon for transcript search.

  ts_stat() walks the STORED content_tsv vectors of event_documents and returns
  one row per distinct lexeme with its document/occurrence counts. The pg_trgm
  GIN index on `word` (post_hook) lets search_documents_pg map a misspelled query
  term (e.g. "flouride") to its nearest real corpus lexeme ("fluorid") in a single
  indexed lookup, instead of failing the full-text match and returning nothing.

  We do NOT trigram-match the transcript bodies themselves -- those average ~43KB
  and an ILIKE/similarity scan over them stalls for 25s+ (see event_documents).
  The lexicon is the small, indexable surface that makes fuzzy matching cheap.

  Neon: content_tsv is NULL on the neon target (full FTS disabled there), so
  ts_stat yields no rows and this table is empty -- the API fallback simply finds
  no suggestion and returns the (already empty) document results unchanged.
#}
{{
  config(
    materialized='table',
    tags=['marts', 'events', 'documents', 'search', 'production'],
    post_hook=(
      [
        "CREATE INDEX IF NOT EXISTS event_document_lexicon_word_trgm_idx "
        "ON {{ this }} USING gin (word gin_trgm_ops)"
      ] if target.name != 'neon' else []
    )
  )
}}

/*
public.event_document_lexicon - distinct lexemes present in transcript full-text
vectors, with corpus frequencies. One row per `word`. Consumed by
api/routes/search_postgres.py (search_documents_pg fuzzy fallback).

Data flow:
  event_documents.content_tsv -> ts_stat() -> event_document_lexicon (this model)
*/

SELECT
    word,
    ndoc   AS document_count,    -- # transcripts the lexeme appears in
    nentry AS occurrence_count   -- total occurrences across all transcripts
FROM ts_stat($$SELECT content_tsv FROM {{ ref('event_documents') }}$$)
WHERE
    -- Alphabetic lexemes only: drop numbers, ids, and punctuation-mangled tokens
    -- that would never be a useful spelling suggestion.
    word ~ '^[a-z]+$'
    AND length(word) BETWEEN 4 AND 40
    -- Appear in >= 2 transcripts: keeps the lexicon to real vocabulary and stops
    -- us "correcting" one typo into another one-off OCR/ASR artifact.
    AND ndoc >= 2
