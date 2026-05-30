CREATE TABLE IF NOT EXISTS bronze.bronze_events_analysis_ai (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES event(event_id) ON DELETE CASCADE,
    video_id VARCHAR(64) NOT NULL,
    analysis_type VARCHAR(50) DEFAULT 'policy_frame_analysis',
    ai_model VARCHAR(100) DEFAULT 'gemini-1.5-flash',
    prompt_version VARCHAR(50) DEFAULT 'v1.0',
    raw_response TEXT,
    structured_analysis JSONB,
    summary_text TEXT,
    timeline_mermaid TEXT,
    processing_time_seconds FLOAT,
    tokens_used INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_id, analysis_type, ai_model)
);

CREATE INDEX IF NOT EXISTS idx_events_ai_event_id ON bronze.bronze_events_analysis_ai(event_id);
CREATE INDEX IF NOT EXISTS idx_events_ai_video_id ON bronze.bronze_events_analysis_ai(video_id);
CREATE INDEX IF NOT EXISTS idx_events_ai_created ON bronze.bronze_events_analysis_ai(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_ai_analysis_type ON bronze.bronze_events_analysis_ai(analysis_type);
