-- Migration: fold public.organization_nonprofit (43,726 rows) into public.c1_organization.
--
-- ``organization_nonprofit`` was a separate IRS-990-derived table. After 048/049 we have
-- one canonical organization table (``c1_organization``) aligned to opencivicdata. This
-- migration:
--
--   1. Adds the IRS-990-specific columns to ``c1_organization`` (tagged
--      ``[source: irs_990]``).
--   2. Drops the legacy_id PK + NOT NULL (was inherited from the old ``organization`` table,
--      0 rows, useless going forward) and replaces it with a UNIQUE constraint on ``ein``
--      so the natural 990 key prevents duplicates on re-fold.
--   3. Widens ``revenue`` from ``double precision`` to ``bigint`` (the IRS-990 source type;
--      ``c1_organization`` had 0 rows so type change is lossless).
--   4. Copies all rows from ``organization_nonprofit`` -> ``c1_organization`` with column
--      mapping: ``street_address`` -> ``address``; ``last_updated`` -> ``updated_at``;
--      everything else direct.
--   5. Drops ``organization_nonprofit`` and its indexes (CASCADE).
--
-- After this migration, ``classification`` and ``classification_code`` co-exist. They are
-- semantically distinct: ``classification`` is the OCD organization-type (government /
-- nonprofit / committee), ``classification_code`` is the IRS classification code (a small
-- numeric string). Both are kept.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/050_fold_organization_nonprofit_into_c1_organization.sql

BEGIN;

-- ----- Step 1: prepare c1_organization to receive 990 data --------------------------

-- legacy_id (int, NOT NULL, PK) blocks NULL inserts. 0 existing rows -> safe to drop.
ALTER TABLE public.c1_organization DROP CONSTRAINT IF EXISTS c1_organization_pkey;
ALTER TABLE public.c1_organization ALTER COLUMN legacy_id DROP NOT NULL;
-- slug is NOT NULL too, blocks 990 inserts that have no slug
ALTER TABLE public.c1_organization ALTER COLUMN slug DROP NOT NULL;

-- Widen revenue type
ALTER TABLE public.c1_organization ALTER COLUMN revenue TYPE BIGINT USING revenue::BIGINT;

-- Add IRS-990 columns
ALTER TABLE public.c1_organization
    ADD COLUMN IF NOT EXISTS street_address                  TEXT,
    ADD COLUMN IF NOT EXISTS zip_code                        VARCHAR(10),
    ADD COLUMN IF NOT EXISTS ntee_description                TEXT,
    ADD COLUMN IF NOT EXISTS subsection_code                 VARCHAR(10),
    ADD COLUMN IF NOT EXISTS affiliation_code                VARCHAR(10),
    ADD COLUMN IF NOT EXISTS classification_code             VARCHAR(20),
    ADD COLUMN IF NOT EXISTS assets                          BIGINT,
    ADD COLUMN IF NOT EXISTS income                          BIGINT,
    ADD COLUMN IF NOT EXISTS ruling_date                     DATE,
    ADD COLUMN IF NOT EXISTS foundation_code                 VARCHAR(10),
    ADD COLUMN IF NOT EXISTS pf_filing_requirement_code      VARCHAR(10),
    ADD COLUMN IF NOT EXISTS accounting_period               VARCHAR(10),
    ADD COLUMN IF NOT EXISTS asset_code                      VARCHAR(10),
    ADD COLUMN IF NOT EXISTS income_code                     VARCHAR(10),
    ADD COLUMN IF NOT EXISTS filing_requirement_code         VARCHAR(10),
    ADD COLUMN IF NOT EXISTS exempt_organization_status_code VARCHAR(10),
    ADD COLUMN IF NOT EXISTS tax_period                      VARCHAR(10),
    ADD COLUMN IF NOT EXISTS asset_amount                    BIGINT,
    ADD COLUMN IF NOT EXISTS income_amount                   BIGINT,
    ADD COLUMN IF NOT EXISTS form_990_revenue_amount         BIGINT,
    ADD COLUMN IF NOT EXISTS source                          VARCHAR(50);

-- ein becomes the natural unique key (since 990 data is EIN-keyed). UNIQUE permits NULL
-- (multiple rows without EIN allowed — non-990 rows). PARTIAL index on non-null EIN.
CREATE UNIQUE INDEX IF NOT EXISTS ix_c1_organization_ein_unique
    ON public.c1_organization (ein) WHERE ein IS NOT NULL;

COMMENT ON COLUMN public.c1_organization.street_address                  IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.zip_code                        IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.ntee_description                IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.subsection_code                 IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.affiliation_code                IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.classification_code             IS '[source: irs_990] IRS classification code (distinct from OCD classification column)';
COMMENT ON COLUMN public.c1_organization.assets                          IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.income                          IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.ruling_date                     IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.foundation_code                 IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.pf_filing_requirement_code      IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.accounting_period               IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.asset_code                      IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.income_code                     IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.filing_requirement_code         IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.exempt_organization_status_code IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.tax_period                      IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.asset_amount                    IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.income_amount                   IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.form_990_revenue_amount         IS '[source: irs_990]';
COMMENT ON COLUMN public.c1_organization.source                          IS '[source: communityone] data provenance label (e.g. ''irs_form990'', ''openstates'')';


-- ----- Step 2: copy 990 data into c1_organization ----------------------------------

INSERT INTO public.c1_organization (
    -- Core identification
    name, ein,
    -- Location
    address, city, state, county, zip_code,
    -- NTEE / classification
    ntee_code, ntee_description, classification_code,
    -- Financials
    revenue, assets, income,
    -- IRS metadata
    subsection_code, affiliation_code, ruling_date,
    foundation_code, pf_filing_requirement_code, accounting_period,
    asset_code, income_code, filing_requirement_code,
    exempt_organization_status_code, tax_period,
    asset_amount, income_amount, form_990_revenue_amount,
    -- Provenance
    source, updated_at, created_at,
    -- OCD defaults (avoid NULL NOT NULL violations)
    extras, links, sources, other_names
)
SELECT
    n.name,
    n.ein,
    n.street_address,
    n.city,
    n.state,
    n.county,
    n.zip_code,
    n.ntee_code,
    n.ntee_description,
    n.classification_code,
    n.revenue,
    n.assets,
    n.income,
    n.subsection_code,
    n.affiliation_code,
    n.ruling_date,
    n.foundation_code,
    n.pf_filing_requirement_code,
    n.accounting_period,
    n.asset_code,
    n.income_code,
    n.filing_requirement_code,
    n.exempt_organization_status_code,
    n.tax_period,
    n.asset_amount,
    n.income_amount,
    n.form_990_revenue_amount,
    COALESCE(n.source, 'irs_form990'),
    COALESCE(n.last_updated AT TIME ZONE 'UTC', now()),
    now(),
    '{}'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb
FROM public.organization_nonprofit n
ON CONFLICT (ein) WHERE ein IS NOT NULL DO NOTHING;


-- ----- Step 3: drop organization_nonprofit ------------------------------------------

DROP TABLE public.organization_nonprofit CASCADE;

COMMIT;
