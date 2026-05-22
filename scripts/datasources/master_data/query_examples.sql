-- ============================================================================
-- Master Data Management: Common Query Patterns
-- ============================================================================
-- This file contains practical SQL queries for working with the master data
-- tables created by the jurisdiction consolidation strategy.
-- ============================================================================

-- ============================================================================
-- 1. FINDING MATCHES: Get all linked data for an entity
-- ============================================================================

-- Find all data sources for "Anchorage School District"
SELECT 
    mj.id as master_id,
    mj.canonical_name,
    mj.state_code,
    mj.nces_id,
    mj.primary_website,
    mj.source_count,
    -- Source IDs
    jc.org_location_id,
    jc.wikidata_id,
    jc.search_id,
    jc.details_search_id,
    -- Match quality
    jc.match_method,
    jc.match_confidence
FROM master_jurisdictions mj
JOIN jurisdiction_crosswalk jc ON mj.id = jc.master_jurisdiction_id
WHERE mj.canonical_name ILIKE '%anchorage%'
  AND mj.state_code = 'AK'
  AND mj.primary_type = 'school_district';


-- ============================================================================
-- 2. REVERSE LOOKUP: Find master record from any source ID
-- ============================================================================

-- Given an organization_location ID, find master record
SELECT 
    mj.*,
    jc.match_method,
    jc.match_confidence
FROM master_jurisdictions mj
JOIN jurisdiction_crosswalk jc ON mj.id = jc.master_jurisdiction_id
WHERE jc.org_location_id = 12345;  -- Replace with actual ID

-- Given a jurisdiction ID, find all linked sources
SELECT 
    mj.canonical_name,
    ol.name as org_name,
    ol.website as org_website,
    jw.official_website as wiki_website,
    jc.match_method
FROM jurisdiction_crosswalk jc
JOIN master_jurisdictions mj ON jc.master_jurisdiction_id = mj.id
LEFT JOIN organization_location ol ON jc.org_location_id = ol.id
LEFT JOIN jurisdictions_wikidata jw ON jc.wikidata_id = jw.id
WHERE jc.details_search_id = 67890;  -- Replace with actual ID


-- ============================================================================
-- 3. DATA QUALITY: Find high-quality vs low-quality records
-- ============================================================================

-- Best quality jurisdictions (multiple sources, high completeness)
SELECT 
    canonical_name,
    state_code,
    primary_type,
    source_count,
    data_completeness_score,
    array_length(all_websites, 1) as website_count
FROM master_jurisdictions
WHERE data_completeness_score >= 0.75
  AND source_count >= 2
ORDER BY data_completeness_score DESC, source_count DESC
LIMIT 50;

-- Low quality jurisdictions (single source, low completeness)
SELECT 
    canonical_name,
    state_code,
    primary_type,
    source_count,
    data_completeness_score
FROM master_jurisdictions
WHERE data_completeness_score < 0.50
  OR source_count = 1
ORDER BY data_completeness_score ASC
LIMIT 50;


-- ============================================================================
-- 4. UNMATCH DETECTION: Find records that couldn't be matched
-- ============================================================================

-- Unmatched school districts from organization_location
SELECT 
    ol.id,
    ol.name,
    ol.city,
    ol.state,
    ol.website,
    ol.source_id as nces_id
FROM organization_location ol
LEFT JOIN jurisdiction_crosswalk jc ON ol.id = jc.org_location_id
WHERE jc.id IS NULL
  AND ol.organization_type = 'school_district'
ORDER BY ol.state, ol.city;

-- Unmatched jurisdictions from jurisdiction
SELECT 
    js.id,
    js.name,
    js.type,
    js.state_code,
    js.county,
    js.geoid,
    js.fips_code
FROM jurisdiction js
LEFT JOIN jurisdiction_crosswalk jc ON js.id = jc.search_id
WHERE jc.id IS NULL
  AND js.type IN ('city', 'county')
ORDER BY js.state_code, js.name
LIMIT 100;


-- ============================================================================
-- 5. DUPLICATE DETECTION: Find potential duplicates
-- ============================================================================

-- Find jurisdictions with same domain (potential duplicates)
SELECT 
    dr.domain,
    COUNT(*) as entity_count,
    array_agg(DISTINCT dr.jurisdiction_name) as names,
    array_agg(DISTINCT dr.state_code) as states,
    array_agg(DISTINCT dr.source_table) as sources
FROM domain_registry dr
GROUP BY dr.domain
HAVING COUNT(*) > 1
ORDER BY entity_count DESC;

-- Find similar jurisdiction names in same state (fuzzy duplicates)
WITH jurisdiction_pairs AS (
    SELECT 
        a.id as id_a,
        b.id as id_b,
        a.canonical_name as name_a,
        b.canonical_name as name_b,
        a.state_code,
        similarity(a.canonical_name, b.canonical_name) as similarity_score
    FROM master_jurisdictions a
    JOIN master_jurisdictions b ON a.state_code = b.state_code AND a.id < b.id
    WHERE a.primary_type = b.primary_type
)
SELECT *
FROM jurisdiction_pairs
WHERE similarity_score >= 0.8  -- Adjust threshold as needed
ORDER BY state_code, similarity_score DESC;


-- ============================================================================
-- 6. DOMAIN ANALYSIS: Website and domain patterns
-- ============================================================================

-- Most common top-level domains
SELECT 
    SUBSTRING(domain FROM '\.([^.]+)$') as tld,
    COUNT(*) as domain_count,
    COUNT(DISTINCT state_code) as states_count
FROM domain_registry
GROUP BY tld
ORDER BY domain_count DESC
LIMIT 20;

-- School districts with .org vs .k12 vs other domains
SELECT 
    CASE 
        WHEN domain LIKE '%.org' THEN '.org'
        WHEN domain LIKE '%.k12.%.us' THEN '.k12.[state].us'
        WHEN domain LIKE '%.edu' THEN '.edu'
        WHEN domain LIKE '%.com' THEN '.com'
        ELSE 'other'
    END as domain_pattern,
    COUNT(*) as count
FROM domain_registry
WHERE organization_type = 'school_district'
GROUP BY domain_pattern
ORDER BY count DESC;


-- ============================================================================
-- 7. GEOGRAPHIC COVERAGE: Match rates by state/region
-- ============================================================================

-- Match rate by state for school districts
SELECT 
    ol.state,
    COUNT(*) as total_school_districts,
    COUNT(jc.id) as matched,
    ROUND(100.0 * COUNT(jc.id) / COUNT(*), 2) as match_rate_pct,
    COUNT(DISTINCT jc.match_method) as match_methods_used
FROM organization_location ol
LEFT JOIN jurisdiction_crosswalk jc ON ol.id = jc.org_location_id
WHERE ol.organization_type = 'school_district'
GROUP BY ol.state
ORDER BY match_rate_pct DESC;

-- Jurisdiction coverage by type
SELECT 
    mj.primary_type,
    mj.state_code,
    COUNT(*) as count,
    AVG(source_count) as avg_sources,
    AVG(data_completeness_score) as avg_quality
FROM master_jurisdictions mj
GROUP BY mj.primary_type, mj.state_code
ORDER BY mj.primary_type, count DESC;


-- ============================================================================
-- 8. MATCH METHOD ANALYSIS: Which strategies work best
-- ============================================================================

-- Match method effectiveness
SELECT 
    match_method,
    COUNT(*) as match_count,
    AVG(match_confidence)::DECIMAL(3,2) as avg_confidence,
    MIN(match_confidence)::DECIMAL(3,2) as min_confidence,
    MAX(match_confidence)::DECIMAL(3,2) as max_confidence
FROM jurisdiction_crosswalk
WHERE match_method IS NOT NULL
GROUP BY match_method
ORDER BY match_count DESC;

-- Multi-method matches (highest confidence)
SELECT 
    mj.canonical_name,
    mj.state_code,
    COUNT(DISTINCT jc.match_method) as method_count,
    array_agg(DISTINCT jc.match_method) as methods,
    AVG(jc.match_confidence) as avg_confidence
FROM master_jurisdictions mj
JOIN jurisdiction_crosswalk jc ON mj.id = jc.master_jurisdiction_id
GROUP BY mj.id, mj.canonical_name, mj.state_code
HAVING COUNT(DISTINCT jc.match_method) > 1
ORDER BY method_count DESC, avg_confidence DESC
LIMIT 50;


-- ============================================================================
-- 9. ENRICHMENT OPPORTUNITIES: Where to add more data
-- ============================================================================

-- School districts with website but no wikidata enrichment
SELECT 
    ol.name,
    ol.state,
    ol.website,
    ol.source_id as nces_id,
    jc.wikidata_id
FROM organization_location ol
LEFT JOIN jurisdiction_crosswalk jc ON ol.id = jc.org_location_id
WHERE ol.organization_type = 'school_district'
  AND ol.website IS NOT NULL
  AND jc.wikidata_id IS NULL
ORDER BY ol.state, ol.name
LIMIT 100;

-- Jurisdictions missing websites (enrichment targets)
SELECT 
    mj.canonical_name,
    mj.state_code,
    mj.primary_type,
    mj.source_count,
    mj.primary_website,
    array_length(mj.all_websites, 1) as website_count
FROM master_jurisdictions mj
WHERE mj.primary_website IS NULL
  AND mj.source_count >= 2  -- Multiple sources but no website
ORDER BY mj.source_count DESC, mj.state_code;


-- ============================================================================
-- 10. EXPORT FOR ANALYSIS: Create materialized views
-- ============================================================================

-- Create a denormalized view for easy querying
CREATE MATERIALIZED VIEW IF NOT EXISTS master_jurisdictions_full AS
SELECT 
    mj.id as master_id,
    mj.canonical_name,
    mj.state_code,
    mj.state,
    mj.county,
    mj.city,
    mj.primary_type,
    mj.nces_id,
    mj.fips_code,
    mj.geoid,
    mj.primary_website,
    mj.source_count,
    mj.data_completeness_score,
    
    -- Organizations data
    ol.id as org_id,
    ol.name as org_name,
    ol.website as org_website,
    ol.address as org_address,
    ol.telephone as org_phone,
    ol.organization_type,
    
    -- Wikidata
    jw.id as wiki_id,
    jw.wikidata_id,
    jw.official_website as wiki_website,
    jw.population as wiki_population,
    jw.youtube_channel_url,
    jw.facebook_url,
    jw.twitter_url,
    
    -- Details
    jd.id as details_id,
    jd.website_url as details_website,
    jd.youtube_channels,
    jd.in_localview,
    
    -- Match metadata
    jc.match_method,
    jc.match_confidence

FROM master_jurisdictions mj
JOIN jurisdiction_crosswalk jc ON mj.id = jc.master_jurisdiction_id
LEFT JOIN organization_location ol ON jc.org_location_id = ol.id
LEFT JOIN jurisdictions_wikidata jw ON jc.wikidata_id = jw.id
LEFT JOIN jurisdiction jd ON jc.details_search_id = jd.id;

-- Create indexes on materialized view
CREATE INDEX IF NOT EXISTS idx_mjf_master_id ON master_jurisdictions_full(master_id);
CREATE INDEX IF NOT EXISTS idx_mjf_state ON master_jurisdictions_full(state_code);
CREATE INDEX IF NOT EXISTS idx_mjf_type ON master_jurisdictions_full(primary_type);
CREATE INDEX IF NOT EXISTS idx_mjf_nces ON master_jurisdictions_full(nces_id);

-- Refresh the materialized view
-- Run after updates: REFRESH MATERIALIZED VIEW master_jurisdictions_full;


-- ============================================================================
-- 11. MANUAL CORRECTIONS: Override automatic matching
-- ============================================================================

-- Example: Manually link two records that should match
INSERT INTO jurisdiction_crosswalk 
(org_location_id, details_search_id, primary_name, state_code, 
 match_method, match_confidence)
VALUES 
(12345, 67890, 'Manual Match Example', 'CA', 'manual_override', 1.0)
ON CONFLICT DO NOTHING;

-- Update master jurisdiction with corrected canonical name
UPDATE master_jurisdictions
SET canonical_name = 'Corrected Name',
    updated_at = NOW()
WHERE id = 123;


-- ============================================================================
-- 12. REPORTING: Summary statistics
-- ============================================================================

-- Overall system health report
SELECT 
    'Total Organizations' as metric,
    COUNT(*)::TEXT as value
FROM organization_location
UNION ALL
SELECT 
    'Total Master Jurisdictions',
    COUNT(*)::TEXT
FROM master_jurisdictions
UNION ALL
SELECT 
    'Total Crosswalk Entries',
    COUNT(*)::TEXT
FROM jurisdiction_crosswalk
UNION ALL
SELECT 
    'Unique Domains',
    COUNT(DISTINCT domain)::TEXT
FROM domain_registry
UNION ALL
SELECT 
    'Average Match Confidence',
    ROUND(AVG(match_confidence), 2)::TEXT
FROM jurisdiction_crosswalk
UNION ALL
SELECT 
    'High Quality Records (>0.75)',
    COUNT(*)::TEXT
FROM master_jurisdictions
WHERE data_completeness_score > 0.75;
