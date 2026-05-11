-- Counties where GSA and NACO disagree on registrable domain (review for bad GSA matches).
-- Run: dbt compile --select analysis:audit_county_gsa_naco_domain_mismatch  (or run query in warehouse)

WITH g AS (
    SELECT jurisdiction_id, lower(trim(domain_name)) AS d
    FROM {{ ref('int_jurisdiction_websites') }}
    WHERE jurisdiction_id LIKE 'county_%'
      AND website_source = 'gsa'
),
n AS (
    SELECT jurisdiction_id, lower(trim(domain_name)) AS d
    FROM {{ ref('int_jurisdiction_websites') }}
    WHERE jurisdiction_id LIKE 'county_%'
      AND website_source = 'naco'
)
SELECT g.jurisdiction_id, g.d AS gsa_domain, n.d AS naco_domain
FROM g
INNER JOIN n USING (jurisdiction_id)
WHERE g.d IS NOT NULL
  AND n.d IS NOT NULL
  AND g.d <> n.d
ORDER BY g.jurisdiction_id;
