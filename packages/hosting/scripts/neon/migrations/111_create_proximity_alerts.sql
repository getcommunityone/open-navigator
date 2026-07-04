CREATE TABLE proximity_alerts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    alert_name VARCHAR(255) NOT NULL,
    target_radius_meters DOUBLE PRECISION NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    center_point GEOGRAPHY(POINT, 4326) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_proximity_alerts_user_id ON proximity_alerts(user_id);
CREATE INDEX idx_proximity_alerts_center_point ON proximity_alerts USING GIST (center_point);
