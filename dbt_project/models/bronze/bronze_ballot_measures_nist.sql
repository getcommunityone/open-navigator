{{
    config(
        materialized='table',
        schema='bronze',
        tags=['bronze', 'ballot_measures', 'nist_vip']
    )
}}

/*
Bronze Ballot Measures — NIST SP 1500-100 / VIP-aligned landing table.

Spec: NIST Election Results Reporting Common Data Format (ERR-CDF), SP 1500-100.
      https://pages.nist.gov/ElectionResultsReporting/
      Companion VIP CDF: SP 1500-101 (https://vip-specification.readthedocs.io/)

Preserves the raw shape of NIST classes:
  - BallotMeasureContest      (the contest wrapper for the measure)
  - BallotMeasureSelection    (the voter choices, typically Yes / No)
  - BallotMeasureType         (enum: initiative | referendum | recall | other)
  - GpUnit                    (geo-political unit — joined to OCD Division IDs
                               via the NIST ExternalIdentifier mechanism)

Sources unioned here: Ballotpedia, VIP feeds, state Secretary-of-State XML,
AI-extracted measures from meeting minutes. Each row keeps its provenance in
`source_system` so silver/public layers can resolve conflicts.

Linkage to OCD: every row carries `ocd_division_id` populated from
`GpUnit.ExternalIdentifier[Type=ocd-id]` so downstream models can join to the
canonical jurisdiction table without a separate crosswalk.
*/

WITH ballotpedia_measures AS (
    SELECT
        'ballotpedia'                                       AS source_system,
        bp.measure_id                                       AS source_record_id,
        bp.ocd_division_id                                  AS ocd_division_id,
        bp.election_date                                    AS election_date,
        bp.measure_number                                   AS contest_identifier,
        bp.measure_title                                    AS contest_name,
        bp.full_text                                        AS contest_full_text,
        bp.summary_text                                     AS contest_summary_text,
        bp.measure_type                                     AS ballot_measure_type_raw,
        bp.subject_areas                                    AS subject_areas,
        bp.source_url                                       AS source_url,
        bp.yes_votes                                        AS yes_votes,
        bp.no_votes                                         AS no_votes,
        bp.passed                                           AS passed,
        bp.source_ingested_at                               AS extracted_at
    FROM {{ ref('int_ballotpedia__measure_resolved') }} bp
    WHERE bp.ocd_division_id IS NOT NULL
),

vip_measures AS (
    SELECT
        'vip_cdf'                                           AS source_system,
        vip.contest_object_id                               AS source_record_id,
        vip.ocd_division_id                                 AS ocd_division_id,
        vip.election_date                                   AS election_date,
        vip.ballot_measure_identifier                       AS contest_identifier,
        vip.contest_name                                    AS contest_name,
        vip.full_text                                       AS contest_full_text,
        vip.summary_text                                    AS contest_summary_text,
        vip.ballot_measure_type                             AS ballot_measure_type_raw,
        vip.subject_areas                                   AS subject_areas,
        vip.source_url                                      AS source_url,
        NULL::bigint                                        AS yes_votes,
        NULL::bigint                                        AS no_votes,
        NULL::boolean                                       AS passed,
        vip.ingested_at                                     AS extracted_at
    FROM {{ source('bronze', 'bronze_vip_ballot_measures') }} vip
    WHERE vip.ocd_division_id IS NOT NULL
),

ai_extracted_measures AS (
    SELECT
        'ai_extraction'                                     AS source_system,
        ai.source_event_id || '_' || ai.measure_id          AS source_record_id,
        ai.ocd_division_id                                  AS ocd_division_id,
        (ai.measure_data->>'election_date')::date           AS election_date,
        ai.measure_data->>'identifier'                      AS contest_identifier,
        ai.measure_data->>'title'                           AS contest_name,
        ai.measure_data->>'full_text'                       AS contest_full_text,
        ai.measure_data->>'summary'                         AS contest_summary_text,
        ai.measure_data->>'type'                            AS ballot_measure_type_raw,
        ai.measure_data->>'subject_areas'                   AS subject_areas,
        ai.measure_data->>'source_url'                      AS source_url,
        NULL::bigint                                        AS yes_votes,
        NULL::bigint                                        AS no_votes,
        NULL::boolean                                       AS passed,
        ai.extracted_at                                     AS extracted_at
    FROM {{ ref('bronze_ballot_measures_from_ai') }} ai
    WHERE ai.ocd_division_id IS NOT NULL
),

unioned AS (
    SELECT * FROM ballotpedia_measures
    UNION ALL
    SELECT * FROM vip_measures
    UNION ALL
    SELECT * FROM ai_extracted_measures
)

SELECT
    -- Composite primary key
    source_system || ':' || source_record_id                AS ballot_measure_uid,

    -- Provenance
    source_system,
    source_record_id,
    source_url,
    extracted_at,

    -- NIST GpUnit linkage (OCD Division ID is the External Identifier we use)
    ocd_division_id,

    -- NIST Election context
    election_date,

    -- NIST BallotMeasureContest fields
    contest_identifier,
    contest_name,
    contest_full_text,
    contest_summary_text,
    subject_areas,

    -- NIST BallotMeasureType (kept raw at bronze; normalized in public layer)
    ballot_measure_type_raw,

    -- NIST ContestResults / BallotMeasureSelectionResults (sparse at bronze)
    yes_votes,
    no_votes,
    passed
FROM unioned
