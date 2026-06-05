{{
    config(
        materialized='table',
        unique_key=['level', 'state_code', 'county', 'city']
    )
}}

/*
    Stats Aggregates - Multi-level statistics with trending causes
    
    Builds jurisdiction_state_aggregate table with:
    - Nonprofit counts and financials by geography
    - Event counts, person counts, leader counts, bill counts
    - Trending causes (JSON) based on decisions in last 90 days

    Levels: national, state, county, city, jurisdiction

    Data Sources:
    - bronze_organizations_nonprofits: Nonprofit counts, revenue, assets (1.95M orgs)
    - bronze_events: Meeting/event counts
    - mdm_person: Person counts (people in the geography)
    - contact_official + mdm_bridge_person_organization: Leader counts
      (elected/government officials + nonprofit board members/leaders)
    - bronze_bills: Bill counts
    - int_trending_causes_by_jurisdiction: Trending causes by jurisdiction
*/

-- CTE for base nonprofits data (use source, not ref)
WITH base_nonprofits AS (
    SELECT * FROM {{ source('bronze', 'bronze_organizations_nonprofits') }}
),

nonprofit_stats AS (
    -- Aggregate nonprofit data by state and county
    SELECT
        state_code,
        census_county_name as county,
        COUNT(*) as nonprofits_count,
        COALESCE(SUM(irs_revenue_amt), 0) as total_revenue,
        COALESCE(SUM(irs_asset_amt), 0) as total_assets
    FROM base_nonprofits
    WHERE state_code IS NOT NULL
    GROUP BY state_code, census_county_name
),

nonprofit_city_stats AS (
    -- Aggregate nonprofit data by city (NEW!)
    SELECT
        state_code,
        city,
        COUNT(*) as nonprofits_count,
        COALESCE(SUM(irs_revenue_amt), 0) as total_revenue,
        COALESCE(SUM(irs_asset_amt), 0) as total_assets
    FROM base_nonprofits
    WHERE state_code IS NOT NULL AND city IS NOT NULL AND city != ''
    GROUP BY state_code, city
),

city_to_county_map AS (
    -- Map cities to their primary county (most nonprofits in that county)
    -- FIX: Order by COUNT DESC to pick the county with most orgs, not alphabetically!
    WITH city_county_counts AS (
        SELECT 
            state_code,
            city,
            census_county_name,
            COUNT(*) as org_count
        FROM base_nonprofits
        WHERE city IS NOT NULL AND city != '' 
          AND census_county_name IS NOT NULL
        GROUP BY state_code, city, census_county_name
    )
    SELECT DISTINCT ON (state_code, city)
        state_code,
        city,
        census_county_name as primary_county
    FROM city_county_counts
    ORDER BY state_code, city, org_count DESC  -- Largest county first!
),

event_stats AS (
    -- Aggregate event counts by state and city
    SELECT
        state_code,
        city,
        COUNT(*) as events_count
    FROM {{ source('bronze', 'bronze_events_localview') }}
    WHERE state_code IS NOT NULL
    GROUP BY state_code, city
),

county_event_stats AS (
    -- Pre-aggregate event counts by county (OPTIMIZATION + CASE-INSENSITIVE!)
    SELECT
        c2c.state_code,
        c2c.primary_county as county,
        SUM(es.events_count) as events_count
    FROM event_stats es
    JOIN city_to_county_map c2c 
        ON UPPER(es.city) = UPPER(c2c.city) AND es.state_code = c2c.state_code
    GROUP BY c2c.state_code, c2c.primary_county
),

-- Person counts from the MDM person master, by geography.
-- mdm_person exposes lowercase `city_norm` and `state_code`; there is no county column.
person_stats AS (
    SELECT
        state_code,
        city_norm,
        COUNT(*) as persons_count
    FROM {{ ref('mdm_person') }}
    WHERE state_code IS NOT NULL
    GROUP BY state_code, city_norm
),

-- Leader counts. Two DIFFERENT id namespaces that CANNOT be deduped across each other,
-- so we SUM the two counts rather than UNION-distinct:
--   1. contact_official: elected + government officials
--      (keyed by state_code + jurisdiction text place name).
--   2. mdm_bridge_person_organization: nonprofit board members / leaders
--      (DISTINCT officer_person_uid where they hold a leadership flag,
--       keyed by state_code + city_norm).
leader_official_stats AS (
    SELECT
        state_code,
        jurisdiction,
        COUNT(*) as officials_count
    FROM {{ ref('contact_official') }}
    WHERE state_code IS NOT NULL
    GROUP BY state_code, jurisdiction
),

leader_board_stats AS (
    SELECT
        state_code,
        city_norm,
        COUNT(DISTINCT officer_person_uid) as board_count
    FROM {{ ref('mdm_bridge_person_organization') }}
    WHERE state_code IS NOT NULL
      AND (is_officer OR is_director_trustee OR is_key_employee OR is_institutional_trustee)
    GROUP BY state_code, city_norm
),

bill_stats AS (
    -- Count bills by state
    SELECT
        LEFT(jurisdiction, 2) as state_code,
        COUNT(*) as bills_count
    FROM {{ source('bronze', 'bronze_bills') }}
    WHERE jurisdiction IS NOT NULL
    GROUP BY LEFT(jurisdiction, 2)
),

decision_stats AS (
    -- Count decisions by state and city
    SELECT
        e.state_code,
        e.city,
        COUNT(DISTINCT d.id) as decisions_count
    FROM {{ source('bronze', 'bronze_decisions') }} d
    JOIN {{ source('bronze', 'bronze_events_localview') }} e ON d.source_event_id = e.event_id
    WHERE e.state_code IS NOT NULL
    GROUP BY e.state_code, e.city
),

-- Trending causes aggregated by jurisdiction (from dbt intermediate model)
trending_causes_data AS (
    SELECT
        state_code,
        state,
        jurisdiction_name,
        jurisdiction_type,
        -- Build JSON array of trending causes for each jurisdiction
        jsonb_agg(
            jsonb_build_object(
                'cause', cause_category,
                'code', cause_code,
                'decision_count', decision_count,
                'topics', unique_topics,
                'most_recent', most_recent_decision::TEXT,
                'rank', cause_rank,
                'sample_headlines', sample_headlines
            ) ORDER BY cause_rank
        ) as trending_causes
    FROM {{ ref('int_trending_causes_by_jurisdiction') }}
    GROUP BY state_code, state, jurisdiction_name, jurisdiction_type
),

-- Aggregate trending causes by state (all cities in a state)
state_trending_causes AS (
    SELECT
        state_code,
        -- Aggregate all causes from all jurisdictions in the state
        jsonb_agg(
            jsonb_build_object(
                'cause', cause_category,
                'code', cause_code,
                'decision_count', decision_count,
                'jurisdiction', jurisdiction_name
            ) ORDER BY decision_count DESC
        ) as all_causes,
        -- Get top 10 most common causes across state
        (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'cause', cause,
                    'decision_count', total_count,
                    'jurisdictions', jurisdictions
                ) ORDER BY total_count DESC
            )
            FROM (
                SELECT 
                    cause_category as cause,
                    SUM(decision_count) as total_count,
                    COUNT(DISTINCT jurisdiction_name) as jurisdictions
                FROM {{ ref('int_trending_causes_by_jurisdiction') }}
                WHERE state_code = tc.state_code
                GROUP BY cause_category
                ORDER BY total_count DESC
                LIMIT 10
            ) top_causes
        ) as trending_causes
    FROM {{ ref('int_trending_causes_by_jurisdiction') }} tc
    GROUP BY state_code
),

-- National trending causes (aggregate across all states)
national_trending_causes AS (
    SELECT
        jsonb_agg(
            jsonb_build_object(
                'cause', cause,
                'decision_count', total_count,
                'states', states
            ) ORDER BY total_count DESC
        ) as trending_causes
    FROM (
        SELECT 
            cause_category as cause,
            SUM(decision_count) as total_count,
            COUNT(DISTINCT state_code) as states
        FROM {{ ref('int_trending_causes_by_jurisdiction') }}
        GROUP BY cause_category
        ORDER BY total_count DESC
        LIMIT 10
    ) top_national_causes
),

-- National level stats
national_stats AS (
    SELECT
        'national' as level,
        NULL::VARCHAR(2) as state_code,
        NULL::VARCHAR(50) as state,
        NULL::VARCHAR(100) as county,
        NULL::VARCHAR(100) as city,
        
        0 as jurisdictions_count,
        0 as school_districts_count,
        -- COALESCE every SUM to 0: an empty source set makes SUM() return NULL, which
        -- would violate the not_null grain test (a jurisdiction with zero of X reads 0, not NULL).
        COALESCE((SELECT SUM(nonprofits_count) FROM nonprofit_stats), 0)::INTEGER as nonprofits_count,
        COALESCE((SELECT SUM(events_count) FROM event_stats), 0)::INTEGER as events_count,
        COALESCE((SELECT SUM(bills_count) FROM bill_stats), 0)::INTEGER as bills_count,
        COALESCE((SELECT SUM(persons_count) FROM person_stats), 0)::INTEGER as persons_count,
        -- leaders = SUM of two non-dedupable id namespaces (officials + nonprofit board)
        (
            COALESCE((SELECT SUM(officials_count) FROM leader_official_stats), 0)
            + COALESCE((SELECT SUM(board_count) FROM leader_board_stats), 0)
        )::INTEGER as leaders_count,
        COALESCE((SELECT SUM(decisions_count) FROM decision_stats), 0)::INTEGER as decisions_count,
        (SELECT SUM(total_revenue) FROM nonprofit_stats) as total_revenue,
        (SELECT SUM(total_assets) FROM nonprofit_stats) as total_assets,
        
        -- National trending causes
        (SELECT trending_causes FROM national_trending_causes LIMIT 1) as trending_causes,
        CURRENT_TIMESTAMP as last_updated
),

-- State level stats
state_stats AS (
    SELECT
        'state' as level,
        nps.state_code,
        NULL::VARCHAR(50) as state,
        NULL::VARCHAR(100) as county,
        NULL::VARCHAR(100) as city,
        
        0 as jurisdictions_count,
        0 as school_districts_count,
        SUM(nps.nonprofits_count)::INTEGER as nonprofits_count,
        COALESCE((SELECT SUM(events_count) FROM event_stats WHERE state_code = nps.state_code), 0)::INTEGER as events_count,
        COALESCE((SELECT bills_count FROM bill_stats WHERE state_code = nps.state_code), 0)::INTEGER as bills_count,
        COALESCE((SELECT SUM(persons_count) FROM person_stats WHERE state_code = nps.state_code), 0)::INTEGER as persons_count,
        -- leaders = SUM of two non-dedupable id namespaces (officials + nonprofit board)
        (
            COALESCE((SELECT SUM(officials_count) FROM leader_official_stats WHERE state_code = nps.state_code), 0)
            + COALESCE((SELECT SUM(board_count) FROM leader_board_stats WHERE state_code = nps.state_code), 0)
        )::INTEGER as leaders_count,
        COALESCE((SELECT SUM(decisions_count) FROM decision_stats WHERE state_code = nps.state_code), 0)::INTEGER as decisions_count,
        SUM(nps.total_revenue) as total_revenue,
        SUM(nps.total_assets) as total_assets,
        
        -- State-level trending causes (aggregated from all jurisdictions in state)
        stc.trending_causes,
        
        CURRENT_TIMESTAMP as last_updated
    FROM nonprofit_stats nps
    LEFT JOIN state_trending_causes stc ON nps.state_code = stc.state_code
    GROUP BY nps.state_code, stc.trending_causes
),

-- County level stats (FIX: Use pre-aggregated events!)
county_stats AS (
    SELECT
        'county' as level,
        nps.state_code,
        NULL::VARCHAR(50) as state,
        nps.county,
        NULL::VARCHAR(100) as city,
        
        0 as jurisdictions_count,
        0 as school_districts_count,
        nps.nonprofits_count::INTEGER,
        COALESCE(ces.events_count, 0)::INTEGER as events_count,
        0 as bills_count,
        -- TODO: county persons/leaders need a city->county roll-up
        -- (mdm_person and the bridge have no county column).
        0 as persons_count,
        0 as leaders_count,
        0 as decisions_count,
        nps.total_revenue,
        nps.total_assets,
        
        -- County trending causes (aggregate from jurisdictions in this county)
        -- Note: We don't have county-level decisions, so this will be NULL for now
        NULL::JSONB as trending_causes,
        CURRENT_TIMESTAMP as last_updated
    FROM nonprofit_stats nps
    LEFT JOIN county_event_stats ces 
        ON nps.county = ces.county AND nps.state_code = ces.state_code
    WHERE nps.county IS NOT NULL
),

-- City-grain key set. BUGFIX: the city grain was previously anchored on
-- event_stats, so a city only got a row if it had localview events. Cities with
-- nonprofits/persons/leaders but no events (e.g. Tuscaloosa, AL — 740 nonprofits,
-- ~29k persons, 0 events) were dropped entirely, and the API then fell back to
-- statewide numbers. Anchor on the UNION of every city-grained metric instead so
-- a row exists whenever ANY metric is present. Keyed on UPPER(city) for a single
-- canonical grain across the differently-cased sources.
city_keys AS (
    SELECT state_code, UPPER(city) AS city_upper FROM nonprofit_city_stats WHERE city IS NOT NULL
    UNION
    SELECT state_code, UPPER(city) AS city_upper FROM event_stats WHERE city IS NOT NULL
    UNION
    SELECT state_code, UPPER(city_norm) AS city_upper FROM person_stats WHERE city_norm IS NOT NULL
    UNION
    SELECT state_code, UPPER(city) AS city_upper FROM decision_stats WHERE city IS NOT NULL
    UNION
    SELECT state_code, UPPER(city_norm) AS city_upper FROM leader_board_stats WHERE city_norm IS NOT NULL
),

-- City level stats (union-anchored). Each metric is re-aggregated to the
-- (state_code, UPPER(city)) grain inside its join so a single key cannot fan out
-- across differently-cased source rows, keeping every join strictly 1:1.
city_stats AS (
    SELECT
        'city' as level,
        ck.state_code,
        -- FIX: populate full state name alongside state_code (naming convention).
        {{ state_code_to_name('ck.state_code') }}::VARCHAR(50) as state,
        -- FIX: carry the city's primary county so the grain is genuinely
        -- (level, state_code, county, city) and distinct same-named places in
        -- different counties cannot merge into one row.
        c2c.primary_county::VARCHAR(100) as county,
        INITCAP(ck.city_upper)::VARCHAR(100) as city,

        0 as jurisdictions_count,
        0 as school_districts_count,
        COALESCE(ncs.nonprofits_count, 0)::INTEGER as nonprofits_count,
        COALESCE(es.events_count, 0)::INTEGER as events_count,
        0 as bills_count,
        COALESCE(ps.persons_count, 0)::INTEGER as persons_count,
        -- leaders = SUM of two non-dedupable id namespaces (officials + nonprofit board)
        (COALESCE(los.officials_count, 0) + COALESCE(lbs.board_count, 0))::INTEGER as leaders_count,
        COALESCE(ds.decisions_count, 0)::INTEGER as decisions_count,
        COALESCE(ncs.total_revenue, 0) as total_revenue,
        COALESCE(ncs.total_assets, 0) as total_assets,

        -- City-level trending causes (from jurisdiction-specific decisions)
        tcd.trending_causes,

        CURRENT_TIMESTAMP as last_updated
    FROM city_keys ck
    LEFT JOIN (
        SELECT DISTINCT ON (state_code, UPPER(city))
            state_code, UPPER(city) AS city_upper, primary_county
        FROM city_to_county_map
        ORDER BY state_code, UPPER(city)
    ) c2c ON c2c.state_code = ck.state_code AND c2c.city_upper = ck.city_upper
    LEFT JOIN (
        SELECT state_code, UPPER(city) AS city_upper,
               SUM(nonprofits_count) AS nonprofits_count,
               SUM(total_revenue) AS total_revenue,
               SUM(total_assets) AS total_assets
        FROM nonprofit_city_stats GROUP BY state_code, UPPER(city)
    ) ncs ON ncs.state_code = ck.state_code AND ncs.city_upper = ck.city_upper
    LEFT JOIN (
        SELECT state_code, UPPER(city) AS city_upper, SUM(events_count) AS events_count
        FROM event_stats WHERE city IS NOT NULL GROUP BY state_code, UPPER(city)
    ) es ON es.state_code = ck.state_code AND es.city_upper = ck.city_upper
    LEFT JOIN (
        SELECT state_code, UPPER(city_norm) AS city_upper, SUM(persons_count) AS persons_count
        FROM person_stats GROUP BY state_code, UPPER(city_norm)
    ) ps ON ps.state_code = ck.state_code AND ps.city_upper = ck.city_upper
    LEFT JOIN (
        SELECT state_code, UPPER(city) AS city_upper, SUM(decisions_count) AS decisions_count
        FROM decision_stats GROUP BY state_code, UPPER(city)
    ) ds ON ds.state_code = ck.state_code AND ds.city_upper = ck.city_upper
    LEFT JOIN (
        SELECT state_code, UPPER(jurisdiction) AS city_upper, SUM(officials_count) AS officials_count
        FROM leader_official_stats GROUP BY state_code, UPPER(jurisdiction)
    ) los ON los.state_code = ck.state_code AND los.city_upper = ck.city_upper
    LEFT JOIN (
        SELECT state_code, UPPER(city_norm) AS city_upper, SUM(board_count) AS board_count
        FROM leader_board_stats GROUP BY state_code, UPPER(city_norm)
    ) lbs ON lbs.state_code = ck.state_code AND lbs.city_upper = ck.city_upper
    LEFT JOIN (
        -- collapse same-named jurisdictions (multiple types) to one jsonb per city
        SELECT state_code, UPPER(jurisdiction_name) AS city_upper,
               (jsonb_agg(trending_causes ORDER BY jurisdiction_name))->0 AS trending_causes
        FROM trending_causes_data GROUP BY state_code, UPPER(jurisdiction_name)
    ) tcd ON tcd.state_code = ck.state_code AND tcd.city_upper = ck.city_upper
)

-- Combine all levels
SELECT * FROM national_stats
UNION ALL
SELECT * FROM state_stats
UNION ALL
SELECT * FROM county_stats
UNION ALL
SELECT * FROM city_stats
