{{
    config(
        materialized='table',
        unique_key=['level', 'state_code', 'county', 'city']
    )
}}

-- depends_on: {{ ref('bronze_organizations_nonprofits') }}

/*
    Stats Aggregates - Multi-level statistics with trending causes
    
    Builds stats_aggregates table with:
    - Nonprofit counts and financials by geography
    - Event counts, contact counts, bill counts
    - Trending causes (JSON) based on decisions in last 90 days
    
    Levels: national, state, county, city, jurisdiction
    
    Data Sources:
    - bronze_organizations_nonprofits: Nonprofit counts, revenue, assets (1.95M orgs)
    - bronze_events: Meeting/event counts
    - bronze_contacts: Contact counts
    - bronze_bills: Bill counts
    - int_trending_causes_by_jurisdiction: Trending causes by jurisdiction
*/

-- CTE for base nonprofits data (extract ref() to top level)
WITH base_nonprofits AS (
    SELECT * FROM {{ ref('bronze_organizations_nonprofits') }}
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
    FROM {{ source('bronze', 'bronze_events') }}
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

contact_stats AS (
    -- Count contacts by state (via events)
    SELECT
        e.state_code,
        COUNT(DISTINCT c.id) as contacts_count
    FROM {{ source('bronze', 'bronze_contacts') }} c
    JOIN {{ source('bronze', 'bronze_events') }} e ON c.source_event_id = e.id
    WHERE e.state_code IS NOT NULL
    GROUP BY e.state_code
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
        (SELECT SUM(nonprofits_count) FROM nonprofit_stats)::INTEGER as nonprofits_count,
        (SELECT SUM(events_count) FROM event_stats)::INTEGER as events_count,
        (SELECT SUM(bills_count) FROM bill_stats)::INTEGER as bills_count,
        (SELECT SUM(contacts_count) FROM contact_stats)::INTEGER as contacts_count,
        (SELECT SUM(total_revenue) FROM nonprofit_stats) as total_revenue,
        (SELECT SUM(total_assets) FROM nonprofit_stats) as total_assets,
        
        NULL::JSONB as trending_causes,
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
        COALESCE((SELECT contacts_count FROM contact_stats WHERE state_code = nps.state_code), 0)::INTEGER as contacts_count,
        SUM(nps.total_revenue) as total_revenue,
        SUM(nps.total_assets) as total_assets,
        
        NULL::JSONB as trending_causes,
        
        CURRENT_TIMESTAMP as last_updated
    FROM nonprofit_stats nps
    GROUP BY nps.state_code
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
        0 as contacts_count,
        nps.total_revenue,
        nps.total_assets,
        
        NULL::JSONB as trending_causes,
        CURRENT_TIMESTAMP as last_updated
    FROM nonprofit_stats nps
    LEFT JOIN county_event_stats ces 
        ON nps.county = ces.county AND nps.state_code = ces.state_code
    WHERE nps.county IS NOT NULL
),

-- City level stats (FIX: Use actual city nonprofit counts!)
city_stats AS (
    SELECT
        'city' as level,
        es.state_code,
        NULL::VARCHAR(50) as state,
        NULL::VARCHAR(100) as county,
        es.city,
        
        0 as jurisdictions_count,
        0 as school_districts_count,
        -- FIX: Use actual city nonprofit count, not state total!
        COALESCE(ncs.nonprofits_count, 0)::INTEGER as nonprofits_count,
        es.events_count::INTEGER,
        0 as bills_count,
        0 as contacts_count,
        COALESCE(ncs.total_revenue, 0) as total_revenue,
        COALESCE(ncs.total_assets, 0) as total_assets,
        
        NULL::JSONB as trending_causes,
        
        CURRENT_TIMESTAMP as last_updated
    FROM event_stats es
    LEFT JOIN nonprofit_city_stats ncs 
        ON UPPER(es.city) = UPPER(ncs.city) AND es.state_code = ncs.state_code
    WHERE es.city IS NOT NULL
)

-- Combine all levels
SELECT * FROM national_stats
UNION ALL
SELECT * FROM state_stats
UNION ALL
SELECT * FROM county_stats
UNION ALL
SELECT * FROM city_stats
