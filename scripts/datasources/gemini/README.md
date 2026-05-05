# Gemini AI Meeting Analysis

Scripts for analyzing government meeting transcripts using Google Gemini AI with policy frame analysis.

**✅ 100% FREE** - Uses Gemini 1.5 Flash free tier (15 requests/min, 1,500/day, 1M tokens/day)

## Overview

This directory contains scripts that use Google's Gemini AI (FREE TIER) to perform deep policy analysis on government meeting transcripts. The analysis extracts:

- **Competing problem frames** - How stakeholders diagnose causes and assign responsibility
- **Moral value conflicts** - Tensions between collective safety vs individual liberty, equity vs efficiency
- **Power dynamics** - Who influenced decisions, whose interests advanced/constrained
- **Financial impacts** - Dollar amounts and budget implications
- **Decision timelines** - Chronological flow of events

## Scripts

### `analyze_meeting_transcripts.py`

Main script for analyzing meeting transcripts with Gemini AI.

**What it does:**
1. Fetches recent meetings from `events_search` (priority states: AL, GA, IN, MA, WA, WI)
2. Filters for known channel types (municipal, county, school) OR channels in localview
3. Gets transcripts from `events_text_search`
4. Analyzes using Gemini 1.5 Flash (FREE tier) with policy_analysis.md prompt
5. Stores structured JSON, human-readable summary, and Mermaid timeline in `events_text_ai`
6. Supports incremental processing (skips already analyzed)

**Usage:**

```bash
# Setup (first time)
pip install google-generativeai

# Get FREE API key from https://makersuite.google.com/app/apikey
# Add to .env file:
echo "GEMINI_API_KEY=your_key_here" >> .env

# ✅ All analysis is FREE (within generous daily limits)

# Analyze most recent 5 meetings per channel (default)
python scripts/datasources/gemini/analyze_meeting_transcripts.py

# Analyze specific state
python scripts/datasources/gemini/analyze_meeting_transcripts.py --states MA

# Analyze more meetings per channel
python scripts/datasources/gemini/analyze_meeting_transcripts.py --meetings-per-channel 10

# Force re-analysis (ignore previously analyzed)
python scripts/datasources/gemini/analyze_meeting_transcripts.py --force

# Dry run (see what would be analyzed)
python scripts/datasources/gemini/analyze_meeting_transcripts.py --dry-run

# Multiple states
python scripts/datasources/gemini/analyze_meeting_transcripts.py --states "MA,WI,GA"
```

## Database Schema

### `events_text_ai` Table

Stores AI analysis results:

```sql
CREATE TABLE events_text_ai (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events_search(id),
    video_id VARCHAR(20),
    analysis_type VARCHAR(50) DEFAULT 'policy_frame_analysis',
    ai_model VARCHAR(100) DEFAULT 'gemini-1.5-flash',
    
    -- Analysis outputs
    structured_analysis JSONB,   -- JSON from policy_analysis.md
    summary_text TEXT,            -- Human-readable summary
    timeline_mermaid TEXT,        -- Mermaid timeline diagram
    
    -- Metadata
    processing_time_seconds FLOAT,
    tokens_used INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Query Results

```sql
-- View recent analyses
SELECT 
    e.title,
    e.jurisdiction_name,
    e.state_code,
    e.event_date,
    ai.ai_model,
    ai.processing_time_seconds,
    ai.created_at
FROM events_text_ai ai
JOIN events_search e ON ai.event_id = e.id
ORDER BY ai.created_at DESC
LIMIT 10;

-- Get structured JSON analysis
SELECT 
    e.title,
    ai.structured_analysis->'meeting'->'body_name' as body,
    jsonb_array_length(ai.structured_analysis->'decisions') as decision_count,
    ai.summary_text
FROM events_text_ai ai
JOIN events_search e ON ai.event_id = e.id
WHERE ai.error_message IS NULL;

-- Extract frame analysis from JSON
SELECT 
    e.title,
    decision->>'topic' as topic,
    decision->'frame_analysis'->'dominant_frame'->>'frame_label' as dominant_frame,
    decision->'frame_analysis'->'counter_frames'->0->>'frame_label' as counter_frame
FROM events_text_ai ai
JOIN events_search e ON ai.event_id = e.id,
LATERAL jsonb_array_elements(ai.structured_analysis->'decisions') as decision
WHERE ai.error_message IS NULL;
```

## Prompt Template

The analysis uses `/prompts/policy_analysis.md` which defines:

- **Entity linking** - Person slugs, organization types, legislation IDs
- **Theme classification** - COFOG codes, NTEE categories
- **Frame analysis** - Causal interpretations, value conflicts, power maps
- **Smart Brevity** - Concise, headline-first writing style
- **Three outputs** - JSON, human summary, Mermaid timeline

## Cost Estimates

**Gemini 1.5 Flash (FREE TIER):**
- ✅ **FREE up to 15 requests/minute**
- ✅ **FREE up to 1 million tokens/day**
- ✅ **FREE up to 1,500 requests/day**

**Typical meeting analysis:**
- Input: 10K-50K tokens (transcript + prompt)
- Output: 5K-10K tokens (JSON + summary + timeline)
- **Cost: $0.00** (within free tier limits)

**For 5 meetings × 10 channels = 50 meetings:**
- **Estimated cost: FREE** ✅
- Processing time: ~4 minutes (with 5s delays)
- Well within free tier daily limits

**Free tier limits:**
- 15 requests/minute = 900 requests/hour
- 1,500 requests/day max
- Script processes ~12 meetings/min = 720 meetings/hour (with 5s delays)
- Can analyze all 1,500 daily meetings in ~2 hours

## Rate Limits

**Gemini 1.5 Flash FREE tier limits:**
- ✅ **15 requests/minute**
- ✅ **1,500 requests/day**
- ✅ **1 million tokens/day**

**Current settings:**
- 5 second delay between requests (default)
- Processes ~12 meetings/minute (720/hour)
- Safely within 15 req/min free tier limit

**No rate limiting needed** for typical usage (under 1,500 meetings/day)

If you somehow hit limits:
```bash
# Slow down to 10s between requests
python scripts/datasources/gemini/analyze_meeting_transcripts.py --delay 10.0
```

## Workflow

### 1. Load Meeting Videos
```bash
# First, get meeting videos with transcripts
python scripts/datasources/youtube/load_youtube_events_to_postgres.py \
  --states AL,GA,IN,MA,WA,WI \
  --skip-transcripts \
  --max-videos 100
```

### 2. Get Transcripts (later, when needed)
```bash
# Fetch transcripts for stored videos
python scripts/datasources/youtube/load_youtube_events_to_postgres.py \
  --states AL,GA,IN,MA,WA,WI \
  --max-videos 10  # Just most recent ones
```

### 3. Analyze with Gemini
```bash
# Run AI analysis on meetings with transcripts
python scripts/datasources/gemini/analyze_meeting_transcripts.py
```

### 4. Query Results
```bash
# Check results
PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d open_navigator -c \
  "SELECT COUNT(*) FROM events_text_ai WHERE error_message IS NULL;"
```

## Troubleshooting

**Issue: "GEMINI_API_KEY not found"**
```bash
# Get key from https://makersuite.google.com/app/apikey
echo "GEMINI_API_KEY=AIza..." >> .env
```

**Issue: "google.generativeai not installed"**
```bash
pip install google-generativeai
```

**Issue: Rate limiting**
```bash
# Increase delay between requests
python scripts/datasources/gemini/analyze_meeting_transcripts.py --delay 5.0
```

**Issue: JSON parsing errors**
- Check `events_text_ai.error_message` column
- Review `raw_response` for debugging
- Gemini may occasionally return malformed JSON

**Issue: No meetings found**
- Check that meetings have transcripts: `SELECT COUNT(*) FROM events_text_search;`
- Verify state codes: `SELECT DISTINCT state_code FROM events_search;`
- Try `--force` to re-analyze existing meetings

## Next Steps

1. **Aggregate insights** - Build summary views of frame analysis across meetings
2. **Trend detection** - Track how frames evolve over time
3. **Export to frontend** - Display analysis results in UI
4. **Fine-tune prompts** - Adjust policy_analysis.md based on results
5. **Batch processing** - Analyze historical meetings en masse
