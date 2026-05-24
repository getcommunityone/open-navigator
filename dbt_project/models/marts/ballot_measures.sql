{{
    config(
        materialized='table',
        tags=['gold', 'ballot_measures', 'nist_vip', 'api']
    )
}}

/*
Public Ballot Measures — analyst- and API-ready table.

Schema is aligned with the NIST SP 1500-100 Election Results Reporting CDF
(ERR-CDF) and its VIP companion (SP 1500-101). Each column maps back to a
specific NIST class/field — see the mapping table below — and the table is
keyed by `ocd_division_id` so it joins natively to {{ ref('jurisdictions') }}.

NIST → Public column mapping
----------------------------
  BallotMeasureContest.ObjectId          -> ballot_measure_uid
  BallotMeasureContest.Name              -> contest_name
  BallotMeasureContest.BallotTitle       -> ballot_title
  BallotMeasureContest.FullText          -> full_text
  BallotMeasureContest.Summary           -> summary_text
  BallotMeasureContest.Type              -> ballot_measure_type   (enum below)
  BallotMeasureContest.OtherType         -> ballot_measure_type_other
  BallotMeasureContest.ElectoralDistrict -> ocd_division_id       (via GpUnit)
  BallotMeasureSelection.Selection       -> selection_choices     (Yes/No array)
  BallotMeasureSelectionResults.VoteCounts -> yes_votes, no_votes
  Election.StartDate                     -> election_date
  GpUnit.ExternalIdentifier[ocd-id]      -> ocd_division_id

BallotMeasureType enum (NIST):
  initiative | referendum | recall | other
*/

WITH bronze AS (
    SELECT *
    FROM {{ ref('bronze_ballot_measures_nist') }}
),

-- Resolve per-measure conflicts when multiple sources describe the same
-- measure. Prefer (1) official VIP feeds, (2) Ballotpedia, (3) AI extraction.
ranked AS (
    SELECT
        bronze.*,
        ROW_NUMBER() OVER (
            PARTITION BY ocd_division_id, election_date, contest_identifier
            ORDER BY CASE source_system
                WHEN 'vip_cdf'       THEN 1
                WHEN 'ballotpedia'   THEN 2
                WHEN 'ai_extraction' THEN 3
                ELSE 99
            END,
            extracted_at DESC
        ) AS source_priority_rank
    FROM bronze
),

deduped AS (
    SELECT *
    FROM ranked
    WHERE source_priority_rank = 1
),

-- Normalize raw type strings to the NIST BallotMeasureType enumeration.
normalized AS (
    SELECT
        d.*,
        CASE
            WHEN LOWER(d.ballot_measure_type_raw) IN (
                'initiative', 'citizen initiative', 'initiated statute',
                'initiated constitutional amendment'
            ) THEN 'initiative'
            WHEN LOWER(d.ballot_measure_type_raw) IN (
                'referendum', 'veto referendum', 'legislative referral',
                'legislatively referred', 'bond measure', 'bond', 'measure'
            ) THEN 'referendum'
            WHEN LOWER(d.ballot_measure_type_raw) IN (
                'recall'
            ) THEN 'recall'
            ELSE 'other'
        END AS ballot_measure_type,

        -- Preserve the precise upstream label when we fall back to 'other'
        CASE
            WHEN LOWER(d.ballot_measure_type_raw) NOT IN (
                'initiative', 'citizen initiative', 'initiated statute',
                'initiated constitutional amendment',
                'referendum', 'veto referendum', 'legislative referral',
                'legislatively referred', 'bond measure', 'bond', 'measure',
                'recall'
            ) THEN d.ballot_measure_type_raw
            ELSE NULL
        END AS ballot_measure_type_other
    FROM deduped d
)

SELECT
    -- Identity
    ballot_measure_uid,

    -- OCD linkage (joins to {{ ref('jurisdictions') }} on ocd_division_id)
    ocd_division_id,

    -- Election context
    election_date,

    -- NIST BallotMeasureContest
    contest_identifier,
    contest_name                                    AS ballot_title,
    contest_name,
    contest_full_text                               AS full_text,
    contest_summary_text                            AS summary_text,
    subject_areas,

    -- NIST BallotMeasureType (enum) + precise upstream label
    ballot_measure_type,
    ballot_measure_type_other,

    -- NIST BallotMeasureSelection — at the public layer we expose the
    -- canonical Yes/No choices (the overwhelming majority case). Multi-choice
    -- selections live in a separate `ballot_measure_selections` long-format
    -- table when present.
    ARRAY['Yes', 'No']::text[]                      AS selection_choices,

    -- NIST BallotMeasureSelectionResults
    yes_votes,
    no_votes,
    CASE
        WHEN yes_votes IS NOT NULL AND no_votes IS NOT NULL
            THEN yes_votes + no_votes
        ELSE NULL
    END                                             AS total_votes,
    passed,

    -- Provenance
    source_system,
    source_url,
    extracted_at
FROM normalized
