-- Replace the ad-hoc cause_ntee reference table with the hierarchical tag taxonomy.
-- Dev only: psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/091_replace_cause_ntee_with_tag.sql
--
-- cause_ntee (+ legacy aliases) -> tag / tag_closure / tag_organization
-- The three tables are populated by dbt (marts: tag, tag_closure,
-- tag_organization); this migration only (re)creates the empty structures and
-- drops the superseded table so the dbt build has a clean target.

BEGIN;

-- Drop the bridge/closure first (FK dependants), then legacy taxonomy tables.
DROP TABLE IF EXISTS public.tag_organization CASCADE;
DROP TABLE IF EXISTS public.tag_closure CASCADE;
DROP TABLE IF EXISTS public.tag CASCADE;
DROP TABLE IF EXISTS public.cause_ntee CASCADE;
DROP TABLE IF EXISTS public.causes_ntee CASCADE;
DROP TABLE IF EXISTS public.reference_ntee_codes CASCADE;

-- Taxonomy nodes. Collision-safe synthetic key: vocabulary || '|' || source_code.
CREATE TABLE public.tag (
    tag_id VARCHAR(120) PRIMARY KEY,            -- e.g. 'ntee|E20', 'everyorg|climate'
    vocabulary VARCHAR(20) NOT NULL,            -- 'ntee' or 'everyorg'
    source_code VARCHAR(100) NOT NULL,          -- original code/slug within the vocabulary
    label TEXT,                                 -- human-readable name
    description TEXT,                           -- detailed description
    parent_tag_id VARCHAR(120),                 -- adjacency edge; NULL at roots (self-FK)
    depth INTEGER,                              -- distance from root (0 = root)
    breadcrumb TEXT,                            -- denormalized root->leaf path
    category VARCHAR(100),
    subcategory VARCHAR(100),                   -- NTEE subcategory (NULL for everyorg)
    icon VARCHAR(100),                          -- EveryOrg icon slug (NULL for ntee)
    popularity_rank INTEGER,                    -- EveryOrg popularity rank (NULL for ntee)
    source VARCHAR(50),                         -- 'irs' or 'everyorg'
    source_ingested_at TIMESTAMPTZ,
    dbt_loaded_at TIMESTAMPTZ,
    -- Deferrable so bulk loaders can insert children before parents in one txn.
    CONSTRAINT fk_tag_parent FOREIGN KEY (parent_tag_id) REFERENCES public.tag(tag_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX idx_tag_vocabulary ON public.tag(vocabulary);
CREATE INDEX idx_tag_parent ON public.tag(parent_tag_id);
CREATE INDEX idx_tag_label_search ON public.tag USING GIN (to_tsvector('english', coalesce(label, '')));
CREATE INDEX idx_tag_description_search ON public.tag USING GIN (to_tsvector('english', coalesce(description, '')));

-- Transitive closure ("sub table") for subtree queries. Includes self pairs (depth 0).
CREATE TABLE public.tag_closure (
    ancestor_tag_id VARCHAR(120) NOT NULL REFERENCES public.tag(tag_id),
    descendant_tag_id VARCHAR(120) NOT NULL REFERENCES public.tag(tag_id),
    depth INTEGER NOT NULL,
    dbt_loaded_at TIMESTAMPTZ,
    PRIMARY KEY (ancestor_tag_id, descendant_tag_id)
);

CREATE INDEX idx_tag_closure_descendant ON public.tag_closure(descendant_tag_id);

-- Bridge: golden organization -> most specific NTEE tag. NTEE-only by design.
CREATE TABLE public.tag_organization (
    master_org_id VARCHAR(64) NOT NULL,         -- FK -> mdm_organization.master_org_id
    tag_id VARCHAR(120) NOT NULL REFERENCES public.tag(tag_id),
    is_primary BOOLEAN,
    match_method VARCHAR(20),                   -- 'exact' | 'prefix' | 'major_group'
    assigned_at TIMESTAMPTZ,
    PRIMARY KEY (master_org_id, tag_id)
);

CREATE INDEX idx_tag_organization_tag ON public.tag_organization(tag_id);

COMMIT;
