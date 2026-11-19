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

    Sources unioned here: Ballotpedia, VIP feeds, AI-extracted measures.
    `bronze_vip_ballot_measures` is optional locally (#486): when the raw VIP
    landing table is missing, the VIP leg contributes zero rows so the model
    still builds.

    source() is called before the guard so dbt records the dependency at parse time.
*/

{%- set vip_src = source('bronze', 'bronze_vip_ballot_measures') -%}
{%- set vip_exists = execute and adapter.get_relation(
        database=vip_src.database,
        schema=vip_src.schema,
        identifier=vip_src.identifier) is not none -%}

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
    {% if vip_exists %}
    SELECT
        'vip_cdf'                                           AS source_system,
        vip.contest_object_id                               AS source_record_id,
        vip.ocd_division_id                                 AS ocd_division_id,
        vip.election_date::text                             AS election_date,
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
    FROM {{ vip_src }} vip
    WHERE vip.ocd_division_id IS NOT NULL
    {% else %}
    -- Typed empty set matching ballotpedia_measures (VIP landing table absent locally).
    SELECT * FROM ballotpedia_measures WHERE false
    {% endif %}
),

ai_extracted_measures AS (
    SELECT
        'ai_extraction'                                     AS source_system,
        ai.source_event_id || '_' || ai.measure_id          AS source_record_id,
        ai.ocd_division_id                                  AS ocd_division_id,
        ai.measure_data->>'election_date'                   AS election_date,
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
    source_system || ':' || source_record_id                AS ballot_measure_uid,
    source_system,
    source_record_id,
    source_url,
    extracted_at,
    ocd_division_id,
    election_date,
    contest_identifier,
    contest_name,
    contest_full_text,
    contest_summary_text,
    subject_areas,
    ballot_measure_type_raw,
    yes_votes,
    no_votes,
    passed
FROM unioned
