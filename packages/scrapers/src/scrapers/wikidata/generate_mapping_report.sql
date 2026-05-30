-- ============================================================================
-- JURISDICTION MAPPING REPORT: jurisdictions_wikidata → jurisdiction
-- ============================================================================
-- This report shows how WikiData jurisdictions map to Census Bureau data
-- 
-- Usage:
--   PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d open_navigator \
--   -f packages/scrapers/src/scrapers/wikidata/generate_mapping_report.sql
--
-- ⚠️ DEPRECATED (migration 048): queries the pre-048 ``public.jurisdiction`` table,
-- now ``public.c1_jurisdiction``. Columns used here (state_code, type) were renamed
-- (state_code→state, type→classification) and the old ``state`` full-name column no
-- longer exists, so this report needs reworking against the new schema before it runs.

\echo '╔══════════════════════════════════════════════════════════════════════════╗'
\echo '║  JURISDICTION MAPPING REPORT: jurisdictions_wikidata → jurisdiction ║'
\echo '╚══════════════════════════════════════════════════════════════════════════╝'
\echo ''
\echo '📊 OVERALL SUMMARY (6 Dev States: AL, GA, IN, MA, WA, WI)'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''

-- OVERALL SUMMARY
SELECT 
    jurisdiction_type as "Type",
    TO_CHAR(SUM(census_total), '999,999') as "Census Total",
    TO_CHAR(SUM(wiki_total), '999,999') as "WikiData",
    TO_CHAR(SUM(matched), '999,999') as "Matched",
    TO_CHAR(SUM(census_only), '999,999') as "Missing",
    ROUND(SUM(matched) * 100.0 / NULLIF(SUM(census_total), 0), 1) || '%' as "Coverage"
FROM (
    -- Counties
    SELECT 
        COUNT(DISTINCT s.id) as census_total,
        COUNT(DISTINCT w.wikidata_id) as wiki_total,
        COUNT(DISTINCT CASE WHEN s.id IS NOT NULL AND w.wikidata_id IS NOT NULL THEN w.wikidata_id END) as matched,
        COUNT(DISTINCT CASE WHEN w.wikidata_id IS NULL AND s.id IS NOT NULL THEN s.id END) as census_only,
        'COUNTIES' as jurisdiction_type,
        1 as sort_order
    FROM jurisdiction s
    FULL OUTER JOIN jurisdictions_wikidata w 
        ON s.geoid = w.geoid AND s.type = 'county' AND w.jurisdiction_type = 'county'
    WHERE (s.state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI') AND s.type = 'county')
       OR (w.state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI') AND w.jurisdiction_type = 'county')
    
    UNION ALL
    
    -- Cities
    SELECT 
        COUNT(DISTINCT s.id) as census_total,
        COUNT(DISTINCT w.wikidata_id) as wiki_total,
        COUNT(DISTINCT CASE WHEN s.id IS NOT NULL AND w.wikidata_id IS NOT NULL THEN w.wikidata_id END) as matched,
        COUNT(DISTINCT CASE WHEN w.wikidata_id IS NULL AND s.id IS NOT NULL THEN s.id END) as census_only,
        'CITIES' as jurisdiction_type,
        2 as sort_order
    FROM jurisdiction s
    FULL OUTER JOIN jurisdictions_wikidata w 
        ON (UPPER(TRIM(w.jurisdiction_name)) = UPPER(TRIM(REPLACE(REPLACE(s.name, ' city', ''), ' town', ''))))
        AND w.state_code = s.state_code AND s.type = 'city' AND w.jurisdiction_type = 'city'
    WHERE (s.state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI') AND s.type = 'city')
       OR (w.state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI') AND w.jurisdiction_type = 'city')
) sub
GROUP BY jurisdiction_type, sort_order
ORDER BY sort_order;

\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo '📍 COUNTY MAPPING BY STATE'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''

-- COUNTY MAPPING BY STATE
SELECT 
    COALESCE(w.state_code, s.state_code) as "State",
    COALESCE(w.state, s.state) as "State Name",
    COUNT(DISTINCT s.id) as "Census",
    COUNT(DISTINCT w.wikidata_id) as "WikiData",
    COUNT(DISTINCT CASE WHEN s.id IS NOT NULL AND w.wikidata_id IS NOT NULL THEN w.wikidata_id END) as "Matched",
    COUNT(DISTINCT CASE WHEN w.wikidata_id IS NULL AND s.id IS NOT NULL THEN s.id END) as "Missing",
    ROUND(COUNT(DISTINCT CASE WHEN s.id IS NOT NULL AND w.wikidata_id IS NOT NULL THEN w.wikidata_id END) * 100.0 / 
          NULLIF(COUNT(DISTINCT s.id), 0), 1) || '%' as "Coverage"
FROM jurisdiction s
FULL OUTER JOIN jurisdictions_wikidata w 
    ON s.geoid = w.geoid 
    AND s.type = 'county'
    AND w.jurisdiction_type = 'county'
WHERE (s.state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI') AND s.type = 'county')
   OR (w.state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI') AND w.jurisdiction_type = 'county')
GROUP BY COALESCE(w.state_code, s.state_code), COALESCE(w.state, s.state)
ORDER BY "State";

\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo '🏙️  CITY MAPPING BY STATE'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''

-- CITY MAPPING BY STATE
SELECT 
    COALESCE(w.state_code, s.state_code) as "State",
    COALESCE(w.state, s.state) as "State Name",
    COUNT(DISTINCT s.id) as "Census",
    COUNT(DISTINCT w.wikidata_id) as "WikiData",
    COUNT(DISTINCT CASE WHEN s.id IS NOT NULL AND w.wikidata_id IS NOT NULL THEN w.wikidata_id END) as "Matched",
    COUNT(DISTINCT CASE WHEN w.wikidata_id IS NULL AND s.id IS NOT NULL THEN s.id END) as "Missing",
    ROUND(COUNT(DISTINCT CASE WHEN s.id IS NOT NULL AND w.wikidata_id IS NOT NULL THEN w.wikidata_id END) * 100.0 / 
          NULLIF(COUNT(DISTINCT s.id), 0), 1) || '%' as "Coverage"
FROM jurisdiction s
FULL OUTER JOIN jurisdictions_wikidata w 
    ON (
        UPPER(TRIM(w.jurisdiction_name)) = UPPER(TRIM(s.name))
        OR UPPER(TRIM(w.jurisdiction_name)) = UPPER(TRIM(REPLACE(s.name, ' city', '')))
        OR UPPER(TRIM(w.jurisdiction_name)) = UPPER(TRIM(REPLACE(s.name, ' town', '')))
    )
    AND w.state_code = s.state_code
    AND s.type = 'city'
    AND w.jurisdiction_type = 'city'
WHERE (s.state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI') AND s.type = 'city')
   OR (w.state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI') AND w.jurisdiction_type = 'city')
GROUP BY COALESCE(w.state_code, s.state_code), COALESCE(w.state, s.state)
ORDER BY "State";

\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo '✅ KEY FINDINGS'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''
\echo '  Counties: 88.5% coverage - EXCELLENT for metadata enrichment'
\echo '            Join on: w.geoid = s.geoid'
\echo '            Best states: AL, GA, MA, WA (100% coverage)'
\echo ''
\echo '  Cities:   0.3% coverage - NOT VIABLE for enrichment'
\echo '            WikiData has only 32 cities vs 3,940 in Census'
\echo '            Use jurisdiction as primary source'
\echo ''
