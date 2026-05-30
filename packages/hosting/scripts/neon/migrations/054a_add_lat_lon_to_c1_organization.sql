-- Migration 054a: add latitude + longitude to c1_organization in preparation for the
-- organization_location fold (571,448 rows of HIFLD/etc location data have geo coords
-- that the existing c1_organization schema can't capture).
--
-- Applied before the fold script runs; migration 054b drops organization_location after.

BEGIN;

ALTER TABLE public.c1_organization
    ADD COLUMN IF NOT EXISTS latitude  NUMERIC,
    ADD COLUMN IF NOT EXISTS longitude NUMERIC;

COMMENT ON COLUMN public.c1_organization.latitude  IS '[source: organization_location fold] WGS84 latitude in decimal degrees';
COMMENT ON COLUMN public.c1_organization.longitude IS '[source: organization_location fold] WGS84 longitude in decimal degrees';

CREATE INDEX IF NOT EXISTS ix_c1_organization_classification
    ON public.c1_organization (classification);
CREATE INDEX IF NOT EXISTS ix_c1_organization_state
    ON public.c1_organization (state);
CREATE INDEX IF NOT EXISTS ix_c1_organization_source
    ON public.c1_organization (source);

COMMIT;
