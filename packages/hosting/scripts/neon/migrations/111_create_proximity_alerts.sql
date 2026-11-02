BEGIN;

CREATE TABLE IF NOT EXISTS public.proximity_alerts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES public."user"(user_id) ON DELETE CASCADE,
    alert_name VARCHAR(255) NOT NULL,
    target_radius_meters DOUBLE PRECISION NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_proximity_alerts_id ON public.proximity_alerts (id);
CREATE INDEX IF NOT EXISTS ix_proximity_alerts_user_id ON public.proximity_alerts (user_id);

COMMIT;
