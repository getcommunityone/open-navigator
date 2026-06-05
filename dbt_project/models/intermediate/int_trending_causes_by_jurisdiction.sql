{{
    config(
        materialized='table'
    )
}}

/*
    Intermediate model: Trending Causes by Jurisdiction

    Rolls up policy-decision counts by cause (the categorical primary_theme from the
    18-label COFOG civic-theme vocabulary) and jurisdiction. Feeds the trending_causes
    JSON in jurisdiction_state_aggregate (joined on state_code + UPPER(jurisdiction_name)).

    SOURCE  : event_policy_decision (public mart; bronze.bronze_policy_decisions →
              stg_policy_decisions, geography resolved via event_youtube_with_jurisdiction).
              Replaces the legacy, now-empty bronze_decisions path.
    CAUSE    : cause_category = primary_theme label; cause_code = COFOG code mapped via
              the policy_theme_cofog seed (mirrors packages/llm THEME_TO_COFOG).

    Decisions whose primary_theme is NULL (analyzed before the extractor shipped) are
    excluded, so this model is legitimately empty until re-analysis backfills themes.

    Output columns are pinned to the consumer contract:
      state_code, state, jurisdiction_name, jurisdiction_type, cause_category,
      cause_code, decision_count, unique_topics, most_recent_decision, cause_rank,
      sample_headlines (avg_days_old retained as a non-contract extra).
*/

WITH decisions AS (
    SELECT
        jurisdiction_id,
        jurisdiction_name,
        jurisdiction_type,
        state_code,
        state,
        primary_theme,
        headline,
        event_date
    FROM {{ ref('event_policy_decision') }}
    WHERE primary_theme IS NOT NULL
      AND jurisdiction_id IS NOT NULL
),

-- Label -> COFOG code (seed mirrors packages/llm THEME_TO_COFOG)
theme_cofog AS (
    SELECT
        primary_theme,
        cofog_code
    FROM {{ ref('policy_theme_cofog') }}
),

-- Aggregate by cause and jurisdiction
cause_aggregates AS (
    SELECT
        d.state_code,
        d.state,
        d.jurisdiction_name,
        COALESCE(d.jurisdiction_type, 'city') AS jurisdiction_type,

        -- Cause identifiers
        d.primary_theme AS cause_category,
        tc.cofog_code   AS cause_code,

        -- Decision counts
        COUNT(*) AS decision_count,
        COUNT(DISTINCT d.headline) AS unique_topics,

        -- Recency
        MAX(d.event_date) AS most_recent_decision,
        AVG(CURRENT_DATE - d.event_date)::DOUBLE PRECISION AS avg_days_old,

        -- Sample headlines (top 3 most recent)
        (ARRAY_AGG(d.headline ORDER BY d.event_date DESC NULLS LAST))[1:3]
            AS sample_headlines

    FROM decisions d
    LEFT JOIN theme_cofog tc ON tc.primary_theme = d.primary_theme
    GROUP BY
        d.state_code,
        d.state,
        d.jurisdiction_name,
        COALESCE(d.jurisdiction_type, 'city'),
        d.primary_theme,
        tc.cofog_code
),

-- Rank causes within each jurisdiction
ranked_causes AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY state_code, jurisdiction_name
            ORDER BY decision_count DESC, most_recent_decision DESC
        ) AS cause_rank
    FROM cause_aggregates
)

-- Top 10 trending causes per jurisdiction
SELECT
    state_code,
    state,
    jurisdiction_name,
    jurisdiction_type,
    cause_category,
    cause_code,
    decision_count,
    unique_topics,
    most_recent_decision,
    avg_days_old,
    sample_headlines,
    cause_rank
FROM ranked_causes
WHERE cause_rank <= 10
ORDER BY
    state_code,
    jurisdiction_name,
    cause_rank
